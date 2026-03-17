#!/usr/bin/env python3
"""Produce calibration-quality analysis for the media preprocessing execution selector.

Outputs a JSON report summarizing prediction accuracy, overhead contributions,
and model reliability — evidence that the execution selector for cloud/AI media
preprocessing pipelines uses a calibrated empirical runtime model rather than
hand-tuned heuristics.  Workloads span lightweight inference-normalization to
heavy multi-stage denoising, representative of preprocessing stages in AI
ingestion systems.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else float("nan")


def _stdev(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def _median(vals: list[float]) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _collect_float(rows: list[dict], key: str) -> list[float]:
    out = []
    for r in rows:
        v = r.get(key)
        if v not in ("", None):
            try:
                out.append(float(v))
            except (ValueError, TypeError):
                continue
    return out


def _prediction_stats(errors: list[float]) -> dict:
    if not errors:
        return {"n": 0}
    abs_errors = [abs(e) for e in errors]
    return {
        "n": len(errors),
        "mean_signed_error": round(_mean(errors), 6),
        "mean_absolute_error": round(_mean(abs_errors), 6),
        "median_absolute_error": round(_median(abs_errors), 6),
        "std_error": round(_stdev(errors), 6),
        "max_absolute_error": round(max(abs_errors), 6),
        "within_5pct": sum(1 for e in abs_errors if e <= 0.05),
        "within_10pct": sum(1 for e in abs_errors if e <= 0.10),
        "within_20pct": sum(1 for e in abs_errors if e <= 0.20),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibration analysis for selector cost model.")
    parser.add_argument("runs_csv", help="Path to runs.csv from experiment runner")
    parser.add_argument("--output-json", default=None, help="Output JSON path")
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.runs_csv, newline="", encoding="utf-8")))

    # Only adaptive-scheduled rows have predictions
    scheduled_rows = [r for r in rows if r.get("experiment.baseline") == "adaptive-scheduled"]
    # Separate parallel predictions (cost model does real work) from serial (trivially exact)
    parallel_scheduled = [r for r in scheduled_rows if r.get("selected_regime") == "parallel"]
    serial_scheduled = [r for r in scheduled_rows if r.get("selected_regime") == "serial"]

    # --- Section 1: Overall prediction accuracy ---
    all_pred_errors = _collect_float(scheduled_rows, "runtime.prediction_relative_error")
    overall_stats = _prediction_stats(all_pred_errors)
    # Parallel-only stats (cost model quality, excluding trivially-exact serial predictions)
    parallel_pred_errors = _collect_float(parallel_scheduled, "runtime.prediction_relative_error")
    parallel_stats = _prediction_stats(parallel_pred_errors)

    # --- Section 2: Prediction accuracy by workload class ---
    by_workload: dict[str, list[float]] = defaultdict(list)
    for r in scheduled_rows:
        err = r.get("runtime.prediction_relative_error")
        if err not in ("", None):
            by_workload[r.get("experiment.workload_class", "unknown")].append(float(err))
    workload_stats = {k: _prediction_stats(v) for k, v in sorted(by_workload.items())}

    # --- Section 3: Prediction accuracy by duration bucket ---
    by_duration: dict[str, list[float]] = defaultdict(list)
    for r in scheduled_rows:
        err = r.get("runtime.prediction_relative_error")
        dur_label = r.get("experiment.duration_label", "")
        if err not in ("", None) and dur_label:
            by_duration[dur_label].append(float(err))
    duration_stats = {k: _prediction_stats(v) for k, v in sorted(by_duration.items(), key=lambda x: x[0])}

    # --- Section 4: Prediction accuracy by content class ---
    by_content: dict[str, list[float]] = defaultdict(list)
    for r in scheduled_rows:
        err = r.get("runtime.prediction_relative_error")
        cc = r.get("experiment.content_class", "")
        if err not in ("", None) and cc:
            by_content[cc].append(float(err))
    content_stats = {k: _prediction_stats(v) for k, v in sorted(by_content.items())}

    # --- Section 5: Overhead contribution analysis ---
    # Measured actual overheads (from execution)
    measured_overhead_keys = [
        "overheads.probe",
        "overheads.feature",
        "overheads.partition",
        "overheads.dispatch",
        "overheads.merge",
        "overheads.serial_sampling",
        "overheads.rate_profile",
        "overheads.scheduler",
        "overheads.quality_evaluation",
    ]
    overhead_contributions: dict[str, dict] = {}
    for key in measured_overhead_keys:
        short_name = key.split(".")[-1]
        vals = _collect_float(scheduled_rows, key)
        if vals:
            overhead_contributions[short_name] = {
                "mean": round(_mean(vals), 6),
                "std": round(_stdev(vals), 6),
                "min": round(min(vals), 6),
                "max": round(max(vals), 6),
            }

    # Predicted overheads (from selector cost model)
    predicted_overhead_keys = [
        "selection.selected.overheads.probe",
        "selection.selected.overheads.feature",
        "selection.selected.overheads.partition",
        "selection.selected.overheads.dispatch",
        "selection.selected.overheads.merge",
        "selection.selected.overheads.overhead",
    ]
    predicted_overheads: dict[str, dict] = {}
    for key in predicted_overhead_keys:
        short_name = key.split(".")[-1]
        vals = _collect_float(scheduled_rows, key)
        if vals:
            predicted_overheads[short_name] = {
                "mean": round(_mean(vals), 6),
                "std": round(_stdev(vals), 6),
                "min": round(min(vals), 6),
                "max": round(max(vals), 6),
            }

    # Orchestration overhead as fraction of actual total time
    # Excludes quality_evaluation (post-processing, not part of pipeline decision)
    orchestration_keys = [
        "overheads.probe", "overheads.feature", "overheads.partition",
        "overheads.dispatch", "overheads.merge", "overheads.scheduler",
        "overheads.serial_sampling",
    ]
    overhead_fractions: list[float] = []
    for r in parallel_scheduled:
        total = r.get("runtime.actual_total_time")
        if total in ("", None):
            continue
        total_f = float(total)
        if total_f <= 0:
            continue
        oh_sum = 0.0
        for key in orchestration_keys:
            v = r.get(key)
            if v not in ("", None):
                try:
                    oh_sum += float(v)
                except (ValueError, TypeError):
                    continue
        overhead_fractions.append(oh_sum / total_f)

    overhead_fraction_stats = {
        "mean_overhead_fraction": round(_mean(overhead_fractions), 6) if overhead_fractions else None,
        "median_overhead_fraction": round(_median(overhead_fractions), 6) if overhead_fractions else None,
        "max_overhead_fraction": round(max(overhead_fractions), 6) if overhead_fractions else None,
    }

    # --- Section 6: Predicted vs actual runtime scatter data ---
    scatter_data: list[dict] = []
    for r in scheduled_rows:
        predicted = r.get("runtime.predicted_total_time")
        actual = r.get("runtime.actual_total_time")
        if predicted in ("", None) or actual in ("", None):
            continue
        scatter_data.append({
            "input_file": r.get("input_file", ""),
            "workload_class": r.get("experiment.workload_class", ""),
            "content_class": r.get("experiment.content_class", ""),
            "duration_label": r.get("experiment.duration_label", ""),
            "predicted": round(float(predicted), 6),
            "actual": round(float(actual), 6),
            "relative_error": round(float(r.get("runtime.prediction_relative_error", 0)), 6),
            "selected_regime": r.get("selected_regime", ""),
        })

    # --- Section 7: Selector decision summary ---
    regime_counts: dict[str, int] = defaultdict(int)
    for r in scheduled_rows:
        regime = r.get("selected_regime", "unknown")
        regime_counts[regime] += 1
    label_counts: dict[str, int] = defaultdict(int)
    for r in scheduled_rows:
        label = r.get("selection.selected.label", "unknown")
        label_counts[label] += 1

    report = {
        "calibration_report_version": "1.0",
        "description": (
            "Calibration analysis for the overhead-aware adaptive execution selector "
            "applied to media preprocessing pipelines (normalization, enhancement, "
            "denoising) in a cloud/AI ingestion context. Prediction errors are "
            "(predicted - actual) / actual, so positive = overestimate. All metrics "
            "computed from adaptive-scheduled experiment runs where the selector "
            "predicted total runtime before execution."
        ),
        "overall_prediction_accuracy": overall_stats,
        "parallel_prediction_accuracy": parallel_stats,
        "prediction_accuracy_by_workload": workload_stats,
        "prediction_accuracy_by_duration": duration_stats,
        "prediction_accuracy_by_content_class": content_stats,
        "measured_overhead_contributions": overhead_contributions,
        "predicted_overhead_terms": predicted_overheads,
        "orchestration_overhead_fraction": overhead_fraction_stats,
        "selector_decision_distribution": {
            "by_regime": dict(regime_counts),
            "by_label": dict(label_counts),
        },
        "predicted_vs_actual": scatter_data,
    }

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Print summary to stdout
    print("=== Calibration Analysis ===")
    print(f"\nOverall prediction accuracy (n={overall_stats.get('n', 0)}, including {len(serial_scheduled)} serial-fallback):")
    print(f"  Mean absolute error:   {overall_stats.get('mean_absolute_error', 'n/a')}")
    print(f"  Median absolute error: {overall_stats.get('median_absolute_error', 'n/a')}")
    print(f"  Mean signed error:     {overall_stats.get('mean_signed_error', 'n/a')}")
    n = overall_stats.get("n", 0)
    if n > 0:
        print(f"  Within 5%:  {overall_stats['within_5pct']}/{n} ({100*overall_stats['within_5pct']/n:.0f}%)")
        print(f"  Within 10%: {overall_stats['within_10pct']}/{n} ({100*overall_stats['within_10pct']/n:.0f}%)")
        print(f"  Within 20%: {overall_stats['within_20pct']}/{n} ({100*overall_stats['within_20pct']/n:.0f}%)")

    pn = parallel_stats.get("n", 0)
    if pn > 0:
        print(f"\nParallel-only prediction accuracy (n={pn}, cost model quality):")
        print(f"  Mean absolute error:   {parallel_stats.get('mean_absolute_error', 'n/a')}")
        print(f"  Median absolute error: {parallel_stats.get('median_absolute_error', 'n/a')}")
        print(f"  Mean signed error:     {parallel_stats.get('mean_signed_error', 'n/a')}")
        print(f"  Within 5%:  {parallel_stats['within_5pct']}/{pn} ({100*parallel_stats['within_5pct']/pn:.0f}%)")
        print(f"  Within 10%: {parallel_stats['within_10pct']}/{pn} ({100*parallel_stats['within_10pct']/pn:.0f}%)")
        print(f"  Within 20%: {parallel_stats['within_20pct']}/{pn} ({100*parallel_stats['within_20pct']/pn:.0f}%)")

    print("\nPrediction accuracy by workload:")
    for wl, stats in workload_stats.items():
        print(f"  {wl:8s}: MAE={stats.get('mean_absolute_error', 'n/a')}, "
              f"MedAE={stats.get('median_absolute_error', 'n/a')}, n={stats.get('n', 0)}")

    print("\nPrediction accuracy by duration:")
    for dur, stats in duration_stats.items():
        print(f"  {dur:5s}: MAE={stats.get('mean_absolute_error', 'n/a')}, "
              f"MedAE={stats.get('median_absolute_error', 'n/a')}, n={stats.get('n', 0)}")

    print("\nMeasured overhead contributions (mean seconds):")
    for name, stats in overhead_contributions.items():
        print(f"  {name:20s}: {stats['mean']:.4f}s (std={stats['std']:.4f})")

    if predicted_overheads:
        print("\nPredicted overhead terms (cost model, mean seconds):")
        for name, stats in predicted_overheads.items():
            print(f"  {name:12s}: {stats['mean']:.4f}s (std={stats['std']:.4f})")

    oh_frac = overhead_fraction_stats
    if oh_frac.get("mean_overhead_fraction") is not None:
        print(f"\nOrchestration overhead as fraction of actual time (parallel runs): "
              f"mean={oh_frac['mean_overhead_fraction']:.1%}, "
              f"median={oh_frac['median_overhead_fraction']:.1%}, "
              f"max={oh_frac['max_overhead_fraction']:.1%}")

    print("\nSelector decision distribution:")
    for regime, count in sorted(regime_counts.items()):
        print(f"  regime={regime}: {count} runs")
    for label, count in sorted(label_counts.items()):
        print(f"  label={label}: {count} runs")


if __name__ == "__main__":
    main()
