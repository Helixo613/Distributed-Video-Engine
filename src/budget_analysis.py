#!/usr/bin/env python3
"""Resource-budgeted execution selection analysis.

Evaluates the overhead-aware execution selector under multiple worker budget
constraints, producing a tradeoff report that shows how the selected plan,
predicted runtime, and resource efficiency change as the budget varies.

This is the cloud-resource-scheduling contribution: the selector not only
picks the fastest plan, but can recommend the best plan under a given
resource budget — relevant to elastic cloud preprocessing services where
worker allocation has cost implications.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from cost_estimator import LinearCostEstimator
from feature_extractor import extract_video_features
from ffmpeg_utils import analyze_video, benchmark_serial_profile, resolve_execution_backend
from scheduler import search_best_configuration


def _run_budgeted_selection(
    input_path: str,
    filter_chain: str,
    serial_reference_time: float,
    worker_budgets: list[int | None],
    all_workers: list[int],
    chunk_multipliers: list[float],
    partition_policy: str,
    rate_profile: list[tuple[float, float]] | None,
    temp_dir: str,
) -> list[dict]:
    """Run the selector under each worker budget and collect results."""
    metadata = analyze_video(input_path)
    feature_result = extract_video_features(input_path)

    results = []
    for budget in worker_budgets:
        budget_label = f"w<={budget}" if budget is not None else "unconstrained"
        start = time.perf_counter()
        selection = search_best_configuration(
            input_path=input_path,
            metadata=metadata,
            feature_result=feature_result,
            filter_chain=filter_chain,
            temp_dir=temp_dir,
            workers=all_workers,
            chunk_multipliers=chunk_multipliers,
            partition_policy=partition_policy,
            serial_reference_time=serial_reference_time,
            rate_profile=rate_profile,
            max_workers=budget,
        )
        elapsed = time.perf_counter() - start

        sel = selection.selected
        predicted_speedup = selection.estimated_serial_time / sel.predicted_e2e_time if sel.predicted_e2e_time > 0 else 1.0
        efficiency = predicted_speedup / max(1, sel.worker_count)

        results.append({
            "budget_label": budget_label,
            "max_workers": budget,
            "selected_regime": sel.regime,
            "selected_label": sel.label,
            "selected_workers": sel.worker_count,
            "selected_chunks": sel.chunk_count,
            "selected_policy": sel.partition_policy,
            "predicted_e2e_time": round(sel.predicted_e2e_time, 6),
            "predicted_compute_time": round(sel.predicted_compute_time, 6),
            "estimated_serial_time": round(selection.estimated_serial_time, 6),
            "predicted_speedup": round(predicted_speedup, 4),
            "predicted_efficiency": round(efficiency, 4),
            "selector_time": round(elapsed, 6),
            "n_candidates_searched": len(selection.search_trace),
            "rationale": selection.selection_rationale[:3],
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resource-budgeted execution selection analysis for media preprocessing."
    )
    parser.add_argument("runs_csv", help="Path to runs.csv from an experiment run (for serial reference times)")
    parser.add_argument("--output-json", default=None, help="Output JSON report path")
    parser.add_argument("--output-csv", default=None, help="Output CSV summary path")
    parser.add_argument("--budgets", default="2,4,8", help="Comma-separated worker budget values to evaluate")
    parser.add_argument("--workers", default="1,2,4,6,8,12,16", help="Full worker candidate list")
    parser.add_argument("--chunk-multipliers", default="1.0,1.5,2.0", help="Chunk multipliers")
    parser.add_argument("--workloads", default="light,medium,heavy", help="Workload classes to analyze")
    parser.add_argument("--execution-backend", default="auto", help="FFmpeg backend for profiling: auto, cpu, or cuda")
    args = parser.parse_args()
    resolved_backend = resolve_execution_backend(args.execution_backend)

    budgets_int = [int(b.strip()) for b in args.budgets.split(",")]
    worker_budgets: list[int | None] = budgets_int + [None]  # None = unconstrained
    all_workers = [int(w.strip()) for w in args.workers.split(",")]
    chunk_multipliers = [float(c.strip()) for c in args.chunk_multipliers.split(",")]
    workload_names = [w.strip() for w in args.workloads.split(",")]

    # Import workload presets
    from experiment_runner import WORKLOAD_PRESETS, WORKLOAD_PIPELINE_DESCRIPTIONS

    # Read runs.csv to get serial reference times per (input_file, workload_class)
    rows = list(csv.DictReader(open(args.runs_csv, newline="", encoding="utf-8")))
    serial_refs: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r.get("experiment.baseline") == "serial":
            t = r.get("runtime.actual_total_time")
            if t not in ("", None):
                serial_refs[(r["input_file"], r.get("experiment.workload_class", ""))].append(float(t))

    # Compute mean serial reference per (input, workload)
    serial_means: dict[tuple[str, str], float] = {}
    for key, vals in serial_refs.items():
        serial_means[key] = sum(vals) / len(vals)

    # Get unique inputs from the runs
    input_files = sorted(set(r["input_file"] for r in rows))

    all_results: list[dict] = []
    for input_file in input_files:
        for wl_name in workload_names:
            key = (input_file, wl_name)
            if key not in serial_means:
                continue
            serial_time = serial_means[key]
            filter_chain = WORKLOAD_PRESETS.get(wl_name, "")
            if not filter_chain:
                continue

            temp_dir = f"/tmp/budget_analysis_{Path(input_file).stem}_{wl_name}"
            Path(temp_dir).mkdir(parents=True, exist_ok=True)

            # Get rate profile
            metadata = analyze_video(input_file)
            profile_sample_seconds = min(1.0, metadata.duration)
            rate_profile = None
            rate_prof = benchmark_serial_profile(
                input_path=input_file,
                temp_dir=temp_dir,
                filter_chain=filter_chain,
                duration=metadata.duration,
                sample_seconds=profile_sample_seconds,
                sample_fractions=[0.0, 0.25, 0.5, 0.75, 0.95],
                execution_backend=resolved_backend,
            )
            if rate_prof["sample_seconds"] > 0 and rate_prof["positions"] and rate_prof["samples"]:
                rate_profile = [
                    (pos, t / rate_prof["sample_seconds"])
                    for pos, t in zip(rate_prof["positions"], rate_prof["samples"])
                ]

            budget_results = _run_budgeted_selection(
                input_path=input_file,
                filter_chain=filter_chain,
                serial_reference_time=serial_time,
                worker_budgets=worker_budgets,
                all_workers=all_workers,
                chunk_multipliers=chunk_multipliers,
                partition_policy="heuristic-adaptive",
                rate_profile=rate_profile,
                temp_dir=temp_dir,
            )
            for result in budget_results:
                result["input_file"] = input_file
                result["workload_class"] = wl_name
                result["pipeline_label"] = WORKLOAD_PIPELINE_DESCRIPTIONS.get(wl_name, {}).get("pipeline_label", wl_name)
                result["measured_serial_time"] = round(serial_time, 6)
                all_results.append(result)

    # Build summary report
    # Group by (input_file, workload_class) to show budget tradeoffs per case
    case_tradeoffs: dict[str, list[dict]] = defaultdict(list)
    for r in all_results:
        case_key = f"{Path(r['input_file']).stem}::{r['workload_class']}"
        case_tradeoffs[case_key].append(r)

    # Aggregate: decision changes across budgets
    budget_decision_dist: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in all_results:
        budget_decision_dist[r["budget_label"]][r["selected_regime"]] += 1

    report = {
        "description": (
            "Resource-budgeted execution selection analysis. Shows how the selector's "
            "regime choice, worker allocation, predicted runtime, and efficiency change "
            "under different worker budget constraints. Relevant to elastic cloud "
            "preprocessing services where resource allocation has cost implications."
        ),
        "worker_budgets_evaluated": [b if b is not None else "unconstrained" for b in worker_budgets],
        "decision_distribution_by_budget": {
            label: dict(counts) for label, counts in sorted(budget_decision_dist.items())
        },
        "per_case_tradeoffs": {
            case_key: [
                {k: v for k, v in r.items() if k != "rationale"}
                for r in results
            ]
            for case_key, results in sorted(case_tradeoffs.items())
        },
        "full_results": all_results,
    }

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")

    # CSV output: flat per-budget-per-case rows
    if args.output_csv:
        csv_rows = []
        for r in all_results:
            csv_rows.append({
                "input_file": r["input_file"],
                "workload_class": r["workload_class"],
                "pipeline_label": r["pipeline_label"],
                "budget_label": r["budget_label"],
                "max_workers": r["max_workers"] if r["max_workers"] is not None else "",
                "selected_regime": r["selected_regime"],
                "selected_workers": r["selected_workers"],
                "selected_chunks": r["selected_chunks"],
                "selected_policy": r["selected_policy"],
                "predicted_e2e_time": r["predicted_e2e_time"],
                "measured_serial_time": r["measured_serial_time"],
                "predicted_speedup": r["predicted_speedup"],
                "predicted_efficiency": r["predicted_efficiency"],
            })
        if csv_rows:
            with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
                writer.writeheader()
                writer.writerows(csv_rows)

    # Print summary to stdout
    print("=== Resource-Budgeted Execution Selection ===\n")
    print("Decision distribution by budget:")
    for label, counts in sorted(budget_decision_dist.items()):
        total = sum(counts.values())
        parts = ", ".join(f"{regime}={n}" for regime, n in sorted(counts.items()))
        print(f"  {label:18s}: {parts} (n={total})")

    print("\nPer-case tradeoffs (predicted speedup):")
    for case_key, results in sorted(case_tradeoffs.items()):
        parts = []
        for r in results:
            parts.append(f"{r['budget_label']}={r['predicted_speedup']:.2f}x(w={r['selected_workers']})")
        print(f"  {case_key:50s}: {' | '.join(parts)}")

    # Efficiency summary
    print("\nEfficiency by budget (speedup / workers):")
    eff_by_budget: dict[str, list[float]] = defaultdict(list)
    for r in all_results:
        if r["selected_regime"] == "parallel":
            eff_by_budget[r["budget_label"]].append(r["predicted_efficiency"])
    for label in sorted(eff_by_budget.keys()):
        vals = eff_by_budget[label]
        mean_eff = sum(vals) / len(vals) if vals else 0
        print(f"  {label:18s}: mean_efficiency={mean_eff:.3f} (n={len(vals)} parallel cases)")


if __name__ == "__main__":
    main()
