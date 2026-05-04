#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from cost_estimator import LinearCostEstimator
from ffmpeg_utils import analyze_video, benchmark_serial_profile, execution_backend_info, resolve_execution_backend
from metrics_logger import MetricsLogger
from pipeline import run_processing_pipeline


BASELINE_PRESETS = {
    "serial": {"partition_policy": "serial", "scheduler_enabled": False},
    "static-equal": {"partition_policy": "equal-duration", "scheduler_enabled": False},
    "adaptive-fixed": {"partition_policy": "heuristic-adaptive", "scheduler_enabled": False},
    "adaptive-scheduled": {"partition_policy": "heuristic-adaptive", "scheduler_enabled": True},
    "ml-adaptive-scheduled": {"partition_policy": "ml-adaptive", "scheduler_enabled": True},
}

WORKLOAD_PRESETS = {
    "light": "eq=contrast=1.02:brightness=0.01:saturation=1.03",
    "medium": "unsharp=5:5:1.5:5:5:0.5",
    "heavy": "hqdn3d=1.5:1.5:6:6,gblur=sigma=1.2,unsharp=7:7:1.8:7:7:0.8",
}

# AI preprocessing pipeline descriptions for each workload class.
# These map the concrete FFmpeg filter chains to their role in a media
# preprocessing pipeline that prepares video for downstream AI/ML inference.
WORKLOAD_PIPELINE_DESCRIPTIONS = {
    "light": {
        "pipeline_label": "inference-normalization",
        "description": (
            "Lightweight color/brightness normalization typical of media ingestion "
            "pipelines that prepare video for downstream ML inference (e.g., object "
            "detection, scene classification). Minimal per-frame cost; overhead-dominated."
        ),
    },
    "medium": {
        "pipeline_label": "vision-enhancement",
        "description": (
            "Sharpening and detail-enhancement preprocessing for vision analytics "
            "pipelines (e.g., feature extraction, action recognition). Moderate per-frame "
            "cost with meaningful compute-to-overhead ratio."
        ),
    },
    "heavy": {
        "pipeline_label": "robust-preprocessing",
        "description": (
            "Multi-stage denoise + blur + sharpen chain representative of robust "
            "preprocessing for noisy or low-quality media before AI model ingestion "
            "(e.g., surveillance analytics, medical video preprocessing, multimodal "
            "embedding pipelines). High per-frame cost; compute-dominated."
        ),
    },
}


def _parse_int_list(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _parse_float_list(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def _load_estimator(model_path: str | None) -> LinearCostEstimator | None:
    if not model_path:
        return None
    return LinearCostEstimator.load(model_path)


def _load_benchmark_metadata(manifest_path: str | None) -> dict[str, dict]:
    if not manifest_path:
        return {}
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    clips = payload.get("clips", [])
    metadata: dict[str, dict] = {}
    for clip in clips:
        clip_path = str(Path(clip["path"]).resolve())
        metadata[clip_path] = clip
    return metadata


def _reset_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("runs.csv", "runs.jsonl", "segments.jsonl", "manifest.json", "summary.json", "summary.csv"):
        target = output_dir / pattern
        if target.exists():
            target.unlink()
    for temp_dir in output_dir.glob("tmp_run_*"):
        shutil.rmtree(temp_dir, ignore_errors=True)
    for artifact in output_dir.iterdir():
        if artifact.name == "inputs":
            continue
        if artifact.is_file() and artifact.suffix in {".mp4", ".json", ".jsonl", ".csv"}:
            artifact.unlink()


def _attach_experiment_fields(
    record: dict,
    baseline: str,
    trial: int,
    run_index: int,
    workload_class: str,
    filter_chain: str,
    clip_metadata: dict | None = None,
) -> dict:
    clip_metadata = clip_metadata or {}
    run_id = f"{record['video_id']}::{workload_class}::{baseline}::trial{trial}"
    record["experiment"] = {
        "run_id": run_id,
        "baseline": baseline,
        "trial": trial,
        "run_index": run_index,
        "workload_class": workload_class,
        "filter_chain": filter_chain,
        "content_class": clip_metadata.get("content_class"),
        "source_kind": clip_metadata.get("source_kind"),
        "resolution_label": clip_metadata.get("resolution_label"),
        "duration_label": clip_metadata.get("duration_label"),
        "clip_id": clip_metadata.get("clip_id"),
    }
    for segment in record.get("segment_records", []):
        segment["run_id"] = run_id
        segment["experiment_baseline"] = baseline
        segment["experiment_trial"] = trial
        segment["experiment_run_index"] = run_index
        segment["workload_class"] = workload_class
        segment["content_class"] = clip_metadata.get("content_class")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reproducible adaptive scheduling experiments for FFmpeg-based parallel video processing."
    )
    parser.add_argument("videos", nargs="+", help="Input video paths")
    parser.add_argument("--output-dir", default="experiments/latest", help="Directory for CSV/JSON outputs")
    parser.add_argument(
        "--baselines",
        default="serial,static-equal,adaptive-fixed,adaptive-scheduled",
        help="Comma-separated baseline/ablation presets",
    )
    parser.add_argument("--workers", default="1,2,4,6,8,12,16", help="Worker counts for scheduler sweeps")
    parser.add_argument("--chunk-multipliers", default="1.0,1.5,2.0", help="Chunk count multipliers")
    parser.add_argument("--fixed-workers", type=int, default=4, help="Worker count for non-scheduled baselines")
    parser.add_argument("--fixed-chunks", type=int, default=None, help="Chunk count for non-scheduled baselines (defaults to --fixed-workers)")
    parser.add_argument("--trials", type=int, default=3, help="Repeat count per configuration")
    parser.add_argument("--workloads", default="medium", help="Comma-separated workload presets: light, medium, heavy")
    parser.add_argument("--filter", help="Override workload presets with a single custom FFmpeg filter chain")
    parser.add_argument("--benchmark-manifest", help="Optional benchmark manifest JSON for workload/content provenance")
    parser.add_argument("--enable-vmaf", action="store_true", help="Attempt VMAF calculation if FFmpeg supports it")
    parser.add_argument("--enable-encode-proxy", action="store_true", help="Enable sampled low-resolution encode-time proxy")
    parser.add_argument("--model", help="Optional linear model JSON for ML-adaptive partitioning")
    parser.add_argument(
        "--execution-backend",
        default="auto",
        choices=["auto", "cpu", "cuda", "gpu", "nvenc"],
        help="FFmpeg execution backend. auto uses NVENC when available, otherwise CPU.",
    )
    args = parser.parse_args()
    resolved_backend = resolve_execution_backend(args.execution_backend)
    backend_info = execution_backend_info(args.execution_backend)

    output_dir = Path(args.output_dir)
    _reset_output_dir(output_dir)

    # Default chunk count to match worker count to avoid unnecessary queuing overhead
    fixed_chunks = args.fixed_chunks if args.fixed_chunks is not None else args.fixed_workers

    logger = MetricsLogger(str(output_dir))
    estimator = _load_estimator(args.model)
    benchmark_metadata = _load_benchmark_metadata(args.benchmark_manifest)
    baselines = [item.strip() for item in args.baselines.split(",") if item.strip()]
    worker_candidates = _parse_int_list(args.workers)
    chunk_multipliers = _parse_float_list(args.chunk_multipliers)
    if args.filter:
        workloads = [("custom", args.filter)]
    else:
        workload_names = [item.strip() for item in args.workloads.split(",") if item.strip()]
        unknown = [name for name in workload_names if name not in WORKLOAD_PRESETS]
        if unknown:
            raise ValueError(f"Unknown workload presets: {unknown}")
        workloads = [(name, WORKLOAD_PRESETS[name]) for name in workload_names]

    manifest = {
        "schema_version": "research-prototype.v3",
        "created_at": time.time(),
        "videos": args.videos,
        "workloads": [name for name, _ in workloads],
        "baselines": baselines,
        "worker_candidates": worker_candidates,
        "chunk_multipliers": chunk_multipliers,
        "filters": {name: filter_chain for name, filter_chain in workloads},
        "trials": args.trials,
        "fixed_workers": args.fixed_workers,
        "fixed_chunks": fixed_chunks,
        "measured_serial_reference": True,
        "benchmark_manifest": args.benchmark_manifest,
        "model": args.model,
        "execution_backend": backend_info,
        "timing_policy": "speedup computed from compute_time (dispatch+processing+merge), symmetric across serial and parallel",
        "preprocessing_pipelines": {
            name: WORKLOAD_PIPELINE_DESCRIPTIONS[name]
            for name in [n for n, _ in workloads]
            if name in WORKLOAD_PIPELINE_DESCRIPTIONS
        },
        "framing": (
            "Workloads represent media preprocessing pipelines at varying compute intensity, "
            "typical of cloud-based AI ingestion systems that normalize, enhance, or denoise "
            "video before downstream ML inference. The execution selector optimizes resource "
            "allocation (serial vs. parallel, worker count, chunk strategy) based on an "
            "overhead-aware cost model calibrated to the preprocessing workload and input content."
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    run_index = 0
    non_serial_baselines = [baseline for baseline in baselines if baseline != "serial"]
    for video in args.videos:
        clip_metadata = benchmark_metadata.get(str(Path(video).resolve()), {})
        for workload_name, filter_chain in workloads:
            for trial in range(1, args.trials + 1):
                video_stem = Path(video).stem
                serial_output_path = output_dir / f"{video_stem}_{workload_name}_serial_trial{trial}.mp4"
                serial_record = run_processing_pipeline(
                    input_path=video,
                    output_path=str(serial_output_path),
                    filter_chain=filter_chain,
                    partition_policy="serial",
                    worker_count=1,
                    chunk_count=1,
                    scheduler_enabled=False,
                    enable_full_serial_baseline=False,
                    enable_encode_time_proxy=args.enable_encode_proxy,
                    enable_quality_metrics=True,
                    enable_vmaf=args.enable_vmaf,
                    estimator=None,
                    temp_dir=str(output_dir / f"tmp_run_serial_{workload_name}_{trial}_{video_stem}"),
                    execution_backend=resolved_backend,
                )
                serial_reference_time = serial_record["runtime"]["serial_baseline_time"]
                serial_reference_e2e_time = serial_record["runtime"]["e2e_time"]
                serial_reference_output = str(serial_output_path)

                # Rate profiling: measure encode rate at multiple positions for the
                # multi-policy scheduler.  Done once per (video, workload, trial) and
                # reused across all non-serial baselines to avoid redundant profiling.
                rate_profile = None
                any_scheduled = any(
                    BASELINE_PRESETS.get(b, {}).get("scheduler_enabled", False)
                    for b in non_serial_baselines
                )
                if any_scheduled:
                    video_meta = analyze_video(video)
                    profile_sample_seconds = min(1.0, video_meta.duration)
                    profile_temp = output_dir / f"tmp_profile_{workload_name}_{trial}_{video_stem}"
                    profile_temp.mkdir(parents=True, exist_ok=True)
                    rate_prof = benchmark_serial_profile(
                        input_path=video,
                        temp_dir=str(profile_temp),
                        filter_chain=filter_chain,
                        duration=video_meta.duration,
                        sample_seconds=profile_sample_seconds,
                        sample_fractions=[0.0, 0.25, 0.5, 0.75, 0.95],
                        execution_backend=resolved_backend,
                    )
                    if rate_prof["sample_seconds"] > 0 and rate_prof["positions"] and rate_prof["samples"]:
                        rate_profile = [
                            (pos, t / rate_prof["sample_seconds"])
                            for pos, t in zip(rate_prof["positions"], rate_prof["samples"])
                        ]

                if "serial" in baselines:
                    run_index += 1
                    record = _attach_experiment_fields(
                        serial_record,
                        "serial",
                        trial,
                        run_index,
                        workload_name,
                        filter_chain,
                        clip_metadata,
                    )
                    logger.log_run(record)
                    logger.log_segments(record.get("segment_records", []))

                for baseline in non_serial_baselines:
                    preset = BASELINE_PRESETS.get(baseline)
                    if preset is None:
                        raise ValueError(f"Unknown baseline preset: {baseline}")
                    if baseline == "ml-adaptive-scheduled" and estimator is None:
                        continue

                    run_index += 1
                    output_path = output_dir / f"{video_stem}_{workload_name}_{baseline}_trial{trial}.mp4"
                    record = run_processing_pipeline(
                        input_path=video,
                        output_path=str(output_path),
                        filter_chain=filter_chain,
                        partition_policy=preset["partition_policy"],
                        worker_count=args.fixed_workers,
                        chunk_count=fixed_chunks,
                        scheduler_enabled=preset["scheduler_enabled"],
                        scheduler_workers=worker_candidates,
                        scheduler_chunk_multipliers=chunk_multipliers,
                        enable_full_serial_baseline=False,
                        enable_encode_time_proxy=args.enable_encode_proxy,
                        enable_quality_metrics=True,
                        enable_vmaf=args.enable_vmaf,
                        estimator=estimator,
                        temp_dir=str(output_dir / f"tmp_run_{run_index}"),
                        serial_reference_time=serial_reference_time,
                        serial_reference_e2e_time=serial_reference_e2e_time,
                        serial_reference_output_path=serial_reference_output,
                        reuse_serial_reference_on_fallback=True,
                        rate_profile=rate_profile if preset["scheduler_enabled"] else None,
                        execution_backend=resolved_backend,
                    )
                    record = _attach_experiment_fields(
                        record,
                        baseline,
                        trial,
                        run_index,
                        workload_name,
                        filter_chain,
                        clip_metadata,
                    )
                    logger.log_run(record)
                    logger.log_segments(record.get("segment_records", []))


if __name__ == "__main__":
    main()
