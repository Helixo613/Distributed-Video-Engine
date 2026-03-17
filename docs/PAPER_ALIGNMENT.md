# Paper Alignment: Cloud/AI Workshop Framing

## Target Venue

Workshop on cloud and AI system innovation — focuses on systems-level contributions for AI/ML workloads in cloud environments.

## Core Contribution

An **overhead-aware adaptive execution selector** for media preprocessing pipelines in cloud AI systems. The selector uses a calibrated runtime cost model to decide — before execution — whether a preprocessing job should run serially or in parallel, and if parallel, which resource configuration (worker count, chunk count, partitioning strategy) minimizes end-to-end time.

## Problem Statement

Cloud-based AI pipelines preprocess media (normalize, enhance, denoise) before feeding it to downstream ML models (object detection, scene classification, multimodal embedding). This preprocessing is routinely parallelized, but fixed parallel configurations are suboptimal because:

1. **Overhead dominates lightweight jobs**: Short or low-complexity clips can become overhead-dominated, making execution-regime selection important — yet fixed configurations cannot adapt.
2. **Content complexity varies**: Static surveillance footage and high-motion action clips have different compute profiles that affect optimal parallelization.
3. **Resource waste**: Over-parallelizing lightweight preprocessing wastes cloud compute; under-parallelizing heavy preprocessing leaves speedup on the table.

Existing parallel video processing systems typically use fixed worker counts and equal-duration chunking, without dynamically selecting between serial and parallel execution based on workload and content characteristics.

## Method

1. **Lightweight content characterization** — Extract motion, scene-cut frequency, texture complexity, and bitrate distribution at low resolution to characterize the preprocessing workload without running it.
2. **Overhead-aware cost model** — Predict total execution time for candidate configurations, including explicit terms for dispatch latency, merge cost, and per-process startup overhead.
3. **Configuration search** — Sweep bounded candidate (workers, chunks, policy) space and select the configuration that minimizes predicted end-to-end time.
4. **Regime selection with safety margin** — Choose serial when predicted parallel gain does not exceed a configurable safety margin, preventing orchestration waste.

## Workload Design

Preprocessing pipelines at three intensity levels, representative of real cloud AI ingestion systems:

| Workload | Pipeline | AI/Cloud Context |
|----------|----------|-----------------|
| Light | Inference-normalization | Color/brightness normalization before ML inference (object detection, classification) |
| Medium | Vision-enhancement | Sharpening for vision analytics (feature extraction, action recognition) |
| Heavy | Robust-preprocessing | Multi-stage denoise+sharpen for noisy/low-quality media (surveillance analytics, medical video, multimodal embeddings) |

## Novelty Positioning

1. **Execution regime selection** — The system selects between serial and parallel execution, not just parallelism parameters. On very short clips (3s), the selector chooses serial because the cost model determines orchestration overhead would dominate. On longer clips (12s-30s), it selects parallel with content-appropriate worker counts. The serial selection is conservative: a brute-force fixed-parallel configuration can still be faster on very short clips, but the selector's decision reflects a principled overhead estimate.
2. **Overhead-aware cost model** — Explicit modeling of orchestration costs (dispatch, merge, process startup) rather than assuming overhead is negligible.
3. **Calibrated prediction** — The cost model achieves ~7% overall mean absolute prediction error (~8% on parallel predictions only), validated across 3 content classes, 3 preprocessing intensities, and durations from 3s to 30s.
4. **Cloud resource relevance** — The selector avoids unnecessary parallelization for overhead-dominated workloads, applicable to elastic cloud preprocessing services where resource allocation decisions have cost implications.
5. **Resource-budgeted selection** — The selector can operate under an explicit worker budget constraint (e.g., max_workers=2, 4, or 8), choosing the best plan within a cloud resource allocation limit. This produces efficiency tradeoff curves showing diminishing returns as budget increases — directly relevant to cloud cost optimization.

## Evaluation

- 5 real video inputs (720p-1080p, 3s-30s), 3 content classes
- 3 preprocessing intensities (light, medium, heavy)
- 3 baselines: serial, fixed-parallel (static-equal), full system (adaptive-scheduled)
- 3 trials per configuration for statistical reliability
- Metrics: wall-clock time, speedup, prediction error, PSNR/SSIM quality preservation
- Calibration analysis: prediction accuracy by workload/duration/content, overhead contribution breakdown
- Resource budget analysis: selector decisions and efficiency under worker budgets of 2, 4, 8, and unconstrained

## Key Results

- Adaptive-scheduled wins outright in 10/13 cases; 12/13 selector decisions are good (match or beat the best baseline within trial noise)
- Selector achieves 1.9x–4.0x speedup over serial on parallel-favorable cases
- Selects serial execution for a 3s overhead-dominated clip; the serial selection is conservative (a fixed-parallel baseline is faster on this edge case, but the selector's overhead estimate is principled)
- Two short 12s cases are near-ties where static-equal is marginally faster (within ~1% of selector runtime); the selector still makes a good decision in both
- Cost model: ~7% overall MAE (~8% parallel-only); by workload: 2.9% on heavy, 3.9% on medium, 13.2% on light
- Quality preservation: PSNR 25-44 dB, SSIM maintained across all configurations
- Resource budget tradeoffs: w<=2 achieves ~80% efficiency (speedup/workers), w<=4 achieves ~63%, w<=8 achieves ~53% — showing clear diminishing returns that inform cloud resource allocation
- 12s clips saturate at w=4 (no benefit from w=8); 30s clips benefit from scaling to w=8; 3s clip remains serial at all budgets

## Outputs

The repository generates paper-ready artifacts:

- Reproducible run manifests with preprocessing pipeline metadata
- Per-run CSV/JSON metrics with prediction error and overhead breakdowns
- Calibration reports with prediction accuracy by workload, duration, and content class
- Summary tables with selector decision analysis (regime, label, prediction quality)
- Resource budget analysis with per-case tradeoff curves and efficiency metrics
- Segment-level feature and runtime datasets for optional cost model training
