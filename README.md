# Distributed Video Engine

Distributed Video Engine is a research-oriented implementation base for **complexity-aware adaptive partitioning and overhead-aware scheduling for FFmpeg-based parallel video processing**.

The repository still contains the original API, frontend, and Streamlit surfaces for compatibility, but the primary development path is now the modular research pipeline in `src/`.

## Research Focus

- Complexity-aware feature extraction for low-cost video characterization
- Adaptive partitioning that balances estimated compute cost instead of only duration
- Overhead-aware worker and chunk-count selection with an explicit runtime model
- Reproducible experiment logging for baselines, ablations, and repeated trials
- Optional lightweight linear regression for segment-cost prediction

## Core Pipeline

1. `ffprobe` metadata extraction
2. Low-resolution feature extraction
3. Partition planning: `serial`, `equal-duration`, `heuristic-adaptive`, or `ml-adaptive`
4. Optional scheduler search over bounded worker/chunk candidates
5. FFmpeg execution with one FFmpeg thread per worker process
6. Concat-based merge
7. Quality and performance evaluation with JSON/CSV logging

## Main Modules

- `src/ffmpeg_utils.py`: FFmpeg/ffprobe wrappers and baseline encode helpers
- `src/feature_extractor.py`: low-cost complexity feature extraction
- `src/adaptive_partitioner.py`: baseline and adaptive chunk planning
- `src/scheduler.py`: overhead-aware configuration search
- `src/pipeline.py`: end-to-end orchestration and structured run records
- `src/evaluator.py`: PSNR/SSIM and optional VMAF hooks
- `src/metrics_logger.py`: JSONL and CSV persistence for experiment aggregation
- `src/experiment_runner.py`: reproducible sweeps for baselines and ablations
- `src/cost_estimator.py`: optional lightweight linear predictor
- `src/train_cost_model.py`: training entry point for the optional predictor

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg installed and available in `PATH`
- Node.js 18+ only if you want the legacy frontend

### Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Single Research Run

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
  --baselines serial,static-equal,adaptive-fixed,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --trials 3
```

### Optional Cost Model Training

```bash
python src/train_cost_model.py experiments/paper_run/segments.jsonl \
  --output experiments/paper_run/cost_model.json
```

## Baselines And Ablations

Supported presets through `src/experiment_runner.py`:

- `serial`
- `static-equal`
- `adaptive-fixed`
- `adaptive-scheduled`
- `ml-adaptive-scheduled` if a trained model is provided

These map directly to paper-friendly ablations:

- without adaptive partitioning
- without scheduler
- without ML predictor
- full system

## Outputs

Each run can log:

- video metadata and feature summaries
- planned chunk boundaries and planning rationale
- predicted and actual chunk runtimes
- overhead breakdowns for probe, feature extraction, scheduling, partitioning, dispatch, and merge
- total runtime, throughput, speedup, efficiency, and imbalance ratios
- output size, bitrate, PSNR, SSIM, and optional VMAF

Structured outputs are written as:

- `runs.jsonl`
- `runs.csv`
- `segments.jsonl`
- per-run JSON records when requested

## Legacy Surfaces

The following remain available but are no longer the primary framing of the project:

- `server.py`: compatibility API for job submission and previews
- `frontend/`: legacy dashboard
- `demo_app.py`: legacy Streamlit interface
- `v2/src/render_engine_v2.py`: compatibility wrapper for the old V2 path

## Additional Documentation

- [Architecture Overview](/home/arnavbansal/HPC_clean_clone/docs/PROJECT_ANALYSIS.md)
- [Technical Architecture](/home/arnavbansal/HPC_clean_clone/docs/GEMINI.md)
- [Experiment Guide](/home/arnavbansal/HPC_clean_clone/docs/EXPERIMENTS.md)
- [Module Map](/home/arnavbansal/HPC_clean_clone/docs/MODULE_MAP.md)
- [Paper Alignment](/home/arnavbansal/HPC_clean_clone/docs/PAPER_ALIGNMENT.md)
