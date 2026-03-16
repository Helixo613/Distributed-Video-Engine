# Technical Architecture

## Design Goal

The system is designed as a research prototype for **adaptive scheduling and complexity-aware partitioning in FFmpeg-based parallel video processing**, not as a dashboard-first application.

## Core Design Choices

### Virtual Chunking

The engine still uses seek-based virtual chunking rather than pre-splitting the source file:

```bash
ffmpeg -ss [start] -i [input] -t [duration] ...
```

This keeps split overhead low and makes chunk planning a software concern rather than a preprocessing step.

### Single-Threaded Worker Processes

Each worker process launches FFmpeg with `-threads 1`. This makes concurrency selection explicit at the scheduler level instead of allowing FFmpeg internal threading to obscure evaluation.

### Low-Cost Feature Extraction

Feature extraction is intentionally lightweight:

- `ffprobe` metadata
- low-resolution grayscale frame sampling
- frame-difference motion proxy
- scene-change approximation from motion spikes
- luma variance and texture proxy
- optional sampled low-resolution encode-time proxy

### Adaptive Partitioning

Equal-duration chunking is retained as a baseline. Adaptive modes instead partition contiguous segments to balance estimated cost.

### Overhead-Aware Scheduling

The scheduler performs a bounded search over worker and chunk candidates and predicts runtime using:

`T_total = T_probe + T_feature + T_partition + T_dispatch + max(chunk_costs) + T_merge + T_overhead`

The model is intentionally simple, explicit, and benchmarkable.

### Reproducible Evaluation

Experiment outputs are written in machine-readable formats:

- JSONL for detailed per-run records
- CSV for aggregation
- JSON for manifest and optional per-run reports

## Legacy Compatibility

`src/render_engine.py`, `v2/src/render_engine_v2.py`, and `server.py` keep older call paths alive, but the authoritative implementation now lives in the shared `src/` research modules.
