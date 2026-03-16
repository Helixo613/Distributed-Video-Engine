# Distributed-Video-Engine Revision Brief for Codex / Claude Code

## Purpose
Transform the current repo from a hackathon-style FFmpeg parallel processing demo into a research-grade adaptive scheduling system for an IEEE-style paper path.

## Core repositioning
Change the project story from:

> “distributed video engine with smart AI dashboard”

to:

> **complexity-aware adaptive partitioning and concurrency control for FFmpeg-based parallel video processing**

## Non-negotiable changes
- Remove or sharply demote paper-facing phrases such as:
  - HPC Hackathon
  - CPU burn
  - Smart AI
  - Amdahl’s Law demo
- Keep the dashboard and API only as supporting infrastructure.
- Make the core contribution about:
  - adaptive chunk partitioning
  - worker/chunk-count selection
  - overhead-aware scheduling
  - makespan reduction
  - load-balance improvement
  - comparable output quality

## Target architecture
Current rough flow:
- probe metadata
- split by time
- parallel FFmpeg
- merge

Target flow:
- probe metadata
- extract lightweight features
- estimate per-segment cost
- partition by predicted cost
- choose workers and chunk count
- parallel FFmpeg execution
- merge
- evaluate and log metrics

### Target control pipeline
`Probe -> Feature Extraction -> Cost Prediction -> Adaptive Partitioner -> Worker/Chunk Selector -> Parallel FFmpeg Execution -> Merge -> Evaluator`

## Required module map
Create or revise modules with the following roles:

### `feature_extractor.py`
Extract cheap content signals:
- duration
- width / height
- fps
- bitrate
- bits-per-pixel
- scene-change proxy
- frame-difference motion score
- optional sampled low-res encode-time proxy

### `cost_estimator.py`
Two-stage design:
1. deterministic heuristic score
2. optional lightweight regressor

Output:
- per-segment predicted compute cost

### `adaptive_partitioner.py`
Responsibilities:
- partition by predicted cost, not pure duration
- enforce minimum chunk length
- avoid tiny tail segments
- support chunk counts tied to worker candidates

### `scheduler.py`
Responsibilities:
- evaluate candidate worker/chunk configurations
- estimate total runtime
- choose the best configuration
- log the decision reason

Recommended objective:
`T_total(w, k) = T_probe + T_feature + T_partition + T_dispatch + max_i(T_i) + T_merge + T_overhead`

where:
- `w` = workers
- `k` = chunks
- `T_i` = predicted processing time of chunk `i`

Suggested candidate search:
- workers: `{1, 2, 4, 6, 8, 12, 16}`
- chunk multipliers: `{1.0x, 1.5x, 2.0x}`

### `evaluator.py`
Must log:
- video metadata
- planning decisions
- predicted per-chunk costs
- actual per-chunk runtimes
- dispatch time
- merge time
- total runtime
- throughput
- CPU / memory summary
- output bitrate
- PSNR
- SSIM
- optional VMAF
- speedup vs serial
- efficiency
- imbalance ratio
- scheduling error
- success/failure

### `bench_runner.py`
Run the full experiment matrix and emit structured artifacts for later plotting.

### `paper_config.yaml`
Single source of truth for:
- dataset paths
- worker candidates
- chunk multipliers
- sampling interval
- quality metric flags
- preset / filter configuration
- repetition count

## Detailed implementation phases

## Phase A — repo cleanup and research framing
Tasks:
1. create a paper-facing branch
2. rename V2 from a marketing label to a systems label
3. update README and architecture notes
4. keep UI logic separate from planning logic

## Phase B — lightweight feature extraction
Requirements:
- stay cheap
- do not add heavy frame-level deep learning
- sample at coarse intervals

Minimum features:
- duration
- resolution
- fps
- bitrate
- BPP
- scene-change estimate
- frame-difference motion estimate

Optional:
- tiny encode-time probe on downscaled snippets
- I-frame density

Important:
- persist feature vectors to logs for later ML training

## Phase C — cost estimation
Rollout:
- Stage 1: heuristic scorer from metadata + sampled complexity
- Stage 2: lightweight regressor trained on logged runtimes
- Stage 3: optional model comparison

Recommended ML options if time allows:
- Linear Regression
- Random Forest Regressor
- XGBoost / LightGBM

Do **not** build:
- CNN
- LSTM
- Transformer
- anything frame-heavy

## Phase D — adaptive partitioning
Replace equal-duration chunking.

Desired behavior:
- balance chunks by predicted compute cost
- honor minimum chunk size
- avoid pathological tiny segments
- produce per-chunk predicted costs in logs

## Phase E — worker and chunk selector
Use predicted chunk costs plus overhead estimates.

Must support:
- candidate search over worker/chunk configurations
- predicted runtime breakdown
- selection of best configuration
- logging of chosen config and alternatives

## Phase F — evaluation layer
Every experiment must produce machine-readable artifacts.

Mandatory outputs:
- experiment summary CSV / JSON
- per-chunk log CSV / JSON
- aggregated summary for paper plots

## Baselines that must exist
- `B1`: serial FFmpeg
- `B2`: static equal-duration partitioning with fixed workers
- `B3`: adaptive partitioning with heuristic cost
- `B4`: adaptive partitioning + worker selector
- `B5`: adaptive partitioning + worker selector + ML predictor (optional)
- `UB`: oracle worker sweep (upper bound)

## Required ablations
- remove adaptive partitioning
- remove worker selector
- remove ML predictor
- compare full system vs reduced variants

## Practical experiment plan
Use a controlled, diverse evaluation set:
- 4 low-motion videos
- 4 medium-motion videos
- 4 high-motion videos
- resolutions across 720p, 1080p, 4K
- durations roughly 30 seconds to 3 minutes

Run each configuration:
- minimum 3 times
- preferably 5 times

Keep preset/filter fixed for the main scheduling study.

## Mandatory reported metrics
- total runtime
- speedup vs serial
- efficiency
- average utilization
- chunk imbalance ratio
- merge overhead %
- scheduling error
- PSNR
- SSIM
- optional VMAF
- failure rate

## Paper-facing plots/tables the code should enable
- architecture figure
- runtime vs workers plot
- chunk runtime spread plot
- predicted cost vs actual cost plot
- main comparison table
- ablation table

## Definition of done
The revised repo is only paper-ready when:
- adaptive planning exists before execution
- serial and static baselines run cleanly
- adaptive heuristic path runs cleanly
- metrics are logged automatically
- structured plots/tables can be generated from logs
- paper-facing language no longer sounds like a gimmick demo

## Suggested repository layout
```text
src/
  planner/
    feature_extractor.py
    cost_estimator.py
    adaptive_partitioner.py
    scheduler.py
  engine/
    ffmpeg_runner.py
    merge_manager.py
    serial_runner.py
  evaluation/
    evaluator.py
    metrics.py
    quality.py
  experiments/
    bench_runner.py
    plot_results.py
    configs/
      paper_config.yaml
  api/
    routes.py
    service.py
tests/
docs/
  paper_notes/
  experiment_reports/
```

## Build priority if time is limited
### Tier 1
- repo reframing
- feature extractor
- heuristic cost score
- adaptive partitioner
- evaluator
- serial/static baselines

### Tier 2
- worker/chunk selector
- experiment harness
- plots and tables
- quality metrics

### Tier 3
- lightweight ML regressor
- oracle comparison
- stronger ablations

## What not to do
- do not add deep learning just to claim AI
- do not spend major effort on frontend polish first
- do not vary presets/filters in every experiment
- do not claim novelty from dashboard/API/basic FFmpeg usage
- do not skip machine-readable logs

## Final paper claim the implementation should support
Compared with static equal-duration partitioning and fixed worker assignment, a complexity-aware and overhead-aware scheduling layer reduces end-to-end runtime and workload imbalance for FFmpeg-based parallel video processing while keeping output quality comparable.

## Recent papers guiding the direction
1. KubeTranscode: A Distributed FFmpeg-based System for DASH Transcoding at Scale (2025, IEEE GIEST)  
   https://www.researchgate.net/publication/401007036_KubeTranscode_A_Distributed_FFmpeg-based_System_for_DASH_Transcoding_at_Scale

2. Cloud media video encoding: review and challenges (2024)  
   https://link.springer.com/article/10.1007/s11042-024-18763-2

3. Optimal Transcoding Preset Selection for Live Video Streaming (2024)  
   https://arxiv.org/abs/2411.14613

4. ALPHAS: Adaptive Bitrate Ladder Optimization for Multi-Live Video Streaming (2025)  
   https://gorinsky.networks.imdea.org/pdf/ALPHAS_Adaptive_Bitrate_Ladder_Optimization_for_Multi-Live_Video_Streaming_IEEE_INFOCOM_2025_accepted_version.pdf

5. Efficient distributed adaptive transcoding: intelligent dynamic partitioning and virtual reference substream co-design (2025)  
   https://www.spiedigitallibrary.org/conference-proceedings-of-spie/13793/1379329/Efficient-distributed-adaptive-transcoding--intelligent-dynamic-partitioning-and-virtual/10.1117/12.3077498.full
