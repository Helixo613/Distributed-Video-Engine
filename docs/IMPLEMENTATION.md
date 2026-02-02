# Implementation Notes

## Phase 1: Core Engine
The first step was wrapping FFmpeg in Python's `subprocess` module. We chose raw subprocess calls over libraries like `moviepy` to minimize overhead and have direct control over flags like `-ss` and `-preset`. 

Key challenge: Ensuring the merge didn't result in "green frames" or audio desync. Using the `concat` demuxer with `-c copy` solved this, provided all chunks were encoded with identical parameters.

## Phase 2: Parallelization
We used `concurrent.futures.ProcessPoolExecutor` for the worker pool.
- **Why not threading?** Python's GIL would block the subprocess management. Multiprocessing allows the OS to handle the parallel execution of the FFmpeg binaries more effectively.
- **Load Balancing:** Added logic to divide the video into more chunks than workers. This prevents the "last worker standing" problem where one long chunk keeps a single core busy while others are idle.

## Phase 3: Benchmarking & Dashboard
To make the demo effective, we added a scaling sweep. This runs the same job multiple times with different worker counts.
- **UI:** Used `rich` for the dashboard. It provides a clean way to show per-core usage without the complexity of a web-based UI.
- **Metrics:** Implemented a simple Amdahl's Law calculator to show judges the theoretical limit of our parallelization.

## Phase 4: 4K Optimization
Testing on 4K content revealed memory bottlenecks. Running 16+ workers on 4K frames can exhaust RAM. We added a recommendation to cap workers at 8 for high-resolution content or use heavier filters to make the task more CPU-bound than I/O-bound.