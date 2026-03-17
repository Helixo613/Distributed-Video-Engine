#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

from ffmpeg_utils import analyze_video


DEFAULT_BASELINES = ["serial", "static-equal", "adaptive-fixed", "adaptive-scheduled"]


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _parse_bool(value: str | None) -> bool | None:
    if value in (None, ""):
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _approx_equal(left: float | None, right: float | None, tolerance: float) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _expected_output_path(output_dir: Path, row: dict[str, str]) -> Path:
    video_stem = Path(row["input_file"]).stem
    baseline = row["experiment.baseline"]
    trial = row["experiment.trial"]
    workload_class = row.get("experiment.workload_class")
    if workload_class:
        return output_dir / f"{video_stem}_{workload_class}_{baseline}_trial{trial}.mp4"
    return output_dir / f"{video_stem}_{baseline}_trial{trial}.mp4"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify research experiment outputs for baseline correctness, quality provenance, and schema consistency."
    )
    parser.add_argument("experiment_dir", help="Directory containing runs.csv, runs.jsonl, and segments.jsonl")
    parser.add_argument(
        "--expected-baselines",
        default=",".join(DEFAULT_BASELINES),
        help="Comma-separated baselines that must appear in the run table",
    )
    parser.add_argument("--min-videos", type=int, default=2, help="Minimum number of distinct input videos expected")
    parser.add_argument(
        "--duration-delta-threshold",
        type=float,
        default=0.5,
        help="Maximum allowed absolute duration delta in seconds before failure",
    )
    parser.add_argument(
        "--fps-delta-threshold",
        type=float,
        default=2.0,
        help="Maximum allowed fps delta between logged output and reference before failure",
    )
    parser.add_argument(
        "--time-tolerance",
        type=float,
        default=1e-3,
        help="Absolute tolerance for runtime equality checks",
    )
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    runs_csv = experiment_dir / "runs.csv"
    runs_jsonl = experiment_dir / "runs.jsonl"
    segments_jsonl = experiment_dir / "segments.jsonl"

    failures: list[str] = []
    warnings: list[str] = []

    for path in (runs_csv, runs_jsonl, segments_jsonl):
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)

    rows = list(csv.DictReader(runs_csv.open(newline="", encoding="utf-8")))
    run_records = _load_jsonl(runs_jsonl)
    segment_records = _load_jsonl(segments_jsonl)

    if len(rows) != len(run_records):
        failures.append(f"runs.csv row count {len(rows)} does not match runs.jsonl record count {len(run_records)}")
    if not rows:
        failures.append("runs.csv is empty")

    expected_baselines = {item.strip() for item in args.expected_baselines.split(",") if item.strip()}
    present_baselines = {row["experiment.baseline"] for row in rows}
    missing_baselines = expected_baselines - present_baselines
    if missing_baselines:
        failures.append(f"Missing expected baselines: {sorted(missing_baselines)}")

    present_videos = {row["input_file"] for row in rows}
    if len(present_videos) < args.min_videos:
        failures.append(f"Expected at least {args.min_videos} videos, found {len(present_videos)}")

    scheduled_prediction_errors: list[float] = []
    duration_deltas: list[float] = []
    output_files_seen: set[Path] = set()

    for row in rows:
        baseline = row["experiment.baseline"]
        actual_total = _parse_float(row.get("runtime.actual_total_time"))
        serial_baseline = _parse_float(row.get("runtime.serial_baseline_time"))
        speedup = _parse_float(row.get("performance.speedup_vs_serial"))
        efficiency = _parse_float(row.get("performance.efficiency"))
        projected_used = _parse_bool(row.get("provenance.projected_serial_used_for_speedup"))
        quality_reference_label = row.get("quality.reference_label")
        serial_baseline_source = row.get("runtime.serial_baseline_source")
        duration_delta = abs(_parse_float(row.get("quality.duration_delta")) or 0.0)
        duration_deltas.append(duration_delta)

        if actual_total is None or actual_total <= 0:
            failures.append(f"{baseline} row for {row['input_file']} has invalid actual runtime")
            continue
        if serial_baseline is None or serial_baseline <= 0:
            failures.append(f"{baseline} row for {row['input_file']} is missing measured serial baseline time")
        if projected_used is not False:
            failures.append(f"{baseline} row for {row['input_file']} reports projected serial time used for speedup")
        if duration_delta > args.duration_delta_threshold:
            failures.append(
                f"{baseline} row for {row['input_file']} exceeds duration delta threshold: {duration_delta:.3f}s"
            )

        expected_speedup = (serial_baseline / actual_total) if serial_baseline is not None else None
        if speedup is None or expected_speedup is None or not _approx_equal(speedup, expected_speedup, 1e-6):
            failures.append(f"{baseline} row for {row['input_file']} has inconsistent speedup calculation")

        worker_count = int(row["worker_count"])
        if speedup is not None and efficiency is not None:
            expected_efficiency = speedup / max(1, worker_count)
            if not _approx_equal(efficiency, expected_efficiency, 1e-6):
                failures.append(f"{baseline} row for {row['input_file']} has inconsistent efficiency calculation")

        if baseline == "serial":
            if not _approx_equal(actual_total, serial_baseline, args.time_tolerance):
                failures.append(f"Serial row for {row['input_file']} does not match its own baseline time")
            if speedup is None or not _approx_equal(speedup, 1.0, 1e-6):
                failures.append(f"Serial row for {row['input_file']} does not report unit speedup")
            if quality_reference_label != "input":
                failures.append(f"Serial row for {row['input_file']} should use input as quality reference")
            if serial_baseline_source != "measured_serial_run":
                failures.append(f"Serial row for {row['input_file']} should record measured_serial_run provenance")
            if row.get("runtime.projected_serial_time") not in ("", None):
                failures.append(f"Serial row for {row['input_file']} should not log projected serial runtime")
        else:
            if quality_reference_label != "serial_baseline":
                failures.append(f"{baseline} row for {row['input_file']} should use serial_baseline as quality reference")
            if serial_baseline_source not in {"external_reference", "measured_full_serial"}:
                failures.append(f"{baseline} row for {row['input_file']} has unexpected baseline source {serial_baseline_source}")

        if row.get("provenance.selector_enabled") == "True":
            predicted_total = _parse_float(row.get("runtime.predicted_total_time"))
            signed_error = _parse_float(row.get("runtime.prediction_signed_error"))
            relative_error = _parse_float(row.get("runtime.prediction_relative_error"))
            underpredicted = _parse_bool(row.get("provenance.scheduler_underpredicted"))
            if predicted_total is None or signed_error is None or relative_error is None:
                failures.append(f"Scheduled row for {row['input_file']} is missing prediction error fields")
            else:
                expected_signed_error = predicted_total - actual_total
                if not _approx_equal(signed_error, expected_signed_error, 1e-6):
                    failures.append(f"Scheduled row for {row['input_file']} has inconsistent signed prediction error")
                expected_relative = abs(expected_signed_error) / actual_total
                if not _approx_equal(relative_error, expected_relative, 1e-6):
                    failures.append(f"Scheduled row for {row['input_file']} has inconsistent relative prediction error")
                scheduled_prediction_errors.append(relative_error)
                if underpredicted != (signed_error < 0):
                    failures.append(f"Scheduled row for {row['input_file']} has inconsistent underprediction flag")

        output_fps = _parse_float(row.get("quality.output_fps"))
        reference_fps = _parse_float(row.get("quality.reference_fps"))
        if output_fps is None or reference_fps is None or output_fps <= 0 or reference_fps <= 0:
            failures.append(f"{baseline} row for {row['input_file']} has invalid fps metadata")
        elif abs(output_fps - reference_fps) > args.fps_delta_threshold:
            failures.append(f"{baseline} row for {row['input_file']} exceeds fps delta threshold")

        if row.get("quality.resolution_match") != "True":
            failures.append(f"{baseline} row for {row['input_file']} reports mismatched resolution")

        expected_output = _expected_output_path(experiment_dir, row)
        output_files_seen.add(expected_output)
        if not expected_output.exists():
            failures.append(f"Missing expected output file: {expected_output}")
            continue

        output_meta = analyze_video(str(expected_output))
        logged_duration = _parse_float(row.get("quality.output_duration"))
        logged_fps = output_fps
        if logged_duration is not None and not _approx_equal(output_meta.duration, logged_duration, 1e-3):
            failures.append(f"{baseline} output file {expected_output.name} duration disagrees with logged quality metadata")
        if logged_fps is not None and abs(output_meta.fps - logged_fps) > 1e-3:
            failures.append(f"{baseline} output file {expected_output.name} fps disagrees with logged quality metadata")

    stale_outputs = sorted(
        str(path.name)
        for path in experiment_dir.glob("*.mp4")
        if path not in output_files_seen
    )
    if stale_outputs:
        warnings.append(f"Unreferenced output videos found: {stale_outputs}")

    if not segment_records:
        failures.append("segments.jsonl is empty")
    else:
        required_segment_fields = {
            "input_file",
            "partition_policy",
            "worker_count",
            "chunk_count",
            "chunk_id",
            "actual_chunk_runtime",
            "experiment_baseline",
            "experiment_trial",
            "schema_version",
            "quality_reference_label",
        }
        for field in required_segment_fields:
            if field not in segment_records[0]:
                failures.append(f"segments.jsonl is missing field: {field}")

    print(f"Runs checked: {len(rows)}")
    print(f"Videos checked: {len(present_videos)}")
    print(f"Baselines present: {sorted(present_baselines)}")
    if scheduled_prediction_errors:
        print(
            "Adaptive-scheduled prediction error: "
            f"mean={_mean(scheduled_prediction_errors):.4f}, max={max(scheduled_prediction_errors):.4f}"
        )
    if duration_deltas:
        print(
            "Absolute duration delta: "
            f"mean={_mean(duration_deltas):.4f}s, max={max(duration_deltas):.4f}s"
        )

    if warnings:
        for warning in warnings:
            print(f"WARN: {warning}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)

    print("PASS: experiment outputs verified")


if __name__ == "__main__":
    main()
