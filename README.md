# Distributed Video Rendering Engine

A CPU-parallel video processing pipeline built for the HPC Hackathon. This tool demonstrates how to scale heavy video filtering across multiple cores using a split-process-merge pattern.

## Overview
The engine breaks a video into virtual chunks, processes them in parallel using FFmpeg subprocesses, and merges them back into a single file. It's designed to benchmark CPU scaling and verify Amdahl's Law without requiring a GPU.

## Setup

### Requirements
- Python 3.10+
- **FFmpeg** (installed and added to your system PATH)

### Installation
**Linux / WSL:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```
*Note: For Windows users, see [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) for FFmpeg setup instructions.*

## Usage

### Running a Benchmark
To run a full scaling sweep (testing 1, 2, 4, 8... workers) and see the live performance dashboard:
```bash
python src/render_engine.py --sweep
```

### Processing a Specific File
```bash
python src/render_engine.py input.mp4 -w 8 --filter "hqdn3d=10:10:10:10"
```

### Exporting Data
```bash
python src/render_engine.py input.mp4 --export results.json
```

## Project Structure
- `src/`: Core engine and synthetic video generator.
- `docs/`: Technical specs and setup guides.
- `benchmarks/`: JSON output from performance runs.
- `references/`: Research papers related to video rendering.
- `data/`: Input/Output video files (ignored by git).

## How it works
1. **Probe:** Gets video metadata using `ffprobe`.
2. **Virtual Split:** Calculates time-based offsets (no physical file cutting).
3. **Parallel Processing:** Executes multiple FFmpeg instances via `ProcessPoolExecutor`.
4. **Stream Merge:** Uses the FFmpeg concat demuxer to join chunks with no re-encoding overhead.