from __future__ import annotations

import json
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
    benchmark_serial_sample,
    ensure_dir,
    merge_chunks,
    process_chunk,
    run_serial_baseline,
)
from scheduler import search_best_configuration, simulate_makespan
from video_types import ChunkResult, PartitionPlan


ProgressCallback = Optional[Callable[[int], None]]


def execute_partition_plan(
    partition_plan: PartitionPlan,
    output_path: str,
    workers: int,
    filter_chain: str,
    temp_dir: str,
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
            executor.submit(process_chunk, chunk, filter_chain): chunk for chunk in partition_plan.chunks
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
) -> dict:
    """Run the research pipeline end-to-end and emit a structured experiment record."""
    temp_root = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="dve_run_"))
    ensure_dir(temp_root)

    started_at = time.time()
    probe_start = time.perf_counter()
    metadata = analyze_video(input_path)
    probe_time = time.perf_counter() - probe_start

    feature_result = extract_video_features(
        input_path=input_path,
        enable_encode_time_proxy=enable_encode_time_proxy,
    )

    serial_sample_seconds = min(2.0, metadata.duration)
    serial_sample_time = benchmark_serial_sample(
        input_path=input_path,
        temp_dir=str(temp_root),
        filter_chain=filter_chain,
        sample_seconds=serial_sample_seconds,
    )
    projected_serial_time = (metadata.duration / max(serial_sample_seconds, 1e-6)) * serial_sample_time

    measured_overheads = {
        "probe": probe_time,
        "feature": feature_result.extraction_time,
    }

    selected_workers = worker_count
    selected_chunks = chunk_count or max(1, worker_count)
    scheduler_decision = None
    scheduler_time = 0.0
    if scheduler_enabled:
        scheduler_start = time.perf_counter()
        scheduler_decision = search_best_configuration(
            input_path=input_path,
            metadata=metadata,
            feature_result=feature_result,
            filter_chain=filter_chain,
            temp_dir=str(temp_root),
            workers=scheduler_workers or [1, 2, 4, 6, 8, 12, 16],
            chunk_multipliers=scheduler_chunk_multipliers or [1.0, 1.5, 2.0],
            partition_policy=partition_policy,
            serial_sample_time=serial_sample_time,
            measured_overheads=measured_overheads,
            estimator=estimator,
        )
        scheduler_time = time.perf_counter() - scheduler_start
        selected_workers = scheduler_decision.worker_count
        selected_chunks = scheduler_decision.chunk_count

    partition_plan = build_partition_plan(
        input_path=input_path,
        metadata=metadata,
        temp_dir=str(temp_root),
        policy=partition_policy,
        num_chunks=selected_chunks if partition_policy != "serial" else 1,
        feature_result=feature_result,
        estimated_total_runtime=scheduler_decision.estimated_serial_time if scheduler_decision else projected_serial_time,
        estimator=estimator,
    )

    execution_start = time.perf_counter()
    execution = execute_partition_plan(
        partition_plan=partition_plan,
        output_path=output_path,
        workers=selected_workers,
        filter_chain=filter_chain,
        temp_dir=str(temp_root),
        progress_callback=progress_callback,
    )
    total_runtime = time.perf_counter() - execution_start

    serial_baseline_time = None
    if enable_full_serial_baseline:
        serial_baseline_output = str(temp_root / "serial_baseline.mp4")
        serial_baseline_time = run_serial_baseline(input_path, serial_baseline_output, filter_chain)

    quality_metrics = {}
    if enable_quality_metrics:
        quality_metrics = evaluate_output(
            input_path=input_path,
            output_path=output_path,
            sample_seconds=min(8.0, metadata.duration),
            enable_vmaf=enable_vmaf,
        )

    baseline_time = serial_baseline_time or projected_serial_time
    speedup = baseline_time / total_runtime if total_runtime > 0 else None
    efficiency = (speedup / selected_workers) if speedup is not None and selected_workers > 0 else None
    throughput = metadata.duration / total_runtime if total_runtime > 0 else None
    predicted_total = scheduler_decision.predicted_total_time if scheduler_decision else (
        probe_time
        + feature_result.extraction_time
        + partition_plan.planning_time
        + execution["dispatch_time"]
        + simulate_makespan([chunk.get("elapsed", 0.0) for chunk in execution["results"]], selected_workers)
        + execution["merge_time"]
    )

    record = {
        "started_at": started_at,
        "input_file": input_path,
        "video_id": Path(input_path).stem,
        "metadata": asdict(metadata),
        "feature_summary": {
            "sample_fps": feature_result.sample_fps,
            "sample_width": feature_result.sample_width,
            "sample_height": feature_result.sample_height,
            "analysis_window_seconds": feature_result.analysis_window_seconds,
            "total_sample_frames": feature_result.total_sample_frames,
            "global_features": feature_result.global_features,
        },
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
        "predicted_chunk_costs": scheduler_decision.estimated_chunk_costs if scheduler_decision else [
            chunk.estimated_cost for chunk in partition_plan.chunks
        ],
        "actual_chunk_runtime": execution["results"],
        "overheads": {
            "probe": probe_time,
            "feature": feature_result.extraction_time,
            "scheduler": scheduler_time,
            "partition": partition_plan.planning_time,
            "dispatch": execution["dispatch_time"],
            "merge": execution["merge_time"],
        },
        "runtime": {
            "serial_sample_time": serial_sample_time,
            "projected_serial_time": projected_serial_time,
            "serial_baseline_time": serial_baseline_time,
            "predicted_total_time": predicted_total,
            "actual_total_time": total_runtime,
            "prediction_error": abs(predicted_total - total_runtime),
        },
        "performance": {
            "throughput": throughput,
            "speedup_vs_serial": speedup,
            "efficiency": efficiency,
            "chunk_imbalance_ratio": execution["straggler_ratio"],
            "straggler_ratio": execution["straggler_ratio"],
        },
        "quality": quality_metrics,
        "scheduler": asdict(scheduler_decision) if scheduler_decision else None,
    }

    segment_records = []
    segment_lookup = {segment.segment_id: segment for segment in feature_result.segment_features}
    for chunk_record in execution["results"]:
        chunk_id = chunk_record["chunk_id"]
        source_ids = partition_plan.chunks[chunk_id].source_segment_ids
        for segment_id in source_ids:
            segment = segment_lookup.get(segment_id)
            if segment is None:
                continue
            payload = asdict(segment)
            payload.update(
                {
                    "input_file": input_path,
                    "partition_policy": partition_plan.policy,
                    "worker_count": selected_workers,
                    "chunk_id": chunk_id,
                    "actual_chunk_runtime": chunk_record["elapsed"],
                }
            )
            segment_records.append(payload)
    record["segment_records"] = segment_records

    if temp_dir is None:
        shutil.rmtree(temp_root, ignore_errors=True)
    return record


def write_record(record: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
