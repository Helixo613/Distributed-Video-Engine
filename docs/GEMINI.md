# GEMINI.md - Distributed Video Rendering Engine

This file documents the architecture and features of the **Distributed Video Rendering Engine** implemented for the HPC Hackathon.

## 🚀 Mission
Demonstrate algorithmic scalability and **Amdahl's Law** on commodity hardware (CPU-only) by parallelizing video filters using a **Split-Process-Merge** architecture, visualized through a professional HPC Control Center.

## 🏗️ Core Architecture: The "Virtual Split"
We utilize a **Seek-and-Process** strategy to eliminate the serial I/O overhead of physical file splitting.

1.  **Analysis:** `ffprobe` determines duration and stream metadata.
2.  **Scheduling:** Dynamic chunk calculation (Chunk Count = Workers * 1.5).
3.  **Parallel Workers:** `concurrent.futures.ProcessPoolExecutor` spawns workers that use `ffmpeg -ss` to seek directly into the source.
4.  **Aggregation:** Instant merge using FFmpeg's `concat` demuxer with stream-copy (`-c copy`).
5.  **UI Layer (New):** A Streamlit-based dashboard for interactive benchmarking and result visualization.

## 🏆 Winning Features (The "Hybrid" Implementation)

### 1. Live HPC CLI Dashboard (Rich)
A professional multi-pane terminal interface for high-precision monitoring:
-   **Job Progress:** Real-time completion percentage and estimated time remaining.
-   **CPU Heatmap:** Per-core utilization monitor (via `psutil`) to prove 100% hardware saturation across the entire CPU topology.
-   **Status Logs:** Live rolling logs showing worker task assignment and completion.

### 2. Scaling Sweep Benchmark
The engine executes a **Scaling Sweep** (1, 2, 4, 8... workers) to generate a performance profile.
-   **Efficiency Metrics:** Calculates Speedup ($S$) and Efficiency ($E$) for each configuration.
-   **Amdahl's Analysis:** Estimates the "Serial Fraction" ($f$) and predicts the theoretical maximum speedup based on the observed bottleneck.

### 3. Integrated Test Asset Generation
Built-in capability to generate synthetic, CPU-intensive Mandelbrot fractal videos for instant, zero-dependency demos.

### 4. Data-Driven Reporting
-   **JSON Performance Export:** Full benchmark results saved for external analysis, plotting, or archival.
-   **Robust Aggregation:** Smart fallback logic (Stream-copy -> Re-encode) ensures the final video integrity.

## 🛠️ Usage

### Running the Engine
```bash
# Full scaling sweep with dashboard
python3 render_engine.py --sweep

# Heavy filter mode for 4K benchmarking
python3 render_engine.py input.mp4 -w 8 --filter "hqdn3d=10:10:10:10"

# Export data for reporting
python3 render_engine.py input.mp4 --export report.json
```

## 📊 Amdahl's Law Verification
The engine measures:
$$Speedup = \frac{T_{serial}}{T_{parallel}}$$
And helps identify the **Serial Bottleneck** ($f$):
$$S(N) = \frac{1}{f + \frac{1-f}{N}}$$

---
*Created by Gemini CLI for the 2026 HPC Hackathon.*
