# Adaptive Execution Selection for Media Preprocessing in Cloud AI Pipelines

Research prototype for **overhead-aware adaptive execution selection** applied to media preprocessing workloads in cloud/AI systems.

The system decides — before execution — whether a media preprocessing job should run serially or in parallel, and if parallel, selects the worker count, chunk count, and partitioning strategy using a calibrated runtime cost model. This targets the preprocessing stage of AI ingestion pipelines where video must be normalized, enhanced, or denoised before downstream ML inference.

## Problem

Cloud-based AI pipelines frequently preprocess media (resize, normalize, denoise, sharpen) before feeding it to vision models, multimodal embeddings, or analytics systems. The preprocessing stage is often parallelized with fixed configurations that ignore:

- **Content complexity**: static surveillance footage vs. high-motion action clips require different resources
- **Workload intensity**: lightweight normalization vs. heavy denoising have very different compute profiles
- **Orchestration overhead**: splitting, dispatching, and merging chunks has non-trivial cost that can dominate short or lightweight jobs

Fixed parallelization can waste cloud resources on jobs where serial execution would suffice, and under-provisions jobs that would benefit from more workers.

## Approach

An **execution selector** that uses a calibrated overhead-aware cost model to choose the execution regime:

1. **Feature extraction**: Low-cost video characterization (motion, scene complexity, bitrate distribution)
2. **Cost model prediction**: Estimate serial runtime, parallel makespan with overhead penalties, and orchestration costs (dispatch, merge, per-process startup)
3. **Configuration search**: Evaluate candidate (workers, chunks, policy) configurations against the cost model
4. **Regime selection**: Choose serial when overhead would dominate, parallel when the predicted speedup exceeds a safety margin
5. **Resource-budgeted mode**: Optionally constrain the search to a maximum worker budget, selecting the best plan within a cloud resource allocation limit

## Preprocessing Workloads

Workloads represent preprocessing pipelines at varying compute intensity:

| Class | Pipeline Label | Description | Filter Chain |
|-------|---------------|-------------|-------------|
| `light` | inference-normalization | Color/brightness normalization for ML inference preparation | `eq=contrast=1.02:brightness=0.01:saturation=1.03` |
| `medium` | vision-enhancement | Sharpening for vision analytics (feature extraction, action recognition) | `unsharp=5:5:1.5:5:5:0.5` |
| `heavy` | robust-preprocessing | Multi-stage denoise+sharpen for noisy media before AI model ingestion | `hqdn3d=1.5:1.5:6:6,gblur=sigma=1.2,unsharp=7:7:1.8:7:7:0.8` |

## Core Pipeline

1. `ffprobe` metadata extraction
2. Low-resolution feature extraction (motion, scene cuts, texture complexity)
3. Partition planning: `serial`, `equal-duration`, `heuristic-adaptive`, or `ml-adaptive`
4. Execution selector search over bounded worker/chunk candidates
5. FFmpeg-based preprocessing with one thread per worker process
6. Concat-based merge
7. Quality and performance evaluation with structured logging

## Main Modules

- `src/pipeline.py`: End-to-end orchestration and structured run records
- `src/scheduler.py`: Overhead-aware execution selector with configuration search
- `src/feature_extractor.py`: Low-cost video complexity characterization
- `src/adaptive_partitioner.py`: Content-aware chunk planning
- `src/experiment_runner.py`: Reproducible benchmark sweeps across baselines
- `src/summarize_experiment_results.py`: Summary generation with preprocessing pipeline metadata
- `src/calibration_analysis.py`: Cost model calibration and prediction quality analysis
- `src/evaluator.py`: PSNR/SSIM quality evaluation
- `src/cost_estimator.py`: Optional lightweight linear segment-cost predictor

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg installed and available in `PATH`

### Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Single Preprocessing Run

```bash
python src/render_engine.py input.mp4 \
  --partition-policy heuristic-adaptive \
  --scheduler \
  --record-output outputs/run_record.json \
  --feature-output outputs/features.json
```

### Reproducible Experiment Sweep

```bash
python src/experiment_runner.py input1.mp4 input2.mp4 \
  --output-dir experiments/paper_run \
  --baselines serial,static-equal,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --workloads light,medium,heavy \
  --trials 3
```

### Calibration Analysis

```bash
python src/calibration_analysis.py experiments/paper_run/runs.csv \
  --output-json experiments/paper_run/calibration_report.json
```

### Resource-Budgeted Selection Analysis

```bash
python src/budget_analysis.py experiments/paper_run/runs.csv \
  --output-json experiments/paper_run/budget_analysis.json \
  --output-csv experiments/paper_run/budget_analysis.csv \
  --budgets 2,4,8
```

## Baselines

| Preset | Partitioning | Selector | Role |
|--------|-------------|----------|------|
| `serial` | None | No | Lower bound: single-process execution |
| `static-equal` | Equal-duration | No | Fixed parallel: no content awareness |
| `adaptive-scheduled` | Heuristic-adaptive | Yes | Full system: overhead-aware execution selection |

## Outputs

Each experiment produces:

- `runs.csv` / `runs.jsonl`: Per-trial metrics (runtime, speedup, prediction error, quality)
- `segments.jsonl`: Per-segment feature and runtime data
- `summary.json` / `summary.csv`: Aggregated results with preprocessing pipeline metadata
- `calibration_report.json`: Cost model prediction accuracy and overhead analysis
- `budget_analysis.json` / `budget_analysis.csv`: Resource-budgeted selection tradeoffs
- `manifest.json`: Experiment configuration and preprocessing pipeline descriptions

## Reproducing the Final Package

```bash
bash scripts/reproduce_final_package.sh experiments/paper_run_final
```

This runs the full benchmark suite (117 runs across 13 cases), generates summaries, calibration reports, and budget analysis in a single command. See `experiments/paper_run_final/paper_assets/reproducibility_note.md` for details.

## Additional Documentation

- [Paper Alignment](docs/PAPER_ALIGNMENT.md)
- [Experiment Guide](docs/EXPERIMENTS.md)
- [Module Map](docs/MODULE_MAP.md)
- [Architecture Overview](docs/PROJECT_ANALYSIS.md)

## Legacy Surfaces

The following remain available but are not the primary framing:

- `server.py`: Compatibility API for job submission
- `frontend/`: Legacy dashboard
- `demo_app.py`: Legacy Streamlit interface
