#!/usr/bin/env python3
"""Measured validation for resource-budgeted execution selection.

Runs a small representative subset of cases under different worker budgets
and compares measured runtimes against the selector's predictions.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from experiment_runner import WORKLOAD_PRESETS, WORKLOAD_PIPELINE_DESCRIPTIONS
from ffmpeg_utils import analyze_video, benchmark_serial_profile
from pipeline import run_processing_pipeline


VALIDATION_CASES = [
    {
        "input": "experiments/benchmark_suite/inputs/real_clipchamp_720p_3s.mp4",
        "workload": "light",
        "reason": "serial-favorable: selector should pick serial at every budget",
    },
    {
        "input": "experiments/benchmark_suite/inputs/real_clipchamp_720p_12s.mp4",
        "workload": "medium",
        "reason": "budget-saturating: w=4 is optimal, w=8 gives no additional benefit",
    },
    {
        "input": "experiments/benchmark_suite/inputs/real_clipchamp_1080p_30s.mp4",
        "workload": "heavy",
        "reason": "budget-scaling: benefits from increasing budget up to w=8",
    },
]

WORKER_BUDGETS = [2, 4, 8, None]  # None = unconstrained
TRIALS = 3


def main() -> None:
    output_dir = Path("experiments/budget_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []

    for case in VALIDATION_CASES:
        input_path = case["input"]
        wl_name = case["workload"]
        filter_chain = WORKLOAD_PRESETS[wl_name]
        video_stem = Path(input_path).stem

        print(f"\n=== {video_stem}::{wl_name} ({case['reason']}) ===")

        # First run serial baseline (once per case, average over trials)
        serial_times = []
        for trial in range(1, TRIALS + 1):
            serial_output = output_dir / f"{video_stem}_{wl_name}_serial_trial{trial}.mp4"
            serial_record = run_processing_pipeline(
                input_path=input_path,
                output_path=str(serial_output),
                filter_chain=filter_chain,
                partition_policy="serial",
                worker_count=1,
                chunk_count=1,
                scheduler_enabled=False,
                temp_dir=str(output_dir / f"tmp_serial_{video_stem}_{wl_name}_{trial}"),
            )
            serial_times.append(serial_record["runtime"]["actual_total_time"])
        serial_mean = sum(serial_times) / len(serial_times)
        print(f"  Serial baseline: {serial_mean:.3f}s (mean of {TRIALS} trials)")

        # Rate profile for the scheduler
        metadata = analyze_video(input_path)
        profile_temp = output_dir / f"tmp_profile_{video_stem}_{wl_name}"
        profile_temp.mkdir(parents=True, exist_ok=True)
        rate_prof = benchmark_serial_profile(
            input_path=input_path,
            temp_dir=str(profile_temp),
            filter_chain=filter_chain,
            duration=metadata.duration,
            sample_seconds=min(1.0, metadata.duration),
            sample_fractions=[0.0, 0.25, 0.5, 0.75, 0.95],
        )
        rate_profile = None
        if rate_prof["sample_seconds"] > 0 and rate_prof["positions"] and rate_prof["samples"]:
            rate_profile = [
                (pos, t / rate_prof["sample_seconds"])
                for pos, t in zip(rate_prof["positions"], rate_prof["samples"])
            ]

        # Run each budget
        for budget in WORKER_BUDGETS:
            budget_label = f"w<={budget}" if budget is not None else "unconstrained"
            measured_times = []
            selected_info = None

            for trial in range(1, TRIALS + 1):
                out_path = output_dir / f"{video_stem}_{wl_name}_budget{budget or 'unc'}_trial{trial}.mp4"
                record = run_processing_pipeline(
                    input_path=input_path,
                    output_path=str(out_path),
                    filter_chain=filter_chain,
                    partition_policy="heuristic-adaptive",
                    worker_count=4,  # default, overridden by scheduler
                    chunk_count=4,
                    scheduler_enabled=True,
                    scheduler_workers=[1, 2, 4, 6, 8, 12, 16],
                    scheduler_chunk_multipliers=[1.0, 1.5, 2.0],
                    serial_reference_time=serial_mean,
                    serial_reference_output_path=str(output_dir / f"{video_stem}_{wl_name}_serial_trial1.mp4"),
                    reuse_serial_reference_on_fallback=True,
                    rate_profile=rate_profile,
                    max_workers=budget,
                    temp_dir=str(output_dir / f"tmp_budget_{budget or 'unc'}_{video_stem}_{wl_name}_{trial}"),
                )
                measured_times.append(record["runtime"]["actual_total_time"])
                if selected_info is None:
                    sel = record.get("selection", {}).get("selected", {})
                    selected_info = {
                        "regime": sel.get("regime", record.get("selected_regime", "")),
                        "worker_count": sel.get("worker_count", record.get("worker_count")),
                        "chunk_count": sel.get("chunk_count", record.get("chunk_count")),
                        "policy": sel.get("partition_policy", record.get("partition_policy")),
                        "predicted_e2e_time": sel.get("predicted_e2e_time"),
                    }

            measured_mean = sum(measured_times) / len(measured_times)
            predicted = selected_info.get("predicted_e2e_time")
            pred_error = None
            if predicted is not None and measured_mean > 0:
                pred_error = (predicted - measured_mean) / measured_mean

            measured_speedup = serial_mean / measured_mean if measured_mean > 0 else 1.0
            predicted_speedup = serial_mean / predicted if predicted and predicted > 0 else 1.0
            efficiency = measured_speedup / max(1, selected_info.get("worker_count", 1))

            result = {
                "input_file": input_path,
                "video_stem": video_stem,
                "workload_class": wl_name,
                "pipeline_label": WORKLOAD_PIPELINE_DESCRIPTIONS.get(wl_name, {}).get("pipeline_label", wl_name),
                "case_reason": case["reason"],
                "budget_label": budget_label,
                "max_workers": budget,
                "selected_regime": selected_info["regime"],
                "selected_workers": selected_info["worker_count"],
                "selected_chunks": selected_info["chunk_count"],
                "selected_policy": selected_info["policy"],
                "predicted_e2e_time": round(predicted, 6) if predicted else None,
                "measured_mean_time": round(measured_mean, 6),
                "measured_serial_time": round(serial_mean, 6),
                "prediction_error": round(pred_error, 6) if pred_error is not None else None,
                "measured_speedup": round(measured_speedup, 4),
                "predicted_speedup": round(predicted_speedup, 4),
                "measured_efficiency": round(efficiency, 4),
                "trials": TRIALS,
            }
            all_results.append(result)

            err_str = f"{pred_error:+.1%}" if pred_error is not None else "n/a"
            print(
                f"  {budget_label:18s}: w={selected_info['worker_count']} "
                f"measured={measured_mean:.3f}s predicted={predicted:.3f}s "
                f"err={err_str} speedup={measured_speedup:.2f}x eff={efficiency:.3f}"
            )

    # Write JSON report
    report = {
        "description": (
            "Measured validation of resource-budgeted execution selection. "
            "Compares the selector's predicted runtimes against measured execution "
            "under worker budget constraints of 2, 4, 8, and unconstrained. "
            "Three representative cases: serial-favorable (3s light), "
            "budget-saturating (12s medium), and budget-scaling (30s heavy)."
        ),
        "validation_cases": VALIDATION_CASES,
        "worker_budgets": [b if b is not None else "unconstrained" for b in WORKER_BUDGETS],
        "trials_per_configuration": TRIALS,
        "results": all_results,
    }

    # Add compact summary
    pred_errors = [abs(r["prediction_error"]) for r in all_results if r["prediction_error"] is not None]
    report["prediction_accuracy_summary"] = {
        "n": len(pred_errors),
        "mean_absolute_error": round(sum(pred_errors) / len(pred_errors), 6) if pred_errors else None,
        "max_absolute_error": round(max(pred_errors), 6) if pred_errors else None,
        "within_10pct": sum(1 for e in pred_errors if e <= 0.10),
        "within_20pct": sum(1 for e in pred_errors if e <= 0.20),
    }

    (output_dir / "budget_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Write CSV
    if all_results:
        csv_fields = [
            "video_stem", "workload_class", "pipeline_label", "budget_label",
            "selected_regime", "selected_workers", "selected_chunks", "selected_policy",
            "predicted_e2e_time", "measured_mean_time", "measured_serial_time",
            "prediction_error", "measured_speedup", "predicted_speedup", "measured_efficiency",
        ]
        with open(output_dir / "budget_validation.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)

    print("\n=== Summary ===")
    if pred_errors:
        print(f"Prediction accuracy: MAE={sum(pred_errors)/len(pred_errors):.1%}, "
              f"within 10%: {sum(1 for e in pred_errors if e<=0.10)}/{len(pred_errors)}, "
              f"within 20%: {sum(1 for e in pred_errors if e<=0.20)}/{len(pred_errors)}")
    print(f"Results written to {output_dir}/")


if __name__ == "__main__":
    main()
