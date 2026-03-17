#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize experiment outputs for paper tables and decision analysis.")
    parser.add_argument("runs_csv", help="Path to runs.csv")
    parser.add_argument("--output-json", default=None, help="Optional summary JSON output path")
    parser.add_argument("--output-csv", default=None, help="Optional summary CSV output path")
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.runs_csv, newline="", encoding="utf-8")))
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["input_file"], row.get("experiment.workload_class", "medium"), row["experiment.baseline"])].append(row)

    summary_rows = []
    baseline_lookup: dict[tuple[str, str], dict[str, dict[str, float | str | None]]] = defaultdict(dict)
    for (input_file, workload_class, baseline), group in sorted(grouped.items()):
        def collect(key: str) -> list[float]:
            values = []
            for row in group:
                raw = row.get(key)
                if raw in ("", None):
                    continue
                values.append(float(raw))
            return values

        runtime = collect("runtime.actual_total_time")
        compute_time = collect("runtime.compute_time")
        e2e_time = collect("runtime.e2e_time")
        speedup = collect("performance.speedup_vs_serial")
        speedup_e2e = collect("performance.speedup_vs_serial_e2e")
        efficiency = collect("performance.efficiency")
        psnr = collect("quality.psnr")
        ssim = collect("quality.ssim")
        pred_err = collect("runtime.prediction_relative_error")
        input_psnr = collect("quality.input_psnr")
        input_ssim = collect("quality.input_ssim")
        chosen_policies = sorted({row.get("partition_policy", "") for row in group if row.get("partition_policy")})
        content_classes = sorted({row.get("experiment.content_class", "") for row in group if row.get("experiment.content_class")})

        # Determine quality reference context for this group
        quality_ref_labels = sorted({row.get("quality.reference_label", "") for row in group if row.get("quality.reference_label")})

        # Actual execution config (available for ALL baselines)
        actual_workers = collect("worker_count")
        actual_chunks = collect("chunk_count")

        # Selector decision fields (populated for adaptive-scheduled runs)
        selected_regimes = sorted({row.get("selected_regime", "") for row in group if row.get("selected_regime")})
        selected_labels = sorted({row.get("selection.selected.label", "") for row in group if row.get("selection.selected.label")})
        selected_workers = collect("selection.selected.worker_count")
        selected_chunks = collect("selection.selected.chunk_count")

        summary_row = {
            "input_file": input_file,
            "workload_class": workload_class,
            "content_class": content_classes[0] if content_classes else None,
            "baseline": baseline,
            "chosen_partition_policies": ",".join(chosen_policies),
            "selected_regime": ",".join(selected_regimes) if selected_regimes else None,
            "selected_label": ",".join(selected_labels) if selected_labels else None,
            "actual_worker_count": int(actual_workers[0]) if actual_workers and len(set(actual_workers)) == 1 else None,
            "actual_chunk_count": int(actual_chunks[0]) if actual_chunks and len(set(actual_chunks)) == 1 else None,
            "selected_worker_count": int(selected_workers[0]) if selected_workers and len(set(selected_workers)) == 1 else None,
            "selected_chunk_count": int(selected_chunks[0]) if selected_chunks and len(set(selected_chunks)) == 1 else None,
            "trials": len(group),
            "runtime_mean": round(_mean(runtime), 6) if runtime else None,
            "runtime_std": round(_stdev(runtime), 6) if runtime else None,
            "compute_time_mean": round(_mean(compute_time), 6) if compute_time else None,
            "e2e_time_mean": round(_mean(e2e_time), 6) if e2e_time else None,
            "speedup_mean": round(_mean(speedup), 6) if speedup else None,
            "speedup_e2e_mean": round(_mean(speedup_e2e), 6) if speedup_e2e else None,
            "efficiency_mean": round(_mean(efficiency), 6) if efficiency else None,
            "quality_reference": ",".join(quality_ref_labels) if quality_ref_labels else None,
            "psnr_mean": round(_mean(psnr), 6) if psnr else None,
            "ssim_mean": round(_mean(ssim), 6) if ssim else None,
            "input_psnr_mean": round(_mean(input_psnr), 6) if input_psnr else None,
            "input_ssim_mean": round(_mean(input_ssim), 6) if input_ssim else None,
            "prediction_relative_error_mean": round(_mean(pred_err), 6) if pred_err else None,
        }
        summary_rows.append(summary_row)
        baseline_lookup[(input_file, workload_class)][baseline] = summary_row

    winner_rows = []
    for (input_file, workload_class), baseline_rows in sorted(baseline_lookup.items()):
        ranked = sorted(
            (row for row in baseline_rows.values() if row.get("runtime_mean") is not None),
            key=lambda row: float(row["runtime_mean"]),
        )
        if not ranked:
            continue
        winner = ranked[0]
        serial_row = baseline_rows.get("serial")
        adaptive_row = baseline_rows.get("adaptive-scheduled")
        # The selector runs inside the adaptive-scheduled experiment baseline.
        # selector_runtime_mean is always the adaptive-scheduled runtime, because
        # that baseline executes whatever configuration the selector chose.
        # The selector's label ("static-equal", "adaptive-searched") describes the
        # *category* of plan chosen (e.g. equal-duration policy), NOT a pointer to
        # another experiment baseline — the selector may choose a different worker
        # count than the static-equal experiment baseline uses.
        static_row = baseline_rows.get("static-equal")
        selector_label = adaptive_row.get("selected_label") if adaptive_row else None
        selector_runtime = (
            float(adaptive_row["runtime_mean"])
            if adaptive_row and adaptive_row.get("runtime_mean") is not None
            else None
        )

        # selector_good_decision: the selector's execution (adaptive-scheduled
        # baseline) is within 5% of the actual winner.  When the selector and
        # winner use the same configuration (same w, c, policy) any runtime gap
        # beyond 5% is pure trial noise, so we also count a config match as good.
        selector_good_decision = None
        if selector_runtime is not None and winner.get("runtime_mean") is not None:
            best_runtime = float(winner["runtime_mean"])
            within_noise = selector_runtime <= best_runtime * 1.05
            # Config match: selector execution used the same (w, c, policy)
            # as the winner baseline.  Uses actual_worker_count (available for
            # all baselines) rather than selected_worker_count (selector-only).
            sel_cfg = (
                adaptive_row.get("actual_worker_count"),
                adaptive_row.get("actual_chunk_count"),
                adaptive_row.get("chosen_partition_policies"),
            )
            winner_full = baseline_rows.get(winner.get("baseline"), {})
            win_cfg = (
                winner_full.get("actual_worker_count"),
                winner_full.get("actual_chunk_count"),
                winner_full.get("chosen_partition_policies"),
            )
            config_match = sel_cfg == win_cfg and sel_cfg[0] is not None
            selector_good_decision = within_noise or config_match

        # Selector vs static-equal margin: positive means selector is faster
        selector_vs_static_margin = None
        if (
            selector_runtime is not None
            and static_row
            and static_row.get("runtime_mean") is not None
        ):
            t_static = float(static_row["runtime_mean"])
            if t_static > 0:
                selector_vs_static_margin = round((t_static - selector_runtime) / t_static, 6)

        # Selector vs serial speedup
        selector_vs_serial_speedup = None
        if (
            selector_runtime is not None
            and serial_row
            and serial_row.get("runtime_mean") is not None
        ):
            t_serial = float(serial_row["runtime_mean"])
            if selector_runtime > 0:
                selector_vs_serial_speedup = round(t_serial / selector_runtime, 6)

        static_runtime = (
            float(static_row["runtime_mean"])
            if static_row and static_row.get("runtime_mean") is not None
            else None
        )

        winner_rows.append(
            {
                "input_file": input_file,
                "workload_class": workload_class,
                "content_class": winner.get("content_class"),
                "serial_runtime_mean": serial_row.get("runtime_mean") if serial_row else None,
                "static_equal_runtime_mean": round(static_runtime, 6) if static_runtime is not None else None,
                "winner_baseline": winner["baseline"],
                "winner_runtime_mean": winner["runtime_mean"],
                "parallel_beneficial": winner["baseline"] != "serial",
                "selector_execution_runtime_mean": round(selector_runtime, 6) if selector_runtime is not None else None,
                "selector_selected_regime": adaptive_row.get("selected_regime") if adaptive_row else None,
                "selector_selected_label": selector_label,
                "selector_selected_policy": adaptive_row.get("chosen_partition_policies") if adaptive_row else None,
                "selector_selected_workers": adaptive_row.get("selected_worker_count") if adaptive_row else None,
                "selector_selected_chunks": adaptive_row.get("selected_chunk_count") if adaptive_row else None,
                "selector_prediction_error_mean": (
                    adaptive_row.get("prediction_relative_error_mean") if adaptive_row else None
                ),
                "selector_vs_static_margin": selector_vs_static_margin,
                "selector_vs_serial_speedup": selector_vs_serial_speedup,
                "selector_good_decision": selector_good_decision,
                "selector_psnr_mean": adaptive_row.get("psnr_mean") if adaptive_row else None,
                "selector_input_psnr_mean": adaptive_row.get("input_psnr_mean") if adaptive_row else None,
            }
        )

    payload = {
        "framing": (
            "Evaluation of an overhead-aware adaptive execution selector for media "
            "preprocessing pipelines in cloud/AI systems. Workloads represent preprocessing "
            "stages (normalization, enhancement, denoising) applied before downstream ML "
            "inference. The selector chooses between serial and parallel execution regimes "
            "based on a calibrated runtime cost model."
        ),
        "preprocessing_pipelines": {
            "light": {
                "pipeline_label": "inference-normalization",
                "description": "Lightweight color/brightness normalization for ML inference preparation.",
                "filter_chain": "eq=contrast=1.02:brightness=0.01:saturation=1.03",
            },
            "medium": {
                "pipeline_label": "vision-enhancement",
                "description": "Sharpening and detail enhancement for vision analytics pipelines.",
                "filter_chain": "unsharp=5:5:1.5:5:5:0.5",
            },
            "heavy": {
                "pipeline_label": "robust-preprocessing",
                "description": "Multi-stage denoise+sharpen chain for noisy media before AI ingestion.",
                "filter_chain": "hqdn3d=1.5:1.5:6:6,gblur=sigma=1.2,unsharp=7:7:1.8:7:7:0.8",
            },
        },
        "timing_policy": "speedup computed from compute_time (dispatch+processing+merge), symmetric across serial and parallel. "
                         "psnr/ssim for serial is vs input; for parallel is vs serial baseline. Use input_psnr/input_ssim for uniform comparison.",
        "field_semantics": {
            "selector_execution_runtime_mean": (
                "Mean measured runtime of the adaptive-scheduled experiment baseline, "
                "which executes the selector's chosen configuration.  This is the "
                "selector's actual achieved runtime, not a prediction."
            ),
            "static_equal_runtime_mean": (
                "Mean measured runtime of the static-equal experiment baseline "
                "(fixed workers, equal-duration partitioning, no selector).  "
                "Provided as a direct comparison target for the selector."
            ),
            "selector_selected_label": (
                "Category of plan the selector chose: 'serial', 'static-equal' "
                "(best equal-duration config), or 'adaptive-searched' (best "
                "heuristic/rate-adjusted config).  This is a plan category, NOT "
                "a reference to another experiment baseline — the selector may "
                "use a different worker count than the static-equal baseline."
            ),
            "selector_good_decision": (
                "True when the selector's execution runtime is within 5% of the "
                "actual winner, OR when the selector and winner used the same "
                "configuration (worker count, chunk count, policy) — indicating "
                "the runtime gap is trial noise, not a decision error."
            ),
        },
        "baseline_summary": summary_rows,
        "winner_summary": winner_rows,
    }
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.output_csv:
        with open(args.output_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(winner_rows[0].keys()) if winner_rows else [])
            writer.writeheader()
            writer.writerows(winner_rows)

    for row in winner_rows:
        margin_str = f"{row['selector_vs_static_margin']:+.1%}" if row.get("selector_vs_static_margin") is not None else "n/a"
        speedup_str = f"{row['selector_vs_serial_speedup']:.2f}x" if row.get("selector_vs_serial_speedup") is not None else "n/a"
        print(
            f"{row['input_file']} | workload={row['workload_class']} | winner={row['winner_baseline']} | "
            f"selector={row.get('selector_execution_runtime_mean', 'n/a')}s | "
            f"vs_static={margin_str} | vs_serial={speedup_str} | "
            f"good={row['selector_good_decision']}"
        )


if __name__ == "__main__":
    main()
