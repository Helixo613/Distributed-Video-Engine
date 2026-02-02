import os
import time
import uuid
import shutil
import re
import subprocess
import mimetypes
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles
from pathlib import Path
import psutil

# Import both engines
import sys
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "v2" / "src"))

from render_engine import (
    analyze_video,
    run_parallel,
    get_smart_config,
    benchmark_serial
)

# Try to import V2 engine
try:
    from render_engine_v2 import get_content_aware_config
    V2_AVAILABLE = True
except ImportError:
    V2_AVAILABLE = False
    print("Warning: V2 engine not available")

app = FastAPI(title="HPC Rendering Server", version="2.0")

# Enable CORS for frontend
cors_origins_raw = os.getenv("HPC_CORS_ORIGINS", "*").strip()
if cors_origins_raw == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage
JOBS: Dict[str, Dict[str, Any]] = {}
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_BASE = PROJECT_ROOT / ".server_temp"
TEMP_BASE.mkdir(exist_ok=True)
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Track global stats
GLOBAL_STATS = {
    "total_jobs": 0,
    "successful_jobs": 0,
    "failed_jobs": 0,
    "total_frames_processed": 0,
    "total_processing_time": 0.0,
}

# =============================================================================
# MODELS
# =============================================================================

class JobCreate(BaseModel):
    input_path: str
    workers: Optional[int] = None
    filter_chain: Optional[str] = "unsharp=5:5:1.5:5:5:0.5"
    smart: Optional[bool] = False
    engine_version: Optional[str] = "v1"  # "v1" or "v2"

class JobStatus(BaseModel):
    id: str
    status: str  # queued, processing, completed, failed
    phase: Optional[str] = "queued" # analyzing, benchmarking, parallel, merging, completed
    progress: int
    input: str
    output: Optional[str] = None
    error: Optional[str] = None
    workers: int
    filter_chain: Optional[str] = None
    duration: Optional[str] = None
    projected_serial_time: Optional[str] = None
    smart_config: Optional[Dict[str, Any]] = None
    comparison_report: Optional[Dict[str, Any]] = None
    created_at: Optional[float] = None
    engine_version: Optional[str] = None

class ClusterStats(BaseModel):
    cpu_percent: float
    cpu_count: int
    per_cpu: List[float]
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    active_jobs: int
    queued_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_jobs: int
    avg_throughput_fps: float
    success_rate: float
    v2_available: bool

def resolve_input_path(raw_path: str) -> Path:
    """
    Resolve and validate an input path to keep processing inside the project tree.
    """
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Input path must be inside the project directory") from exc

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Input file not found: {raw_path}")

    return candidate

def _parse_psnr(stderr: str) -> Optional[float]:
    match = re.search(r"average:([0-9.]+)", stderr)
    return float(match.group(1)) if match else None

def _parse_ssim(stderr: str) -> Optional[float]:
    match = re.search(r"All:([0-9.]+)", stderr)
    return float(match.group(1)) if match else None

def _build_comparison_summary(psnr_avg: Optional[float], ssim_all: Optional[float], size_change_pct: float) -> str:
    quality = "unknown"
    if psnr_avg is not None and ssim_all is not None:
        if psnr_avg >= 40 and ssim_all >= 0.99:
            quality = "very high"
        elif psnr_avg >= 35 and ssim_all >= 0.97:
            quality = "high"
        elif psnr_avg >= 30 and ssim_all >= 0.94:
            quality = "moderate"
        else:
            quality = "noticeable changes"

    size_note = "roughly unchanged"
    if size_change_pct <= -5:
        size_note = "smaller output size"
    elif size_change_pct >= 5:
        size_note = "larger output size"

    return f"Visual similarity is {quality}. File size is {size_note} ({size_change_pct:+.1f}%)."

def generate_comparison_report(input_path: str, output_path: str, sample_seconds: float) -> Dict[str, Any]:
    """
    Generate a lightweight quality comparison between source and processed outputs.
    """
    input_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    size_change_pct = ((output_size_mb - input_size_mb) / input_size_mb * 100) if input_size_mb > 0 else 0.0

    psnr_avg: Optional[float] = None
    ssim_all: Optional[float] = None

    psnr_cmd = [
        "ffmpeg", "-hide_banner", "-v", "info",
        "-t", f"{sample_seconds:.2f}", "-i", input_path,
        "-t", f"{sample_seconds:.2f}", "-i", output_path,
        "-lavfi", "[0:v][1:v]psnr",
        "-f", "null", "-"
    ]
    ssim_cmd = [
        "ffmpeg", "-hide_banner", "-v", "info",
        "-t", f"{sample_seconds:.2f}", "-i", input_path,
        "-t", f"{sample_seconds:.2f}", "-i", output_path,
        "-lavfi", "[0:v][1:v]ssim",
        "-f", "null", "-"
    ]

    try:
        psnr_run = subprocess.run(psnr_cmd, capture_output=True, text=True, check=True)
        psnr_avg = _parse_psnr(psnr_run.stderr)
    except Exception:
        psnr_avg = None

    try:
        ssim_run = subprocess.run(ssim_cmd, capture_output=True, text=True, check=True)
        ssim_all = _parse_ssim(ssim_run.stderr)
    except Exception:
        ssim_all = None

    summary = _build_comparison_summary(psnr_avg, ssim_all, size_change_pct)

    return {
        "sample_seconds": round(sample_seconds, 2),
        "input_size_mb": round(input_size_mb, 2),
        "output_size_mb": round(output_size_mb, 2),
        "size_change_pct": round(size_change_pct, 2),
        "psnr_avg": round(psnr_avg, 3) if psnr_avg is not None else None,
        "ssim_all": round(ssim_all, 5) if ssim_all is not None else None,
        "summary": summary,
        "generated_at": time.time(),
    }

# =============================================================================
# BACKGROUND TASK
# =============================================================================

def run_render_task(
    job_id: str,
    input_path: str,
    workers: int,
    filter_chain: str,
    smart_mode: bool,
    engine_version: str
):
    """Background task wrapper for the render engine."""
    global GLOBAL_STATS

    print(f"DEBUG: Starting job {job_id}, engine={engine_version}, smart={smart_mode}", flush=True)
    job = JOBS[job_id]
    job["status"] = "processing"
    job["phase"] = "analyzing"

    job_temp = TEMP_BASE / job_id
    job_temp.mkdir(exist_ok=True)
    output_filename = f"output_{job_id}.mp4"
    output_path = OUTPUT_DIR / output_filename

    try:
        # 1. Analyze
        print("DEBUG: Analyzing video...", flush=True)
        metadata = analyze_video(input_path)

        # 2. Smart Mode Override based on engine version
        if smart_mode:
            if engine_version == "v2" and V2_AVAILABLE:
                print(f"Applying V2 Content-Aware Config for Job {job_id}", flush=True)
                smart_conf = get_content_aware_config(metadata, workers, input_path)
            else:
                print(f"Applying V1 Resolution-Based Config for Job {job_id}", flush=True)
                smart_conf = get_smart_config(metadata, workers)

            print(f"DEBUG: Smart Config Result: {smart_conf}", flush=True)
            workers = smart_conf["workers"]
            filter_chain = smart_conf["filter"]

            # Update job state with smart decisions
            job["workers"] = workers
            job["filter_chain"] = filter_chain
            job["smart_config"] = smart_conf

        # 3. Serial Benchmark (New Phase)
        job["phase"] = "benchmarking"
        print("DEBUG: Benchmarking Serial Performance...", flush=True)
        # Benchmark 2 seconds of video
        serial_sample_time = benchmark_serial(input_path, str(job_temp), filter_chain)
        
        # Extrapolate to full duration
        # If we rendered 2s in X seconds, total duration T will take (T/2) * X
        bench_dur = min(2.0, metadata.duration)
        projected_serial = (metadata.duration / bench_dur) * serial_sample_time
        job["projected_serial_time"] = f"{projected_serial:.2f}s"
        print(f"DEBUG: Projected Serial Time: {projected_serial:.2f}s (Sample: {serial_sample_time:.2f}s)", flush=True)

        # 4. Define callback
        def on_progress(p):
            job["progress"] = p

        # 5. Run Parallel
        job["phase"] = "parallel"
        print("DEBUG: Running Parallel...", flush=True)
        elapsed, _ = run_parallel(
            input_path=input_path,
            output_path=str(output_path),
            metadata=metadata,
            num_workers=workers,
            filter_chain=filter_chain,
            temp_dir=str(job_temp),
            quiet=True,
            progress_callback=on_progress
        )

        job["status"] = "completed"
        job["phase"] = "completed"
        job["progress"] = 100
        job["output"] = f"/outputs/{output_filename}"
        job["duration"] = f"{elapsed:.2f}s"
        job["comparison_report"] = generate_comparison_report(
            input_path=input_path,
            output_path=str(output_path),
            sample_seconds=min(8.0, metadata.duration),
        )

        # Update global stats
        GLOBAL_STATS["successful_jobs"] += 1
        GLOBAL_STATS["total_processing_time"] += elapsed
        GLOBAL_STATS["total_frames_processed"] += int(metadata.duration * metadata.fps)

    except Exception as e:
        job["status"] = "failed"
        job["phase"] = "completed"
        job["error"] = str(e)
        GLOBAL_STATS["failed_jobs"] += 1
        print(f"Job {job_id} failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if job_temp.exists():
            shutil.rmtree(job_temp)

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/stats", response_model=ClusterStats)
async def get_cluster_stats():
    """Get real-time cluster statistics."""
    mem = psutil.virtual_memory()

    # Count jobs by status
    active = sum(1 for j in JOBS.values() if j["status"] == "processing")
    queued = sum(1 for j in JOBS.values() if j["status"] == "queued")
    completed = sum(1 for j in JOBS.values() if j["status"] == "completed")
    failed = sum(1 for j in JOBS.values() if j["status"] == "failed")
    total = len(JOBS)

    # Calculate throughput
    if GLOBAL_STATS["total_processing_time"] > 0:
        avg_fps = GLOBAL_STATS["total_frames_processed"] / GLOBAL_STATS["total_processing_time"]
    else:
        avg_fps = 0.0

    # Success rate
    completed_total = completed + failed
    success_rate = (completed / completed_total * 100) if completed_total > 0 else 100.0

    return ClusterStats(
        cpu_percent=psutil.cpu_percent(),
        cpu_count=psutil.cpu_count(logical=True),
        per_cpu=psutil.cpu_percent(percpu=True),
        memory_percent=mem.percent,
        memory_used_gb=mem.used / (1024**3),
        memory_total_gb=mem.total / (1024**3),
        active_jobs=active,
        queued_jobs=queued,
        completed_jobs=completed,
        failed_jobs=failed,
        total_jobs=total,
        avg_throughput_fps=round(avg_fps, 1),
        success_rate=round(success_rate, 1),
        v2_available=V2_AVAILABLE
    )

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    allowed_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {allowed_extensions}")

    # Save file
    file_id = str(uuid.uuid4())[:8]
    filename = f"{file_id}_{file.filename}"
    filepath = (UPLOAD_DIR / filename).resolve()

    size_bytes = 0
    chunk_size = 1024 * 1024  # 1 MiB
    async with aiofiles.open(filepath, 'wb') as out_file:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size_bytes += len(chunk)
            await out_file.write(chunk)
    await file.close()

    # Get file size
    file_size_mb = size_bytes / (1024 * 1024)

    return {
        "filename": filename,
        "path": str(filepath.relative_to(PROJECT_ROOT)),
        "size_mb": round(file_size_mb, 2)
    }

@app.post("/jobs", response_model=JobStatus)
async def create_job(job_req: JobCreate, background_tasks: BackgroundTasks):
    print(f"DEBUG: Received Job Request: {job_req}", flush=True)

    resolved_input_path = resolve_input_path(job_req.input_path)

    # Validate engine version
    engine_version = job_req.engine_version or "v1"
    if engine_version == "v2" and not V2_AVAILABLE:
        raise HTTPException(status_code=400, detail="V2 engine not available")

    job_id = str(uuid.uuid4())[:8]
    workers = job_req.workers or os.cpu_count() or 4
    if workers < 1:
        raise HTTPException(status_code=400, detail="workers must be >= 1")

    filter_chain = job_req.filter_chain or "unsharp=5:5:1.5:5:5:0.5"
    input_display_path = str(resolved_input_path.relative_to(PROJECT_ROOT))

    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "phase": "queued",
        "progress": 0,
        "input": input_display_path,
        "workers": workers,
        "filter_chain": filter_chain,
        "created_at": time.time(),
        "smart_config": None,
        "comparison_report": None,
        "engine_version": engine_version
    }

    GLOBAL_STATS["total_jobs"] += 1

    background_tasks.add_task(
        run_render_task,
        job_id,
        str(resolved_input_path),
        workers,
        filter_chain,
        bool(job_req.smart),
        engine_version
    )

    return JOBS[job_id]

@app.get("/jobs", response_model=List[JobStatus])
async def list_jobs():
    # Sort by created_at desc
    return sorted(JOBS.values(), key=lambda x: x.get("created_at", 0), reverse=True)

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    del JOBS[job_id]
    return {"message": "Job deleted"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "v2_available": V2_AVAILABLE}

@app.get("/uploads")
async def list_uploads():
    """List all uploaded video files."""
    files = []
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            files.append({
                "filename": f.name,
                "path": str(f.relative_to(PROJECT_ROOT)),
                "size_mb": round(os.path.getsize(f) / (1024 * 1024), 2)
            })
    return sorted(files, key=lambda x: x["filename"], reverse=True)

@app.get("/files/{file_path:path}")
async def get_source_file(file_path: str):
    """
    Safely serve any project-scoped input file for UI previews/comparison.
    """
    resolved = resolve_input_path(file_path)
    media_type, _ = mimetypes.guess_type(str(resolved))
    return FileResponse(str(resolved), media_type=media_type or "application/octet-stream")

# Mount static directories
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

if __name__ == "__main__":
    import uvicorn
    try:
        print("=" * 60, flush=True)
        print("  HPC Rendering Server v2.0", flush=True)
        print(f"  V1 Engine: Available", flush=True)
        print(f"  V2 Engine: {'Available' if V2_AVAILABLE else 'Not Found'}", flush=True)
        print("=" * 60, flush=True)
        print("Starting on http://0.0.0.0:8000", flush=True)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        print(f"CRITICAL SERVER ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
