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

The draft has been updated with the GPU benchmark results from:

```text
experiments/paper_run_gpu_decision_cost/summary.csv
experiments/paper_run_gpu_decision_cost/calibration_report.json
experiments/paper_run_gpu_decision_cost/paper_assets/decision_cost_summary.json
experiments/paper_run_gpu_decision_cost/paper_assets/figure5_decision_cost_rho.svg
```

Before the final LaTeX compile, convert the decision-cost SVG to PDF or PNG, or keep the built-in placeholder box.
Also insert the exact CPU model, FFmpeg version, NVIDIA driver version, and WSL version in the hardware subsection.
