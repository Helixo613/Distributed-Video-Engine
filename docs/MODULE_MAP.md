# Module Map

## Research Core

- `src/video_types.py`
  Shared dataclasses for metadata, segment features, chunk tasks, partition plans, and scheduler decisions.

- `src/ffmpeg_utils.py`
  FFmpeg/ffprobe wrappers, serial baseline helpers, and concat merge logic.

- `src/feature_extractor.py`
  Low-cost feature extraction and structured feature export.

- `src/adaptive_partitioner.py`
  Serial, equal-duration, heuristic-adaptive, and ML-adaptive partition planning.

- `src/scheduler.py`
  Explicit runtime prediction and bounded configuration search.

- `src/pipeline.py`
  End-to-end orchestration and structured run records.

- `src/evaluator.py`
  Quality metric evaluation.

- `src/metrics_logger.py`
  JSONL and CSV persistence.

- `src/experiment_runner.py`
  Reproducible sweeps for videos, policies, workers, and trials.

- `src/cost_estimator.py`
  Lightweight linear regression model.

- `src/train_cost_model.py`
  Cost-model training entry point.

## Compatibility Layer

- `src/render_engine.py`
  Research-focused CLI plus compatibility exports used by `server.py`.

- `v2/src/render_engine_v2.py`
  Legacy wrapper that maps the old V2 API into the new adaptive path.

- `server.py`
  Compatibility API and preview service.

## Secondary Presentation Surfaces

- `frontend/`
- `demo_app.py`
