#!/usr/bin/env python3
"""Generate decision-cost evidence for the paper rewrite.

The central paper metric is rho = T_decide / T_execute.  This script reads the
flattened experiment CSV, compares each adaptive-scheduled run against the best
non-adaptive default available for the same trial, and emits paper-ready assets.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median


def _float(row: dict[str, str], key: str) -> float | None:
    raw = row.get(key)
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _trial_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("input_file", ""),
        row.get("experiment.workload_class", ""),
        row.get("experiment.trial", ""),
    )


def _round(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def build_decision_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_trial_key(row)].append(row)

    decision_rows: list[dict[str, object]] = []
    for (input_file, workload, trial), group in sorted(grouped.items()):
        adaptive = next((row for row in group if row.get("experiment.baseline") == "adaptive-scheduled"), None)
        if adaptive is None:
            continue

        rho = _float(adaptive, "decision_cost.rho")
        t_decide = _float(adaptive, "decision_cost.T_decide")
        t_execute = _float(adaptive, "decision_cost.T_execute")
        adaptive_runtime = _float(adaptive, "runtime.actual_total_time")
        if rho is None or t_decide is None or t_execute is None or adaptive_runtime is None:
            continue

        defaults = [
            row for row in group
            if row.get("experiment.baseline") in {"serial", "static-equal"}
            and _float(row, "runtime.actual_total_time") is not None
        ]
        if not defaults:
            continue

        best_default = min(defaults, key=lambda row: _float(row, "runtime.actual_total_time") or float("inf"))
        best_default_runtime = _float(best_default, "runtime.actual_total_time")
        if best_default_runtime is None or best_default_runtime <= 0:
            continue

        margin = (best_default_runtime - adaptive_runtime) / best_default_runtime
        decision_rows.append(
            {
                "input_file": input_file,
                "workload_class": workload,
                "trial": int(float(trial)) if trial else None,
                "content_class": adaptive.get("experiment.content_class") or "",
                "duration_label": adaptive.get("experiment.duration_label") or "",
                "selected_regime": adaptive.get("selected_regime") or "",
                "selected_label": adaptive.get("selection.selected.label") or "",
                "adaptive_runtime": _round(adaptive_runtime),
                "best_default_baseline": best_default.get("experiment.baseline"),
                "best_default_runtime": _round(best_default_runtime),
                "selector_vs_default_margin": _round(margin),
                "adaptive_beneficial": margin > 0.0,
                "T_metadata": _round(_float(adaptive, "decision_cost.T_metadata")),
                "T_features": _round(_float(adaptive, "decision_cost.T_features")),
                "T_scheduler": _round(_float(adaptive, "decision_cost.T_scheduler")),
                "T_decide": _round(t_decide),
                "T_execute": _round(t_execute),
                "rho": _round(rho),
            }
        )
    return decision_rows


def summarize(decision_rows: list[dict[str, object]]) -> dict[str, object]:
    rhos = [float(row["rho"]) for row in decision_rows if row.get("rho") is not None]
    margins = [
        float(row["selector_vs_default_margin"])
        for row in decision_rows
        if row.get("selector_vs_default_margin") is not None
    ]
    beneficial = [row for row in decision_rows if row.get("adaptive_beneficial") is True]
    safer_default = [row for row in decision_rows if row.get("adaptive_beneficial") is False]
    return {
        "n": len(decision_rows),
        "beneficial_count": len(beneficial),
        "default_safer_count": len(safer_default),
        "rho_mean": _round(mean(rhos)) if rhos else None,
        "rho_median": _round(median(rhos)) if rhos else None,
        "rho_min": _round(min(rhos)) if rhos else None,
        "rho_max": _round(max(rhos)) if rhos else None,
        "margin_mean": _round(mean(margins)) if margins else None,
        "definition": "rho = T_decide / T_execute; T_decide = T_metadata + T_features + T_scheduler.",
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [
        "input_file", "workload_class", "trial", "content_class", "duration_label",
        "selected_regime", "selected_label", "adaptive_runtime", "best_default_baseline",
        "best_default_runtime", "selector_vs_default_margin", "adaptive_beneficial",
        "T_metadata", "T_features", "T_scheduler", "T_decide", "T_execute", "rho",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, rows: list[dict[str, object]]) -> None:
    width, height = 920, 560
    left, right, top, bottom = 82, 34, 42, 82
    plot_w = width - left - right
    plot_h = height - top - bottom
    xs = [float(row["best_default_runtime"]) for row in rows if row.get("best_default_runtime") is not None]
    ys = [float(row["rho"]) for row in rows if row.get("rho") is not None]
    x_max = max(xs) * 1.08 if xs else 1.0
    y_max = max(ys) * 1.15 if ys else 1.0
    x_max = max(x_max, 1.0)
    y_max = max(y_max, 0.05)

    def sx(value: float) -> float:
        return left + (value / x_max) * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value / y_max) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="82" y="28" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#111827">Decision cost ratio across adaptive runs</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#111827" stroke-width="1.4"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#111827" stroke-width="1.4"/>',
    ]

    for i in range(6):
        x_val = x_max * i / 5
        x = sx(x_val)
        parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{x:.2f}" y="{top + plot_h + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#374151">{x_val:.1f}s</text>')
    for i in range(6):
        y_val = y_max * i / 5
        y = sy(y_val)
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#374151">{y_val:.3f}</text>')

    for row in rows:
        x_val = float(row["best_default_runtime"])
        y_val = float(row["rho"])
        beneficial = row.get("adaptive_beneficial") is True
        color = "#047857" if beneficial else "#b91c1c"
        label = html.escape(f"{Path(str(row['input_file'])).stem} {row['workload_class']} trial {row['trial']}")
        parts.append(
            f'<circle cx="{sx(x_val):.2f}" cy="{sy(y_val):.2f}" r="5.5" fill="{color}" fill-opacity="0.82">'
            f"<title>{label}: rho={y_val:.4f}</title></circle>"
        )

    parts.extend(
        [
            f'<text x="{left + plot_w / 2}" y="{height - 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#111827">Best non-adaptive default runtime</text>',
            f'<text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#111827">rho = T_decide / T_execute</text>',
            f'<circle cx="{width - 250}" cy="28" r="5.5" fill="#047857" fill-opacity="0.82"/><text x="{width - 238}" y="32" font-family="Arial, sans-serif" font-size="12" fill="#111827">adaptive faster than default</text>',
            f'<circle cx="{width - 250}" cy="48" r="5.5" fill="#b91c1c" fill-opacity="0.82"/><text x="{width - 238}" y="52" font-family="Arial, sans-serif" font-size="12" fill="#111827">default safer</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(parts), encoding="utf-8")


def write_caption(path: Path, summary: dict[str, object]) -> None:
    path.write_text(
        "\n".join(
            [
                "# Decision-Cost Figure Caption",
                "",
                "Figure X plots the decision-cost ratio, rho = T_decide / T_execute, for adaptive-scheduled runs.",
                "T_decide includes metadata probing, feature extraction, and scheduler search.",
                "Green points indicate runs where adaptive selection beat the best non-adaptive default for the same trial; red points indicate trials where the default was safer.",
                "",
                f"Rows analyzed: {summary['n']}",
                f"Adaptive beneficial: {summary['beneficial_count']}",
                f"Default safer: {summary['default_safer_count']}",
                f"Mean rho: {summary['rho_mean']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate decision-cost rho assets from experiment runs.csv.")
    parser.add_argument("runs_csv", help="Path to flattened experiment runs.csv")
    parser.add_argument("--output-dir", required=True, help="Directory for generated paper assets")
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.runs_csv, newline="", encoding="utf-8")))
    decision_rows = build_decision_rows(rows)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize(decision_rows)
    write_csv(output_dir / "figure5_decision_cost_rho.csv", decision_rows)
    (output_dir / "decision_cost_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_caption(output_dir / "decision_cost_caption.md", summary)
    if decision_rows:
        write_svg(output_dir / "figure5_decision_cost_rho.svg", decision_rows)

    print(f"Decision-cost rows: {summary['n']}")
    print(f"Mean rho: {summary['rho_mean']}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
