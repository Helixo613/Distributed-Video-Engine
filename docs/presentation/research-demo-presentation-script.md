# Distributed Video Engine Presentation Script

## 1. Opening

- Today I am presenting **Distributed Video Engine**, a research prototype for adaptive video preprocessing.
- The project is focused on cloud AI pipelines where video is preprocessed before downstream tasks like detection, analytics, or multimodal inference.
- The core question is simple:
  - **Should this video preprocessing job run serially or in parallel?**
  - If parallel, **how many workers and chunks should we use?**
- My main contribution is not just parallel video processing.
- The novelty is **overhead-aware adaptive execution selection**.

## 2. Problem

- In many systems, video preprocessing is parallelized with a fixed worker count.
- That sounds efficient, but it is not always optimal.
- Parallel execution has overhead:
  - splitting the video
  - dispatching chunks
  - starting worker processes
  - merging output chunks
- For short or lightweight clips, this overhead can dominate the actual useful work.
- For longer or heavier clips, parallelism can give meaningful speedup.
- So the problem is:
  - fixed serial execution can be too slow
  - fixed parallel execution can waste resources
  - the system needs to decide before execution which path makes sense

## 3. Project Idea

- The engine first analyzes the input video using lightweight features.
- It extracts signals like:
  - duration
  - resolution
  - bitrate
  - motion level
  - scene changes
  - texture complexity
- Then it uses a cost model to estimate:
  - serial runtime
  - parallel runtime
  - dispatch overhead
  - merge overhead
  - worker startup cost
- Based on this estimate, the scheduler selects:
  - serial execution, or
  - adaptive parallel execution
- If it chooses parallel execution, it also selects:
  - worker count
  - chunk count
  - partitioning policy

## 4. UI Walkthrough: Story Mode

- The first section of the UI is **Story Mode**.
- This is designed for presentation and reviewer clarity.
- It explains the project in four steps:
  - Problem: fixed parallelism is not always optimal.
  - Characterization: cheap video features estimate cost before execution.
  - Novelty: the scheduler decides whether parallelism is worth it.
  - Evidence: results show speedup, prediction quality, and resource tradeoffs.
- The key sentence to remember is:
  - **This project does not merely parallelize video preprocessing; it decides whether parallelism is worth it.**

## 5. UI Walkthrough: Live Demo

- The Live Demo tab has two modes.
- First is **Benchmark Replay**.
  - This uses recorded results so the presentation is reliable.
  - It compares three execution strategies:
    - Serial
    - Fixed Parallel
    - Adaptive Selector
- Second is **Live Run**.
  - If the backend is connected, I can upload a video and run the processing live.
  - The UI then polls the backend and shows:
    - job status
    - current phase
    - progress
    - parallel runtime
    - serial runtime
    - actual speedup
    - PSNR
    - SSIM
- This makes the demo safer:
  - replay mode always works
  - live mode proves the system actually runs

## 6. Demo Scenario 1: Short Lightweight Clip

- In the short/light case, the input is small and cheap to process.
- The adaptive selector chooses serial execution.
- Reason:
  - the predicted parallel speedup is not enough to justify orchestration overhead.
- This demonstrates an important point:
  - parallelism is not always the best answer.
- Even if a fixed parallel run can sometimes be close or slightly faster, the selector is conservative because it models overhead explicitly.

## 7. Demo Scenario 2: Medium Action Clip

- In the medium/action case, the video has more motion and enough useful work.
- The selector chooses adaptive parallel execution.
- It selects a worker/chunk plan that balances speedup and overhead.
- This shows that the scheduler does not always avoid parallelism.
- Instead, it chooses parallelism when the cost model predicts that it is worthwhile.

## 8. Demo Scenario 3: Long Heavy Clip

- In the long/heavy case, the preprocessing workload is more expensive.
- The overhead becomes small compared to the useful compute work.
- The adaptive selector chooses a stronger parallel plan.
- This is where the system can show larger speedups.
- The point is that the same system adapts across different workload types.

## 9. Evidence Tab

- The Evidence tab summarizes the research results.
- Key results:
  - adaptive scheduled execution wins in **10 out of 13** cases
  - selector decisions are good in **12 out of 13** cases
  - speedups are around **1.9x to 4.0x** on favorable cases
  - prediction error is around **7% overall**
- The UI also shows resource-budget tradeoffs.
- This is important for cloud systems because more workers are not always better.
- The system can reason about worker budgets and diminishing returns.

## 10. Architecture Tab

- The Architecture tab shows how the system works internally.
- Pipeline:
  - `ffprobe` extracts metadata
  - feature extraction estimates video complexity
  - scheduler predicts execution cost
  - partitioner creates chunk boundaries
  - FFmpeg workers process chunks
  - merge stage combines outputs
  - evaluator records performance and quality metrics
- The scheduler is the central research component.
- It connects video features to execution decisions.

## 11. Why This Is Novel

- Traditional systems often assume parallel execution is beneficial.
- This project asks a more careful question:
  - **Is parallel execution worth its overhead for this specific video and workload?**
- Novel contributions:
  - execution-regime selection between serial and parallel
  - overhead-aware cost model
  - content-aware video characterization
  - adaptive worker/chunk selection
  - resource-budgeted planning
  - reproducible evaluation with runtime and quality metrics

## 12. Limitations

- The current prototype depends on FFmpeg and local multiprocessing.
- GPU acceleration is not the main research contribution yet.
- A GPU laptop may help if FFmpeg GPU acceleration is configured, but the current research story is mainly about scheduling and overhead.
- The cost model is calibrated for the tested workloads, so broader deployment would need more diverse benchmark data.

## 13. Closing

- To summarize:
  - video preprocessing is important in cloud AI pipelines
  - fixed parallelism can be inefficient
  - this project predicts whether parallelism is worth it before execution
  - it chooses serial or adaptive parallel execution based on content features and overhead modeling
  - the UI demonstrates both the research idea and the working system
- The final takeaway:
  - **The contribution is adaptive execution selection, not just faster video processing.**

