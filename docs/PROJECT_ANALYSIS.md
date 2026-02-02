# Project Analysis: Distributed Video Rendering Engine

## 1. Project Overview
**Name:** Distributed Video Rendering Engine
**Purpose:** A High-Performance Computing (HPC) demonstration tool designed to visualize and measure the effects of parallel scaling and **Amdahl's Law** on video processing tasks.
**Core Tech:** Python 3, FFmpeg, `concurrent.futures` (multiprocessing), `rich` (CLI UI), `psutil` (system monitoring).
**Architecture:** **Split-Process-Merge** using a "Virtual Split" strategy (seek-based processing) to minimize I/O overhead.

## 2. Directory Structure & Key Files

```text
/home/arnavbansal/HPC/
├── render_engine.py           # [CORE] Main application logic (CLI, orchestration, benchmarking)
├── generate_test_video.py     # [UTIL] Generates synthetic CPU-intensive video assets (Mandelbrot)
├── GEMINI.md                  # [DOCS] High-level architectural documentation
├── benchmark.json             # [DATA] Output from a scaling sweep run
├── output_processed.mp4       # [ARTIFACT] Final rendered video output
├── .temp_chunks/              # [TEMP] Temporary storage for video segments during processing
└── venv/                      # [ENV] Python virtual environment
```

## 3. Component Analysis

### A. Main Engine (`render_engine.py`)
This is the orchestrator. It follows a strictly sequential pipeline:

1.  **Analysis Phase:**
    *   Uses `ffprobe` to extract metadata (duration, resolution, FPS).
    *   Validates input streams (checks for video/audio).

2.  **Planning Phase:**
    *   **Dynamic Chunking:** Breaks the video into segments.
    *   **Formula:** $Chunks = Workers \times 4$. This "over-decomposition" helps with load balancing (preventing a single slow chunk from stalling the entire job).

3.  **Execution Phase (The "Virtual Split"):**
    *   Instead of cutting the source file physically, it spawns workers that read the *same* source file but seek (`-ss`) to specific timestamps.
    *   **Thread Pinning:** Forces FFmpeg to use 1 thread per process (`-threads 1`) to reduce context switching and ensure the Python process pool manages the concurrency, not FFmpeg's internal threading.
    *   **Live Dashboard:** Uses `rich` to show per-core CPU utilization (heatmap) and job progress.

4.  **Merge Phase:**
    *   Uses FFmpeg's `concat` demuxer.
    *   **Strategy:** Attempts a stream-copy first (instant). If that fails, falls back to a re-encode merge (slower but robust).

5.  **Benchmarking & Analytics:**
    *   Can run a "Sweep" (1, 2, 4, 8... N workers).
    *   Calculates **Speedup** ($T_{serial} / T_{parallel}$) and **Efficiency**.
    *   Estimates the **Serial Fraction** ($f$) of the workload using Amdahl's Law.

### B. Test Generator (`generate_test_video.py`)
*   Creates a `mandelbrot` fractal video stream using FFmpeg's `lavfi` (Libavfilter).
*   **Why?** Fractals are mathematically expensive to calculate, making them perfect for testing CPU compute performance without needing massive input files.

### C. Data Output (`benchmark.json`)
A structured JSON report containing:
*   **Metadata:** Input video specs.
*   **Serial Time:** Baseline execution time.
*   **Sweep Results:** Performance metrics for each worker count (Time, Speedup, Efficiency).

## 4. Observations & Insights

### The "Small File" Anomaly
Looking at the provided `benchmark.json`:
*   **Serial Time:** ~3.23s
*   **16 Workers:** ~4.31s
*   **Insight:** The sample run shows *negative scaling* (slowdown) for 16 workers. This is a textbook HPC lesson: **Overhead Dominance**.
    *   For a short 30s clip, the overhead of spawning 16 Python processes and starting 60+ FFmpeg instances outweighs the parallel compute gains.
    *   The engine is designed for *heavy* workloads (long videos or complex filters like `hqdn3d`). On trivial tasks, the orchestration cost > compute cost.

### Architecture Strengths
1.  **I/O Efficiency:** No intermediate "split" files on disk. Workers read directly from source.
2.  **Resilience:** Robust fallback if stream-copy merging fails.
3.  **Visibility:** The dashboard proves "work is happening" which is crucial for demos.

## 5. Usage Commands

**Standard Run:**
```bash
python3 render_engine.py input.mp4 -w 8
```

**Scientific Benchmark (Sweep):**
```bash
python3 render_engine.py input.mp4 --sweep --export benchmark.json
```

**Generate Test Asset:**
```bash
python3 generate_test_video.py
```
