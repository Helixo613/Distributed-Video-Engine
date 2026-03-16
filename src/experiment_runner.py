#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from cost_estimator import LinearCostEstimator
from metrics_logger import MetricsLogger
from pipeline import run_processing_pipeline


BASELINE_PRESETS = {
    "serial": {"partition_policy": "serial", "scheduler_enabled": False},
    "static-equal": {"partition_policy": "equal-duration", "scheduler_enabled": False},
    "adaptive-fixed": {"partition_policy": "heuristic-adaptive", "scheduler_enabled": False},
    "adaptive-scheduled": {"partition_policy": "heuristic-adaptive", "scheduler_enabled": True},
    "ml-adaptive-scheduled": {"partition_policy": "ml-adaptive", "scheduler_enabled": True},
}


def _parse_int_list(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _parse_float_list(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def _load_estimator(model_path: str | None) -> LinearCostEstimator | None:
    if not model_path:
        return None
    return LinearCostEstimator.load(model_path)


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
    parser.add_argument("--workers", default="1,2,4,6,8,12,16", help="Worker counts for sweeps")
    parser.add_argument("--chunk-multipliers", default="1.0,1.5,2.0", help="Chunk count multipliers")
    parser.add_argument("--fixed-workers", type=int, default=4, help="Worker count for non-scheduled baselines")
    parser.add_argument("--fixed-chunks", type=int, default=8, help="Chunk count for non-scheduled baselines")
    parser.add_argument("--trials", type=int, default=1, help="Repeat count per configuration")
    parser.add_argument("--filter", default="unsharp=5:5:1.5:5:5:0.5", help="FFmpeg filter chain")
    parser.add_argument("--full-serial", action="store_true", help="Run a full serial baseline instead of projection only")
    parser.add_argument("--enable-vmaf", action="store_true", help="Attempt VMAF calculation if FFmpeg supports it")
    parser.add_argument("--enable-encode-proxy", action="store_true", help="Enable sampled low-resolution encode-time proxy")
    parser.add_argument("--model", help="Optional linear model JSON for ML-adaptive partitioning")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = MetricsLogger(str(output_dir))
    estimator = _load_estimator(args.model)
    baselines = [item.strip() for item in args.baselines.split(",") if item.strip()]
    worker_candidates = _parse_int_list(args.workers)
    chunk_multipliers = _parse_float_list(args.chunk_multipliers)

    manifest = {
        "created_at": time.time(),
        "videos": args.videos,
        "baselines": baselines,
        "worker_candidates": worker_candidates,
        "chunk_multipliers": chunk_multipliers,
        "filter_chain": args.filter,
        "trials": args.trials,
        "full_serial": bool(args.full_serial),
        "model": args.model,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    run_index = 0
    for video in args.videos:
        for baseline in baselines:
            preset = BASELINE_PRESETS.get(baseline)
            if preset is None:
                raise ValueError(f"Unknown baseline preset: {baseline}")
            if baseline == "ml-adaptive-scheduled" and estimator is None:
                continue

            for trial in range(1, args.trials + 1):
                run_index += 1
                video_stem = Path(video).stem
                output_path = output_dir / f"{video_stem}_{baseline}_trial{trial}.mp4"
                record = run_processing_pipeline(
                    input_path=video,
                    output_path=str(output_path),
                    filter_chain=args.filter,
                    partition_policy=preset["partition_policy"],
                    worker_count=args.fixed_workers,
                    chunk_count=args.fixed_chunks,
                    scheduler_enabled=preset["scheduler_enabled"],
                    scheduler_workers=worker_candidates,
                    scheduler_chunk_multipliers=chunk_multipliers,
                    enable_full_serial_baseline=args.full_serial,
                    enable_encode_time_proxy=args.enable_encode_proxy,
                    enable_quality_metrics=True,
                    enable_vmaf=args.enable_vmaf,
                    estimator=estimator,
                    temp_dir=str(output_dir / f"tmp_run_{run_index}"),
                )
                record["experiment"] = {
                    "baseline": baseline,
                    "trial": trial,
                    "run_index": run_index,
                }
                logger.log_run(record)
                logger.log_segments(record.get("segment_records", []))


if __name__ == "__main__":
    main()
