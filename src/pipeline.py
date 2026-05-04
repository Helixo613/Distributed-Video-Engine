from __future__ import annotations

import json
import shutil as shutil_lib
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from adaptive_partitioner import build_partition_plan
from cost_estimator import LinearCostEstimator
from evaluator import evaluate_output
from feature_extractor import extract_video_features
from ffmpeg_utils import (
    analyze_video,
    benchmark_serial_profile,
    benchmark_serial_sample,
    ensure_dir,
    merge_chunks,
    process_chunk,
    run_serial_baseline,
    execution_backend_info,
    resolve_execution_backend,
)
from scheduler import search_best_configuration
from video_types import ChunkResult, PartitionPlan, SelectionResult


ProgressCallback = Optional[Callable[[int], None]]


def execute_partition_plan(
    partition_plan: PartitionPlan,
    output_path: str,
    workers: int,
    filter_chain: str,
    temp_dir: str,
    execution_backend: str | None = None,
    progress_callback: ProgressCallback = None,
    phase_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Execute a prepared partition plan and return detailed timing information."""
    results: list[ChunkResult] = []
    submit_start = time.perf_counter()
    if phase_callback:
        phase_callback("parallel")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(process_chunk, chunk, filter_chain, execution_backend=execution_backend): chunk
            for chunk in partition_plan.chunks
        }
        dispatch_time = time.perf_counter() - submit_start
        completed = 0
        compute_start = time.perf_counter()
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(int((completed / max(1, len(partition_plan.chunks))) * 100))
        compute_time = time.perf_counter() - compute_start

    results.sort(key=lambda item: item.chunk_id)
    failed = [result for result in results if not result.success]
    if failed:
        raise RuntimeError(f"{len(failed)} chunks failed")

    if phase_callback:
        phase_callback("merging")
    merge_start = time.perf_counter()
    chunk_paths = [result.output_path or partition_plan.chunks[result.chunk_id].output_path for result in results]
    merged = merge_chunks(chunk_paths, output_path, temp_dir)
    merge_time = time.perf_counter() - merge_start
    if not merged:
        raise RuntimeError("Merge failed")

    mean_chunk_time = sum(result.elapsed for result in results) / max(1, len(results))
    straggler_ratio = max((result.elapsed for result in results), default=0.0) / max(mean_chunk_time, 1e-6)

    return {
        "dispatch_time": dispatch_time,
        "compute_time": compute_time,
        "merge_time": merge_time,
        "results": [asdict(result) for result in results],
        "straggler_ratio": straggler_ratio,
        "actual_makespan_proxy": max((result.elapsed for result in results), default=0.0),
    }


def _segment_records(record: dict, feature_result, partition_plan) -> list[dict]:
    segment_lookup = {segment.segment_id: segment for segment in feature_result.segment_features}
    segment_records = []
    for chunk_record in record["actual_chunk_runtime"]:
        chunk_id = chunk_record["chunk_id"]
        chunk = partition_plan.chunks[chunk_id]
        source_ids = chunk.source_segment_ids
        # Fall back to time-overlap mapping when source_segment_ids is empty
        # (equal-duration and rate-adjusted policies don't set them).
        if not source_ids:
            chunk_start = chunk.start
            chunk_end = chunk.start + chunk.duration
            source_ids = [
                seg.segment_id
                for seg in feature_result.segment_features
                if seg.start < chunk_end and seg.end > chunk_start
            ]
        for segment_id in source_ids:
            segment = segment_lookup.get(segment_id)
            if segment is None:
                continue
            payload = asdict(segment)
            payload.update(
                {
                    "input_file": record["input_file"],
                    "video_id": record["video_id"],
                    "partition_policy": record["partition_policy"],
                    "worker_count": record["worker_count"],
                    "chunk_count": record["chunk_count"],
                    "chunk_id": chunk_id,
                    "actual_chunk_runtime": chunk_record["elapsed"],
                    "schema_version": record["schema_version"],
                    "quality_reference_label": record["quality"].get("reference_label"),
                }
            )
            segment_records.append(payload)
    return segment_records


def run_processing_pipeline(
    input_path: str,
    output_path: str,
    filter_chain: str,
    partition_policy: str = "equal-duration",
    worker_count: int = 1,
    chunk_count: Optional[int] = None,
    scheduler_enabled: bool = False,
    scheduler_workers: Optional[list[int]] = None,
    scheduler_chunk_multipliers: Optional[list[float]] = None,
    enable_full_serial_baseline: bool = False,
    enable_encode_time_proxy: bool = False,
    enable_quality_metrics: bool = True,
    enable_vmaf: bool = False,
    estimator: Optional[LinearCostEstimator] = None,
    progress_callback: ProgressCallback = None,
    temp_dir: Optional[str] = None,
    keep_temp: bool = False,
    serial_reference_time: Optional[float] = None,
    serial_reference_e2e_time: Optional[float] = None,
    serial_reference_output_path: Optional[str] = None,
    reuse_serial_reference_on_fallback: bool = False,
    rate_profile: Optional[list[tuple[float, float]]] = None,
    max_workers: Optional[int] = None,
    execution_backend: str | None = None,
) -> dict:
    """Run the research pipeline and emit a paper-oriented experiment record."""
    resolved_backend = resolve_execution_backend(execution_backend)
    backend_info = execution_backend_info(execution_backend)
    temp_root = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="dve_run_"))
    ensure_dir(temp_root)

    started_at = time.time()
    pipeline_start = time.perf_counter()
    probe_start = time.perf_counter()
    metadata = analyze_video(input_path)
    probe_time = time.perf_counter() - probe_start

    feature_result = extract_video_features(
        input_path=input_path,
        enable_encode_time_proxy=enable_encode_time_proxy,
    )

    serial_sample_seconds = None
    serial_sample_time = None
    serial_sample_positions: list[float] = []
    serial_sample_times: list[float] = []
    serial_sampling_time = 0.0
    projected_serial_time = None
    requested_partition_policy = partition_policy

    # Always do rate profiling when the scheduler is enabled — the multi-policy
    # search needs per-position encode rates to evaluate rate-adjusted partitions.
    # When serial_reference_time is provided, the profiling is NOT used for serial
    # estimation but its rate data still feeds the partitioner.
    should_profile_serial = partition_policy != "serial" and (
        serial_reference_time is None or (scheduler_enabled and rate_profile is None)
    )
    if should_profile_serial:
        serial_sample_seconds = min(1.0, metadata.duration)
        serial_profile_start = time.perf_counter()
        serial_profile = benchmark_serial_profile(
            input_path=input_path,
            temp_dir=str(temp_root),
            filter_chain=filter_chain,
            duration=metadata.duration,
            sample_seconds=serial_sample_seconds,
            sample_fractions=[0.0, 0.25, 0.5, 0.75, 0.95],
            execution_backend=resolved_backend,
        )
        serial_sampling_time = time.perf_counter() - serial_profile_start
        serial_sample_seconds = float(serial_profile["sample_seconds"])
        serial_sample_positions = list(serial_profile["positions"])
        serial_sample_times = list(serial_profile["samples"])
        serial_sample_time = float(serial_profile["mean_time"])
        if serial_sample_seconds > 0:
            projected_serial_time = (metadata.duration / serial_sample_seconds) * serial_sample_time
        # Build rate profile from multi-position profiling data for the scheduler.
        if rate_profile is None and serial_sample_positions and serial_sample_times and serial_sample_seconds > 0:
            rate_profile = [
                (pos, t / serial_sample_seconds)
                for pos, t in zip(serial_sample_positions, serial_sample_times)
            ]
    elif partition_policy != "serial" and serial_reference_time is None:
        serial_sample_seconds = min(2.0, metadata.duration)
        serial_sample_time = benchmark_serial_sample(
            input_path=input_path,
            temp_dir=str(temp_root),
            filter_chain=filter_chain,
            sample_seconds=serial_sample_seconds,
            execution_backend=resolved_backend,
        )
        serial_sample_times = [serial_sample_time]
        serial_sampling_time = serial_sample_time
        if serial_sample_seconds > 0:
            projected_serial_time = (metadata.duration / serial_sample_seconds) * serial_sample_time

    selected_workers = 1 if partition_policy == "serial" else worker_count
    selected_chunks = 1 if partition_policy == "serial" else (chunk_count or max(1, worker_count))
    selection_result: Optional[SelectionResult] = None
    scheduler_time = 0.0
    if scheduler_enabled and partition_policy != "serial":
        scheduler_start = time.perf_counter()
        selection_result = search_best_configuration(
            input_path=input_path,
            metadata=metadata,
            feature_result=feature_result,
            filter_chain=filter_chain,
            temp_dir=str(temp_root),
            workers=scheduler_workers or [1, 2, 4, 6, 8, 12, 16],
            chunk_multipliers=scheduler_chunk_multipliers or [1.0, 1.5, 2.0],
            partition_policy=partition_policy,
            serial_sample_time=serial_sample_time,
            serial_reference_time=serial_reference_time,
            measured_overheads={
                "probe": probe_time,
                "feature": feature_result.extraction_time,
            },
            estimator=estimator,
            rate_profile=rate_profile,
            max_workers=max_workers,
        )
        scheduler_time = time.perf_counter() - scheduler_start
        selected_workers = selection_result.selected.worker_count
        selected_chunks = selection_result.selected.chunk_count
        partition_policy = selection_result.selected.partition_policy

    partition_plan = build_partition_plan(
        input_path=input_path,
        metadata=metadata,
        temp_dir=str(temp_root),
        policy=partition_policy,
        num_chunks=selected_chunks,
        feature_result=feature_result,
        estimated_total_runtime=selection_result.estimated_serial_time if selection_result else projected_serial_time,
        estimator=estimator,
        rate_profile=rate_profile,
    )

    reused_serial_reference = (
        reuse_serial_reference_on_fallback
        and requested_partition_policy != "serial"
        and partition_plan.policy == "serial"
        and serial_reference_time is not None
        and serial_reference_output_path is not None
    )
    if reused_serial_reference:
        shutil_lib.copyfile(serial_reference_output_path, output_path)
        execution = {
            "dispatch_time": 0.0,
            "compute_time": serial_reference_time,
            "merge_time": 0.0,
            "results": [
                {
                    "chunk_id": 0,
                    "success": True,
                    "elapsed": serial_reference_time,
                    "error": None,
                    "return_code": 0,
                    "output_path": output_path,
                }
            ],
            "straggler_ratio": 1.0,
            "actual_makespan_proxy": serial_reference_time,
        }
        processing_complete = time.perf_counter()
    else:
        execution = execute_partition_plan(
            partition_plan=partition_plan,
            output_path=output_path,
            workers=selected_workers,
            filter_chain=filter_chain,
            temp_dir=str(temp_root),
            execution_backend=resolved_backend,
            progress_callback=progress_callback,
        )
        processing_complete = time.perf_counter()

    serial_baseline_output = None
    serial_baseline_time = serial_reference_time
    serial_baseline_source = "external_reference" if serial_reference_time is not None else None
    requested_serial_run = requested_partition_policy == "serial"

    # --- Symmetric timing: compute both views for ALL methods ---
    # compute_time: dispatch + chunk processing (wall-clock) + merge — the actual video work
    # e2e_time: wall-clock from pipeline_start to processing_complete — includes all overheads
    compute_time = execution["dispatch_time"] + execution["compute_time"] + execution["merge_time"]
    e2e_time = processing_complete - pipeline_start

    if requested_serial_run:
        serial_baseline_time = compute_time
        serial_baseline_output = output_path
        serial_baseline_source = "measured_serial_run"
    else:
        if reused_serial_reference and serial_reference_time is not None:
            e2e_time = serial_reference_time
            compute_time = serial_reference_time
        if serial_baseline_time is None and enable_full_serial_baseline:
            serial_baseline_output = str(temp_root / "serial_baseline.mp4")
            serial_baseline_time = run_serial_baseline(
                input_path,
                serial_baseline_output,
                filter_chain,
                execution_backend=resolved_backend,
            )
            serial_baseline_source = "measured_full_serial"
        elif serial_baseline_time is None:
            serial_baseline_source = "projected_only"

    # Primary metric for speedup: compute_time (symmetric across all methods)
    actual_total_time = compute_time

    if requested_serial_run:
        quality_reference_path = input_path
        quality_reference_label = "input"
    else:
        quality_reference_path = serial_reference_output_path or serial_baseline_output or input_path
        quality_reference_label = "serial_baseline" if quality_reference_path != input_path else "input"

    quality_metrics = {}
    quality_eval_time = 0.0
    if enable_quality_metrics:
        quality_start = time.perf_counter()
        quality_metrics = evaluate_output(
            input_path=input_path,
            output_path=output_path,
            sample_seconds=min(8.0, metadata.duration),
            enable_vmaf=enable_vmaf,
            reference_path=quality_reference_path,
            reference_label=quality_reference_label,
        )
        quality_eval_time = time.perf_counter() - quality_start

    speedup = (serial_baseline_time / compute_time) if serial_baseline_time is not None and compute_time > 0 else None
    efficiency = (speedup / selected_workers) if speedup is not None and selected_workers > 0 else None
    throughput = metadata.duration / compute_time if compute_time > 0 else None

    # Secondary: e2e speedup includes all pipeline overhead
    serial_e2e_ref = serial_reference_e2e_time if serial_reference_e2e_time is not None else (
        e2e_time if requested_serial_run else serial_baseline_time
    )
    speedup_e2e = (serial_e2e_ref / e2e_time) if serial_e2e_ref is not None and e2e_time > 0 else None

    decision_cost = {
        "T_metadata": probe_time,
        "T_features": feature_result.extraction_time,
        "T_scheduler": scheduler_time,
        "T_decide": probe_time + feature_result.extraction_time + scheduler_time,
        "T_execute": compute_time,
        "rho": ((probe_time + feature_result.extraction_time + scheduler_time) / compute_time) if compute_time > 0 else None,
    }

    predicted_total = selection_result.selected.predicted_e2e_time if selection_result else None
    prediction_signed_error = (predicted_total - compute_time) if predicted_total is not None else None
    prediction_error = abs(prediction_signed_error) if prediction_signed_error is not None else None
    prediction_relative_error = (prediction_error / compute_time) if prediction_error is not None and compute_time > 0 else None

    record = {
        "schema_version": "research-prototype.v3",
        "started_at": started_at,
        "input_file": input_path,
        "video_id": Path(input_path).stem,
        "video_duration_seconds": round(metadata.duration, 6),
        "metadata": asdict(metadata),
        "execution_backend": backend_info,
        "feature_summary": {
            "sample_fps": feature_result.sample_fps,
            "sample_width": feature_result.sample_width,
            "sample_height": feature_result.sample_height,
            "analysis_window_seconds": feature_result.analysis_window_seconds,
            "total_sample_frames": feature_result.total_sample_frames,
            "global_features": feature_result.global_features,
        },
        "selected_regime": selection_result.selected.regime if selection_result else ("serial" if partition_policy == "serial" else "parallel"),
        "partition_policy": partition_plan.policy,
        "worker_count": selected_workers,
        "chunk_count": len(partition_plan.chunks),
        "planned_chunk_boundaries": [
            {
                "chunk_id": chunk.chunk_id,
                "start": chunk.start,
                "duration": chunk.duration,
                "estimated_cost": chunk.estimated_cost,
                "rationale": chunk.rationale,
            }
            for chunk in partition_plan.chunks
        ],
        "planning_rationale": partition_plan.rationale,
        "predicted_chunk_costs": (
            list(selection_result.selected.estimated_chunk_costs)
            if selection_result
            else [chunk.estimated_cost for chunk in partition_plan.chunks]
        ),
        "actual_chunk_runtime": execution["results"],
        "overheads": {
            "probe": probe_time,
            "feature": feature_result.extraction_time,
            "serial_sampling": serial_sampling_time,
            "rate_profile": [(round(p, 6), round(r, 6)) for p, r in rate_profile] if rate_profile else None,
            "scheduler": scheduler_time,
            "partition": partition_plan.planning_time,
            "dispatch": execution["dispatch_time"],
            "merge": execution["merge_time"],
            "quality_evaluation": quality_eval_time,
        },
        "decision_cost": decision_cost,
        "runtime": {
            "serial_sample_time": serial_sample_time,
            "serial_sample_positions": serial_sample_positions,
            "serial_sample_times": serial_sample_times,
            "serial_sampled_duration": serial_sample_seconds,
            "projected_serial_time": projected_serial_time,
            "serial_baseline_time": serial_baseline_time,
            "serial_baseline_source": serial_baseline_source,
            "serial_reference_output_path": serial_reference_output_path or serial_baseline_output,
            "predicted_total_time": predicted_total,
            "actual_total_time": actual_total_time,
            "compute_time": compute_time,
            "e2e_time": e2e_time,
            "timing_policy": "compute_time: dispatch+processing+merge (symmetric); e2e_time: wall-clock including all overheads",
            "prediction_signed_error": prediction_signed_error,
            "prediction_error": prediction_error,
            "prediction_relative_error": prediction_relative_error,
        },
        "performance": {
            "throughput": throughput,
            "speedup_vs_serial": speedup,
            "speedup_vs_serial_e2e": speedup_e2e,
            "efficiency": efficiency,
            "chunk_imbalance_ratio": execution["straggler_ratio"],
            "straggler_ratio": execution["straggler_ratio"],
        },
        "quality": quality_metrics,
        "selection": (
            {
                "selected": asdict(selection_result.selected),
                "candidates": [asdict(c) for c in selection_result.candidates],
                "selection_rationale": selection_result.selection_rationale,
                "estimated_serial_time": selection_result.estimated_serial_time,
            }
            if selection_result
            else None
        ),
        "provenance": {
            "requested_partition_policy": requested_partition_policy,
            "selected_partition_policy": partition_plan.policy,
            "quality_reference_label": quality_reference_label,
            "quality_reference_path": quality_reference_path,
            "speedup_reference": "measured_serial_baseline" if serial_baseline_time is not None else None,
            "projected_serial_used_for_speedup": False,
            "scheduler_underpredicted": prediction_signed_error is not None and prediction_signed_error < 0,
            "selector_enabled": scheduler_enabled,
            "ml_estimator_enabled": estimator is not None,
            "reused_serial_reference_on_fallback": reused_serial_reference,
        },
    }
    record["segment_records"] = _segment_records(record, feature_result, partition_plan)

    if not keep_temp:
        shutil.rmtree(temp_root, ignore_errors=True)
    return record


def write_record(record: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
