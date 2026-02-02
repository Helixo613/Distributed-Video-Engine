# Distributed Video Rendering Engine

A CPU-parallel video processing system with real-time monitoring dashboard. Built for the HPC Hackathon to demonstrate Amdahl's Law and parallel speedup using a split-process-merge pattern.

## Features

- **Dual Engine Architecture**
  - **V1 (CPU Burn):** Resolution-based heavy filtering to maximize CPU utilization
  - **V2 (Smart AI):** Content-aware analysis using bitrate/BPP detection for optimal filter selection

- **Real-time Monitoring Dashboard**
  - Cinebench-style CPU visualization with per-core utilization bars
  - Live chunk processing grid showing pending/processing/completed states
  - Throughput metrics and job history

- **REST API Backend**
  - Job queue management with concurrent processing
  - Video file upload support
  - Real-time stats endpoint for dashboard updates

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- FFmpeg installed and in PATH

### Installation

```bash
# Clone the repo
git clone https://github.com/Helixo613/Distributed-Video-Engine.git
cd Distributed-Video-Engine

# Setup Python environment
python3 -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate
pip install -r requirements.txt

# Setup frontend
cd frontend
npm install
cd ..
```

### Running the Application

**Terminal 1 - Backend:**
```bash
source venv/bin/activate
python server.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 to access the dashboard.

### CLI Usage

Run a scaling benchmark:
```bash
python src/render_engine.py --sweep
```

Process with specific workers:
```bash
python src/render_engine.py input.mp4 -w 8 --filter "hqdn3d=10:10:10:10"
```

## Project Structure

```
.
├── server.py              # FastAPI backend server
├── src/
│   └── render_engine.py   # V1 CPU Burn engine
├── v2/
│   └── src/
│       └── render_engine_v2.py  # V2 Smart AI engine
├── frontend/
│   └── src/
│       ├── App.tsx        # Main dashboard
│       └── components/
│           └── dashboard/
│               ├── realtime-monitor.tsx   # CPU visualization
│               ├── chunk-visualizer.tsx   # Processing grid
│               ├── job-list.tsx           # Job history
│               └── video-upload.tsx       # File upload
├── benchmarks/            # Performance test results
├── demo_app.py            # Streamlit demo (alternative UI)
└── docs/                  # Documentation
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server status and V2 availability |
| GET | `/stats` | Real-time CPU, memory, throughput |
| GET | `/jobs` | List all rendering jobs |
| POST | `/jobs` | Start a new render job |
| POST | `/upload` | Upload video file |
| GET | `/uploads` | List uploaded files |

## Engine Comparison

| Feature | V1 (CPU Burn) | V2 (Smart AI) |
|---------|---------------|---------------|
| Filter Selection | Resolution-based | Content-aware (bitrate/BPP) |
| Low Quality Video | Heavy denoise | Adaptive denoise |
| High Quality Video | Sharpen + saturation | Light sharpen only |
| CPU Utilization | Maximum (demo) | Optimized |

## How It Works

1. **Probe:** Extract video metadata using `ffprobe`
2. **Virtual Split:** Calculate time-based chunk offsets (no physical splitting)
3. **Parallel Process:** Run FFmpeg instances via `ProcessPoolExecutor`
4. **Stream Merge:** Concatenate chunks using FFmpeg concat demuxer

## Screenshots

The dashboard provides real-time visualization of:
- Per-core CPU utilization with color-coded load indicators
- Chunk processing progress in a Cinebench-style grid
- Job queue with status, progress, and timing information

## License

MIT
