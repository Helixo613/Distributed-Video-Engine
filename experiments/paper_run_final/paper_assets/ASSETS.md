# Paper Assets — experiments/paper_run_final/paper_assets/

Generated from the canonical `paper_run_final` package (117 runs, 13 cases, 5 inputs, 3 trials).

## Tables

### table1_main_comparison.csv
Main performance comparison table. One row per case (13 rows).
Columns: case, content_class, serial/static-equal/selector runtimes, selector speedup, vs_static_pct, winner, selector_good.
Use for: Table 1 in the paper — "Execution selection results across preprocessing workloads."

### table2_calibration.csv
Cost model prediction accuracy. Rows: overall, parallel-only, by workload (heavy/medium/light), by content class.
Columns: scope, n, mae_pct, median_ae_pct, within_10pct, within_20pct.
Use for: Table 2 — "Cost model calibration accuracy."

### table3_budget_tradeoffs.csv
Resource-budgeted selection summary. One row per budget level (w<=2, w<=4, w<=8, unconstrained).
Columns: budget, mean_speedup, mean_efficiency_pct, serial/parallel selection counts.
Use for: Table 3 — "Efficiency under worker budget constraints."

## Figure Data

### figure1_speedup_comparison.csv
Per-case runtimes for all three baselines. 13 rows.
Plot as: grouped bar chart (serial vs static-equal vs selector) or speedup bar chart.

### figure2_calibration_scatter.csv
Predicted vs actual runtime for all 39 adaptive-scheduled runs.
Plot as: scatter with y=x reference line. Color by workload or content class.

### figure3_budget_curves.csv
Per-case predicted speedup and efficiency at each budget level. 52 rows (13 cases x 4 budgets).
Plot as: line chart of speedup vs budget, or efficiency vs budget. Group by case or aggregate.

### figure4_selector_decisions.csv
Selector regime/label/worker/chunk choices per case. 13 rows.
Plot as: heatmap or annotation table showing what the selector chose and whether it was correct.

## Figures (PNG + PDF)

### figure1_speedup_comparison.png / .pdf
Grouped bar chart: serial vs static-equal vs adaptive-scheduled runtime per case.
Use for: Figure 1 — main performance comparison.

### figure2_calibration_scatter.png / .pdf
Scatter plot: predicted vs measured runtime for all 39 adaptive-scheduled runs, colored by workload.
Use for: Figure 2 — cost model calibration quality.

### figure3_budget_tradeoffs.png / .pdf
Dual-axis line chart: mean speedup (left) and mean efficiency (right) vs worker budget.
Use for: Figure 3 — resource-budgeted selection tradeoffs.

### figure4_selector_decisions.png / .pdf
Bar chart: selected worker count per case, colored by correctness (good/miss) and regime (parallel/serial).
Use for: Figure 4 — selector decision breakdown.

## Text Artifacts

### threats_to_validity.md
Concise threats-to-validity section covering internal, external, and construct validity. Ready to paste into the paper.

### reproducibility_note.md
Artifact description and reproduction workflow. Covers the canonical package path, file contents, and exact commands to reproduce.

## Key Numbers (ground truth from paper_run_final)

- 5 inputs, 13 cases, 117 runs, 2457 segments
- 10/13 outright wins for adaptive-scheduled
- 12/13 good selector decisions
- 1 conservative serial miss (3s light clip)
- 2 near-ties where static-equal is marginally faster (12s heavy: -0.7%, 12s light: -0.2%)
- Parallel speedup range: 1.9x-4.0x
- Overall prediction MAE: 7.2% (parallel-only: 7.8%)
- By workload: heavy 2.9%, medium 3.9%, light 13.2%
- Budget efficiency: w<=2 80.5%, w<=4 62.6%, w<=8 52.5%
- Measured budget validation MAE: 2.8% (11/12 within 10%)
