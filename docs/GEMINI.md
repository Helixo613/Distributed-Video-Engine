# Technical Specifications

## Architectural Overview
The engine implements a "Virtual Split" architecture. Instead of physically segmenting the input file (which creates significant I/O overhead), the scheduler calculates time-based offsets and passes them to parallel worker processes.

### 1. Ingest & Analysis
The `analyzer` uses `ffprobe` to extract duration, resolution, and codec information. This data is used to calculate the chunk boundaries.

### 2. Scheduler
The workload is distributed using a `ProcessPoolExecutor`.
- **Worker Count:** Default is the logical CPU count.
- **Load Balancing:** The engine uses an oversubscription factor of 1.5x (Chunks = Workers * 1.5) to ensure high CPU utilization even if some chunks process faster than others.

### 3. Processing Pipeline
Each worker executes an independent FFmpeg subprocess:
```bash
ffmpeg -ss [start] -i [input] -t [duration] -vf [filter] [output_chunk]
```
Using `-ss` before `-i` ensures fast, frame-accurate seeking. Chunks are rendered using the `libx264` encoder with the `ultrafast` preset to focus the benchmark on the filter's computational cost.

### 4. Concat & Merge
Processed chunks are merged using the `concat` demuxer.
```bash
ffmpeg -f concat -i concat_list.txt -c copy [final_output]
```
The use of `-c copy` ensures the merge phase is a simple stream copy, making it a negligible part of the total execution time.

## Benchmarking Logic
The engine calculates the speedup factor ($S$) by comparing the serial execution time ($T_1$) against the parallel execution time ($T_n$):
$$S = T_1 / T_n$$

It also estimates the serial fraction of the code using Amdahl's Law to identify bottlenecks in the filesystem or scheduling logic.

## Monitoring
The CLI uses a multi-pane layout to show:
- Per-core utilization (Real-time).
- Chunk status (Queued, Processing, Finished).
- Global job progress.