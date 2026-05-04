# Decision-Aware IEEE Draft

Main file:

```text
paper_draft_decision_aware.tex
```

Compile from this folder:

```bash
pdflatex paper_draft_decision_aware.tex
pdflatex paper_draft_decision_aware.tex
```

The draft intentionally contains red `TBD` placeholders. Replace them after the GPU benchmark produces:

```text
experiments/paper_run_gpu_decision_cost/summary.csv
experiments/paper_run_gpu_decision_cost/calibration_report.json
experiments/paper_run_gpu_decision_cost/paper_assets/decision_cost_summary.json
experiments/paper_run_gpu_decision_cost/paper_assets/figure5_decision_cost_rho.svg
```

Convert the decision-cost SVG to PDF or PNG before the final LaTeX compile.
