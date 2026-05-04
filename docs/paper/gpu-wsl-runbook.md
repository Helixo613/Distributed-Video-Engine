# GPU WSL Paper Runbook

Use this for the RTX 3060 laptop. Run all final paper experiments on one machine and report that machine in the paper.

## 1. Update The Repository

```bash
cd ~/HPC_clean_clone
env -u GITHUB_TOKEN git fetch origin
env -u GITHUB_TOKEN git checkout feature/research-demo-ui
env -u GITHUB_TOKEN git pull
```

If the folder is not a git clone yet:

```bash
cd ~
env -u GITHUB_TOKEN git clone https://github.com/Helixo613/Distributed-Video-Engine.git HPC_clean_clone
cd ~/HPC_clean_clone
env -u GITHUB_TOKEN git checkout feature/research-demo-ui
```

## 2. Install Runtime Dependencies

```bash
cd ~/HPC_clean_clone
sudo apt update
sudo apt install -y python3-venv ffmpeg
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Check NVIDIA Access In WSL

```bash
nvidia-smi
ffmpeg -hide_banner -encoders | grep nvenc
python3 - <<'PY'
import sys
sys.path.insert(0, "src")
from ffmpeg_utils import execution_backend_info
print(execution_backend_info("auto"))
PY
```

Expected result:

```text
{'requested': 'auto', 'resolved': 'cuda', 'nvenc_available': True}
```

If it says `resolved: cpu`, WSL/FFmpeg cannot use NVENC yet. The code will still run correctly, but not GPU-accelerated.

## 4. Quick Smoke Test

Use any available short video path. This verifies the GPU backend, decision-cost fields, and rho asset generation.

```bash
cd ~/HPC_clean_clone
source venv/bin/activate
export DVE_EXECUTION_BACKEND=auto

PYTHONPATH=src python3 -m experiment_runner \
  uploads/your_video.mp4 \
  --output-dir experiments/smoke_gpu_decision_cost \
  --workloads light \
  --baselines serial,adaptive-scheduled \
  --workers 1,2 \
  --chunk-multipliers 1.0 \
  --fixed-workers 2 \
  --trials 1 \
  --execution-backend auto

PYTHONPATH=src python3 -m decision_cost_analysis \
  experiments/smoke_gpu_decision_cost/runs.csv \
  --output-dir experiments/smoke_gpu_decision_cost/paper_assets
```

## 5. Prepare Benchmark Inputs

The benchmark input videos are `.mp4` files and are intentionally not stored in git. Check that they exist:

```bash
ls experiments/benchmark_suite/inputs
```

If the folder is missing but the original source videos are present in the repo root, regenerate the suite:

```bash
PYTHONPATH=src python3 -m prepare_benchmark_suite
```

The full paper script expects these files:

```text
experiments/benchmark_suite/inputs/real_clipchamp_720p_12s.mp4
experiments/benchmark_suite/inputs/real_test_input_720p_30s.mp4
experiments/benchmark_suite/inputs/real_phone_1080p_12s.mp4
experiments/benchmark_suite/inputs/real_clipchamp_1080p_30s.mp4
experiments/benchmark_suite/inputs/real_clipchamp_720p_3s.mp4
```

## 6. Full Paper Run

```bash
cd ~/HPC_clean_clone
source venv/bin/activate
export DVE_EXECUTION_BACKEND=auto
bash scripts/reproduce_final_package.sh experiments/paper_run_gpu_decision_cost
```

The output backend is recorded in:

```text
experiments/paper_run_gpu_decision_cost/manifest.json
experiments/paper_run_gpu_decision_cost/runs.csv
```

Use these generated paper assets:

```text
experiments/paper_run_gpu_decision_cost/paper_assets/figure5_decision_cost_rho.svg
experiments/paper_run_gpu_decision_cost/paper_assets/figure5_decision_cost_rho.csv
experiments/paper_run_gpu_decision_cost/paper_assets/decision_cost_summary.json
experiments/paper_run_gpu_decision_cost/paper_assets/decision_cost_caption.md
```

## Paper Wording

Report the backend like this:

> Experiments were run on a laptop with an NVIDIA RTX 3060 GPU with 6 GB VRAM, 32 GB RAM, and FFmpeg NVENC acceleration enabled through WSL. The selector logic was unchanged; only the execution backend used for FFmpeg encoding changed from CPU x264 to NVENC where available.

Do not mix these results with CPU-only runs from another laptop.
