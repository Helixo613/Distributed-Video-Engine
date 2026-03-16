# Architecture Overview

## Current Research-Oriented Structure

The repository now has two layers:

1. A **research core** in `src/` for adaptive partitioning, scheduling, and evaluation.
2. Legacy **presentation surfaces** in `server.py`, `frontend/`, and `demo_app.py` kept for compatibility.

## Execution Pipeline

1. **Probe**
   `src/ffmpeg_utils.py` uses `ffprobe` to extract duration, resolution, FPS, codec, audio presence, and bitrate.

2. **Feature Extraction**
   `src/feature_extractor.py` samples low-resolution grayscale frames to estimate:
   - bits per pixel
   - scene-change proxy
   - motion proxy
   - luma variance
   - texture proxy
   - optional low-resolution encode-time proxy

3. **Partitioning**
   `src/adaptive_partitioner.py` supports:
   - `serial`
   - `equal-duration`
   - `heuristic-adaptive`
   - `ml-adaptive`

4. **Scheduling**
   `src/scheduler.py` evaluates bounded `(workers, chunks)` candidates with an explicit runtime model:

   `T_total = T_probe + T_feature + T_partition + T_dispatch + max(chunk_costs) + T_merge + T_overhead`

5. **Execution**
   `src/pipeline.py` dispatches chunk tasks through `ProcessPoolExecutor`, with each worker launching a single-threaded FFmpeg process.

6. **Merge and Evaluation**
   Processed chunks are merged with FFmpeg concat demuxer, then `src/evaluator.py` computes output metrics for experiment logging.

## Reusable Components

- FFmpeg metadata extraction
- Serial sample baseline
- Full serial baseline
- Concat-based merge with fallback
- Quality metrics computation

## Refactor Outcome Relative To The Original Codebase

- V1 and V2 duplication has been replaced by shared modules in `src/`
- Equal-time chunking is now one baseline mode instead of the only mode
- Heuristic “smart” logic is demoted to a compatibility layer
- Experiment outputs are structured for aggregation instead of only ad hoc benchmark JSON files

## Legacy Versus Paper-Relevant Areas

Paper-relevant:

- `src/ffmpeg_utils.py`
- `src/feature_extractor.py`
- `src/adaptive_partitioner.py`
- `src/scheduler.py`
- `src/pipeline.py`
- `src/evaluator.py`
- `src/metrics_logger.py`
- `src/experiment_runner.py`
- `src/cost_estimator.py`

Legacy/demo-only or secondary:

- `frontend/`
- `demo_app.py`
- mock chunk grid behavior in `frontend/src/components/dashboard/chunk-visualizer.tsx`
- in-memory API job state in `server.py`
- legacy sweep JSON files in `benchmarks/`
