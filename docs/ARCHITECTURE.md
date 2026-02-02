# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Distributed Video Rendering Engine - HPC hackathon demo demonstrating CPU parallelism and Amdahl's Law via Split-Process-Merge pattern.

## Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg  # if not installed

# Generate test video
python generate_test_video.py 60 test_input.mp4

# Run demo
python render_engine.py test_input.mp4 --sweep
```

## Commands

```bash
# Basic run (uses all CPU cores)
python render_engine.py input.mp4

# Full scaling sweep (1, 2, 4, 8... workers)
python render_engine.py input.mp4 --sweep

# Custom workers and output
python render_engine.py input.mp4 -w 4 -o result.mp4

# Skip serial baseline (faster iteration)
python render_engine.py input.mp4 --skip-serial

# Keep temp files for debugging
python render_engine.py input.mp4 --keep-temp

# Custom filter
python render_engine.py input.mp4 --filter "boxblur=10:1"
```

## Architecture

```
Input → analyze_video() → plan_chunks() → ProcessPoolExecutor → merge_chunks() → Output
              ↓                ↓                   ↓
          ffprobe        Virtual split       FFmpeg workers
                        (no disk I/O)        (seek + filter)
```

**Key Design**: Virtual Split - workers seek directly into source file, no physical splitting step.

## Files

- `render_engine.py` - Main engine (single file, ~350 lines)
- `generate_test_video.py` - Creates test video using FFmpeg
- `.temp_chunks/` - Temporary directory (auto-cleaned)
