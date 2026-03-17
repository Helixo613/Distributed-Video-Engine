# Experiment Guide

## Overview

Experiments evaluate the overhead-aware execution selector across media preprocessing workloads representative of cloud AI ingestion pipelines. Each experiment runs multiple baselines, workload intensities, and trials to produce reproducible performance and quality metrics.

## Preprocessing Workloads

| Class | Pipeline Label | Description | Filter Chain |
|-------|---------------|-------------|-------------|
| `light` | inference-normalization | Lightweight color/brightness normalization for ML inference preparation | `eq=contrast=1.02:brightness=0.01:saturation=1.03` |
| `medium` | vision-enhancement | Sharpening and detail enhancement for vision analytics pipelines | `unsharp=5:5:1.5:5:5:0.5` |
| `heavy` | robust-preprocessing | Multi-stage denoise+blur+sharpen for noisy media before AI model ingestion | `hqdn3d=1.5:1.5:6:6,gblur=sigma=1.2,unsharp=7:7:1.8:7:7:0.8` |

These represent the preprocessing stage of AI pipelines at varying compute intensity, from near-zero-cost normalization (overhead-dominated) to expensive multi-stage denoising (compute-dominated).

## Recommended Workflow

1. Prepare a deterministic set of input videos with the benchmark suite.
2. Run `src/experiment_runner.py` with explicit worker candidates, chunk multipliers, trial counts, and workload presets.
3. Aggregate `runs.csv` and `runs.jsonl`.
4. Generate summaries with `src/summarize_experiment_results.py`.
5. Generate calibration analysis with `src/calibration_analysis.py`.
6. Optionally train a linear cost model from `segments.jsonl`.

## Example

```bash
python src/experiment_runner.py \
  experiments/benchmark_suite/inputs/real_*.mp4 \
  --output-dir experiments/paper_run \
  --baselines serial,static-equal,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --workloads light,medium,heavy \
  --trials 3 \
  --benchmark-manifest experiments/benchmark_suite/benchmark_manifest.json
```

## Baselines

| Preset | Description | Role |
|--------|-------------|------|
| `serial` | Single-process execution, no parallelism | Lower bound; overhead-free reference |
| `static-equal` | Fixed workers, equal-duration chunks, no selector | Fixed-parallel baseline; no content awareness |
| `adaptive-fixed` | Heuristic-adaptive partitioning, no selector | Tests partitioning quality without execution selection |
| `adaptive-scheduled` | Full system with overhead-aware execution selector | Evaluates the selector's regime and configuration choices |
| `ml-adaptive-scheduled` | Selector with trained linear cost model | Optional; requires model from `segments.jsonl` |

## Logged Metrics

- Input metadata: duration, resolution, FPS, bitrate, content class
- Preprocessing workload class and filter chain
- Partition policy and chunk boundaries
- Predicted and actual per-chunk runtimes
- Overhead breakdown: probe, feature extraction, scheduling, partitioning, dispatch, merge
- Total runtime, throughput, speedup, efficiency
- Selector decision: regime (serial/parallel), label, worker count, chunk count
- Prediction relative error
- Output quality: PSNR, SSIM, optional VMAF

## Output Files

- `runs.csv` / `runs.jsonl`: Per-trial raw metrics
- `segments.jsonl`: Per-segment features and runtimes
- `summary.json` / `summary.csv`: Aggregated results with preprocessing pipeline metadata
- `calibration_report.json`: Cost model prediction accuracy analysis
- `budget_analysis.json` / `budget_analysis.csv`: Resource-budgeted selection tradeoffs
- `manifest.json`: Experiment configuration with preprocessing pipeline descriptions

## Resource Budget Analysis

After running experiments, generate a budget tradeoff analysis:

```bash
python src/budget_analysis.py experiments/paper_run/runs.csv \
  --output-json experiments/paper_run/budget_analysis.json \
  --output-csv experiments/paper_run/budget_analysis.csv \
  --budgets 2,4,8
```

This evaluates the selector under each worker budget constraint and reports:
- Which regime/configuration is selected at each budget level
- Predicted speedup and efficiency (speedup / workers) per budget
- Where additional workers stop providing meaningful speedup (diminishing returns)

## Notes

- Start with the three main baselines (`serial`, `static-equal`, `adaptive-scheduled`) for the core comparison.
- Use `--benchmark-manifest` to attach content class and provenance metadata to each run.
- The calibration analysis script (`src/calibration_analysis.py`) produces prediction accuracy breakdowns by workload, duration, and content class.
- The budget analysis script (`src/budget_analysis.py`) shows how the selector's decisions change under cloud resource constraints.
