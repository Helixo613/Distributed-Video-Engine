# Implementation Notes

## Scope

The project was not rebuilt from scratch. The refactor preserved the original FFmpeg execution style and incrementally replaced monolithic demo logic with research-oriented modules.

## Main Changes

### Shared Core Instead Of Duplicated Engines

The original V1 and V2 paths duplicated metadata extraction, chunk planning, execution, and merge logic. The refactor moved these responsibilities into shared modules under `src/`.

### Feature-Driven Planning

The system now extracts lightweight complexity signals before partitioning:

- bitrate and BPP
- scene-change proxy
- motion proxy
- luma variance
- texture proxy
- optional encode-time proxy

### Partition Policies

The codebase now treats partitioning as an experimental variable rather than a fixed equal-duration policy.

### Scheduler Search

The scheduler explicitly searches a bounded set of worker and chunk configurations and records both predictions and actual outcomes.

### Evaluation And Logging

The old benchmark path mainly exported worker sweep timing. The new path logs:

- planning decisions
- per-chunk runtimes
- overhead breakdowns
- speedup and efficiency
- quality metrics
- segment-level records for optional model training
