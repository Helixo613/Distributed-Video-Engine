# Experiment Guide

## Recommended Workflow

1. Prepare a deterministic set of input videos.
2. Run `src/experiment_runner.py` with explicit worker candidates, chunk multipliers, and trial counts.
3. Aggregate `runs.csv` and `runs.jsonl`.
4. Train an optional linear model from `segments.jsonl`.
5. Re-run with `ml-adaptive-scheduled` for comparison.

## Example

```bash
python src/experiment_runner.py \
  videos/a.mp4 videos/b.mp4 \
  --output-dir experiments/ieee_run \
  --baselines serial,static-equal,adaptive-fixed,adaptive-scheduled \
  --workers 1,2,4,6,8,12,16 \
  --chunk-multipliers 1.0,1.5,2.0 \
  --trials 3 \
  --full-serial
```

## Logged Metrics

- input file and video id
- duration, resolution, FPS, bitrate
- feature summary
- partition policy
- worker count and chunk count
- chunk boundaries and predicted costs
- actual per-chunk runtimes
- probe, feature, scheduler, partition, dispatch, and merge overheads
- total runtime, throughput, speedup, efficiency
- chunk imbalance / straggler ratio
- output bitrate and size
- PSNR and SSIM
- optional VMAF

## Baselines

- `serial`
- `static-equal`
- `adaptive-fixed`
- `adaptive-scheduled`
- `ml-adaptive-scheduled`

## Ablations

- without adaptive partitioning: `static-equal`
- without scheduler: `adaptive-fixed`
- without ML: `adaptive-scheduled`
- full system: `ml-adaptive-scheduled`

## Notes

- If full serial runs are too expensive, start with projected serial time and only enable `--full-serial` for final paper-grade measurements.
- If model training becomes expensive, export `segments.jsonl` and train in Kaggle or another batch environment.
