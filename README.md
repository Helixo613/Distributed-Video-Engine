# Distributed Video Rendering Engine (HPC Hackathon)

A high-performance, distributed video processing engine written in Python. It uses a **Split-Process-Merge** architecture to parallelize FFmpeg filters across CPU cores, demonstrating **Amdahl's Law** and algorithmic scalability on commodity hardware.

## 📂 Project Structure

```
/
├── src/
│   ├── render_engine.py       # Core Logic + Scheduler + CLI
│   └── generate_test_video.py # Synthetic Asset Generator
├── docs/
│   ├── GEMINI.md              # Final Architecture & Features
│   ├── ARCHITECTURE.md        # Original Architecture Design
│   └── IMPLEMENTATION.md      # Step-by-Step Implementation Guide
├── benchmarks/                # JSON Performance Data
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Setup Environment
**WSL / Linux:**
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
*Note: For Windows users, please follow the [FFmpeg Installation Guide](docs/WINDOWS_SETUP.md) before starting.*

### 2. Run the Engine
Run a full scaling sweep (1, 2, 4, 8... workers) with the live HPC dashboard:
```bash
python src/render_engine.py --sweep
```

## 💻 Cross-Platform Compatibility
This project is developed on WSL (Ubuntu) but is designed to be fully compatible with native Windows environments. For detailed setup instructions regarding Windows paths, FFmpeg binaries, and environment activation, see:
👉 **[docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)**

### 3. Demo Mode (High Load)
To prove the speedup on high-end hardware (simulating 3D rendering), run with the heavy filter:
```bash
python src/render_engine.py input.mp4 -w 8 --filter "hqdn3d=10:10:10:10"
```

## 📊 Key Features
*   **Live CLI Dashboard:** Visualizes per-core CPU usage and job progress.
*   **Auto-Asset Gen:** Automatically creates a test video if none is provided.
*   **Data Export:** Saves benchmark results to JSON for analysis.

## 📝 UI Integration
This backend is designed to be decoupled. The UI team should interface with it by:
1.  Calling `render_engine.py` via `subprocess`.
2.  Parsing the real-time stdout for progress updates.
3.  Reading the `--export result.json` file for final metrics.
