# Reproducibility and Artifact Description

## Canonical Package

Path: `experiments/paper_run_final/`

This directory contains the complete, self-contained result package for all claims in the paper.

## Contents

| File | Description |
|------|-------------|
| `manifest.json` | Experiment configuration: inputs, workloads, baselines, worker candidates, trial count, preprocessing pipeline metadata |
| `runs.csv` | 117 per-trial records with runtime, prediction error, overhead breakdown, quality metrics, and selector decisions |
| `runs.jsonl` | Same data in JSON-lines format (one JSON object per run) |
| `segments.jsonl` | 2,457 per-segment records with features and runtimes for optional cost model training |
| `summary.json` | Aggregated per-case results: winner analysis, selector decisions, speedup, preprocessing pipeline framing |
| `summary.csv` | 13-row summary table for direct use in paper tables |
| `calibration_report.json` | Cost model prediction accuracy by workload, duration, and content class; overhead contribution breakdown |
| `budget_analysis.json` | Resource-budgeted selection analysis: 52 tradeoff entries (13 cases x 4 budgets), efficiency/speedup summaries |
| `budget_analysis.csv` | CSV version of budget analysis tradeoffs |
| `paper_assets/` | Table-ready CSVs, figure PNGs/PDFs, and supporting text artifacts |

## Reproduction Workflow

### Prerequisites
- Python 3.10+
- FFmpeg installed and in PATH

### One-command reproduction (preferred)

```bash
bash scripts/reproduce_final_package.sh experiments/paper_run_final
```

This script runs both experiment batches, merges them, generates all analysis artifacts (summary, calibration report, budget analysis), and cleans up temporary files. An optional output directory argument overrides the default path.

### Detailed manual steps (equivalent)

#### Step 1: Main experiment (4 clips, 3 workloads)
```bash
PYTHONPATH=src python3 -m experiment_runner \
  experiments/benchmark_suite/inputs/real_clipchamp_720p_12s.mp4 \
  experiments/benchmark_suite/inputs/real_test_input_720p_30s.mp4 \
  experiments/benchmark_suite/inputs/real_phone_1080p_12s.mp4 \
  experiments/benchmark_suite/inputs/real_clipchamp_1080p_30s.mp4 \
  --output-dir experiments/paper_run_final \
  --baselines serial,static-equal,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --fixed-workers 4 --trials 3 \
  --workloads light,medium,heavy \
  --benchmark-manifest experiments/benchmark_suite/benchmark_manifest.json
```

### Step 2: Short clip (3s, light only)
```bash
PYTHONPATH=src python3 -m experiment_runner \
  experiments/benchmark_suite/inputs/real_clipchamp_720p_3s.mp4 \
  --output-dir experiments/paper_run_final_short \
  --baselines serial,static-equal,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --fixed-workers 4 --trials 3 \
  --workloads light \
  --benchmark-manifest experiments/benchmark_suite/benchmark_manifest.json
```

### Step 3: Merge
```bash
tail -n +2 experiments/paper_run_final_short/runs.csv >> experiments/paper_run_final/runs.csv
cat experiments/paper_run_final_short/segments.jsonl >> experiments/paper_run_final/segments.jsonl
cat experiments/paper_run_final_short/runs.jsonl >> experiments/paper_run_final/runs.jsonl
```

### Step 4: Generate analysis artifacts
```bash
PYTHONPATH=src python3 -m summarize_experiment_results \
  experiments/paper_run_final/runs.csv \
  --output-json experiments/paper_run_final/summary.json \
  --output-csv experiments/paper_run_final/summary.csv

PYTHONPATH=src python3 -m calibration_analysis \
  experiments/paper_run_final/runs.csv \
  --output experiments/paper_run_final/calibration_report.json

PYTHONPATH=src python3 -m budget_analysis \
  experiments/paper_run_final/runs.csv \
  --output-json experiments/paper_run_final/budget_analysis.json \
  --output-csv experiments/paper_run_final/budget_analysis.csv
```

## Key Numbers

- 5 inputs, 13 cases, 3 baselines, 3 trials = 117 runs
- 10/13 outright wins for adaptive-scheduled
- 12/13 good selector decisions
- Overall prediction MAE: 7.2% (parallel-only: 7.8%)
- Measured budget validation MAE: 2.8%
