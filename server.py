import mimetypes
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "v2" / "src"))

from adaptive_partitioner import build_partition_plan
from evaluator import evaluate_output
from feature_extractor import extract_video_features
from ffmpeg_utils import analyze_video, benchmark_serial_sample, ensure_dir
from metrics_logger import MetricsLogger
from pipeline import execute_partition_plan, write_record
from render_engine import get_smart_config
from scheduler import search_best_configuration

try:
    from render_engine_v2 import get_content_aware_config

    V2_AVAILABLE = True
except ImportError:
    V2_AVAILABLE = False
    print("Warning: V2 compatibility engine not available")

app = FastAPI(title="Distributed Video Engine Research API", version="2.1")

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

JOBS: Dict[str, Dict[str, Any]] = {}
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_BASE = PROJECT_ROOT / ".server_temp"
TEMP_BASE.mkdir(exist_ok=True)
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
RECORD_DIR = OUTPUT_DIR / "records"
RECORD_DIR.mkdir(exist_ok=True)
API_METRICS_DIR = OUTPUT_DIR / "api_metrics"
API_METRICS_DIR.mkdir(exist_ok=True)
API_METRICS_LOGGER = MetricsLogger(str(API_METRICS_DIR))

GLOBAL_STATS = {
    "total_jobs": 0,
    "successful_jobs": 0,
    "failed_jobs": 0,
    "total_frames_processed": 0,
    "total_processing_time": 0.0,
}

DEFAULT_SCHEDULER_WORKERS = [1, 2, 4, 6, 8, 12, 16]
DEFAULT_CHUNK_MULTIPLIERS = [1.0, 1.5, 2.0]


class JobCreate(BaseModel):
    input_path: str
    workers: Optional[int] = None
    filter_chain: Optional[str] = "unsharp=5:5:1.5:5:5:0.5"
    smart: Optional[bool] = False
    strict_benchmark: Optional[bool] = False
    engine_version: Optional[str] = "v1"
    partition_policy: Optional[str] = None
    chunk_count: Optional[int] = None
    scheduler_enabled: Optional[bool] = None
    scheduler_workers: Optional[List[int]] = None
    scheduler_chunk_multipliers: Optional[List[float]] = None
    enable_encode_proxy: Optional[bool] = False
    enable_vmaf: Optional[bool] = False


class JobStatus(BaseModel):
    id: str
    status: str
    phase: Optional[str] = "queued"
    progress: int
    input: str
    output: Optional[str] = None
    error: Optional[str] = None
    workers: int
    filter_chain: Optional[str] = None
    duration: Optional[str] = None
    projected_serial_time: Optional[str] = None
    serial_actual_time: Optional[str] = None
    serial_progress: Optional[int] = 0
    serial_output: Optional[str] = None
    parallel_progress: Optional[int] = 0
    smart_config: Optional[Dict[str, Any]] = None
    comparison_report: Optional[Dict[str, Any]] = None
    created_at: Optional[float] = None
    engine_version: Optional[str] = None
    strict_benchmark: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    feature_summary: Optional[Dict[str, Any]] = None
    partition_policy: Optional[str] = None
    chunk_count: Optional[int] = None
    planning_rationale: Optional[List[str]] = None
    planned_chunk_boundaries: Optional[List[Dict[str, Any]]] = None
    predicted_chunk_costs: Optional[List[float]] = None
    actual_chunk_runtime: Optional[List[Dict[str, Any]]] = None
    overheads: Optional[Dict[str, float]] = None
    decision_cost: Optional[Dict[str, Optional[float]]] = None
    performance: Optional[Dict[str, Any]] = None
    scheduler: Optional[Dict[str, Any]] = None
    scheduler_enabled: Optional[bool] = None
    experiment_record_path: Optional[str] = None
    quality_metrics: Optional[Dict[str, Any]] = None


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


def _format_seconds(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{value:.2f}s"


def _public_path(path: Path) -> str:
    return "/" + str(path.relative_to(PROJECT_ROOT)).replace(os.sep, "/")


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


def build_comparison_report(
    quality_metrics: Dict[str, Any],
    sample_seconds: float,
    speedup: Optional[float],
    serial_mode: str,
) -> Dict[str, Any]:
    psnr_avg = quality_metrics.get("psnr")
    ssim_all = quality_metrics.get("ssim")
    size_change_pct = float(quality_metrics.get("size_change_pct") or 0.0)
    report = {
        "sample_seconds": round(sample_seconds, 2),
        "input_size_mb": quality_metrics.get("reference_size_mb"),
        "output_size_mb": quality_metrics.get("output_size_mb"),
        "size_change_pct": round(size_change_pct, 2),
        "psnr_avg": psnr_avg,
        "ssim_all": ssim_all,
        "vmaf": quality_metrics.get("vmaf"),
        "summary": _build_comparison_summary(psnr_avg, ssim_all, size_change_pct),
        "generated_at": time.time(),
        "serial_mode": serial_mode,
    }
    if speedup is not None:
        report["actual_speedup"] = round(speedup, 3)
    return report


def run_serial_baseline_with_progress(
    input_path: str,
    output_path: str,
    filter_chain: str,
    total_duration: float,
    progress_callback=None,
) -> float:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        filter_chain,
        "-threads",
        "1",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        "-progress",
        "pipe:1",
        "-nostats",
        "-loglevel",
        "error",
        output_path,
    ]
    start = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if progress_callback:
        progress_callback(0)

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "out_time_ms":
            try:
                out_time_seconds = int(value) / 1_000_000
            except ValueError:
                continue
            if total_duration > 0 and progress_callback:
                progress_callback(int(min(100, max(0, (out_time_seconds / total_duration) * 100))))
        elif key == "progress" and value == "end" and progress_callback:
            progress_callback(100)

    return_code = proc.wait()
    elapsed = time.perf_counter() - start
    if return_code != 0:
        err = proc.stderr.read() if proc.stderr else "Serial baseline failed"
        raise RuntimeError(err.strip() or "Serial baseline failed")
    return elapsed


def _set_job_progress(job: Dict[str, Any], phase: str, progress: Optional[int] = None) -> None:
    phase_base = {
        "queued": 0,
        "analyzing": 5,
        "extracting": 15,
        "benchmarking": 30,
        "planning": 45,
        "parallel": 55,
        "merging": 95,
        "completed": 100,
    }
    job["phase"] = phase
    if progress is not None:
        job["progress"] = progress
        return
    job["progress"] = phase_base.get(phase, job.get("progress", 0))


def _build_segment_records(
    input_path: str,
    partition_plan,
    feature_result,
    actual_chunk_runtime: List[Dict[str, Any]],
    workers: int,
) -> List[Dict[str, Any]]:
    lookup = {segment.segment_id: segment for segment in feature_result.segment_features}
    records: List[Dict[str, Any]] = []
    for chunk_record in actual_chunk_runtime:
        chunk = partition_plan.chunks[chunk_record["chunk_id"]]
        for segment_id in chunk.source_segment_ids:
            segment = lookup.get(segment_id)
            if segment is None:
                continue
            payload = asdict(segment)
            payload.update(
                {
                    "input_file": input_path,
                    "partition_policy": partition_plan.policy,
                    "worker_count": workers,
                    "chunk_id": chunk_record["chunk_id"],
                    "actual_chunk_runtime": chunk_record["elapsed"],
                }
            )
            records.append(payload)
    return records


def run_render_task(
    job_id: str,
    input_path: str,
    workers: int,
    filter_chain: str,
    smart_mode: bool,
    engine_version: str,
    strict_benchmark: bool,
) -> None:
    global GLOBAL_STATS

    job = JOBS[job_id]
    job["status"] = "processing"
    _set_job_progress(job, "analyzing")
    job["serial_progress"] = 0
    job["parallel_progress"] = 0

    job_temp = ensure_dir(TEMP_BASE / job_id)
    output_path = OUTPUT_DIR / f"output_{job_id}.mp4"
    serial_output_path = OUTPUT_DIR / f"serial_{job_id}.mp4"
    record_path = RECORD_DIR / f"job_{job_id}.json"

    serial_baseline_time: Optional[float] = None
    projected_serial_time: Optional[float] = None
    serial_sample_time: Optional[float] = None

    try:
        probe_start = time.perf_counter()
        metadata = analyze_video(input_path)
        probe_time = time.perf_counter() - probe_start
        job["metadata"] = asdict(metadata)

        partition_policy = job.get("partition_policy") or "equal-duration"
        requested_chunk_count = job.get("chunk_count")
        scheduler_enabled = bool(job.get("scheduler_enabled"))
        scheduler_workers = job.get("scheduler_workers") or list(DEFAULT_SCHEDULER_WORKERS)
        scheduler_chunk_multipliers = job.get("scheduler_chunk_multipliers") or list(DEFAULT_CHUNK_MULTIPLIERS)

        if smart_mode:
            if engine_version == "v2" and V2_AVAILABLE:
                smart_conf = get_content_aware_config(metadata, workers, input_path)
            else:
                smart_conf = get_smart_config(metadata, workers)
            workers = int(smart_conf["workers"])
            filter_chain = str(smart_conf["filter"])
            partition_policy = str(smart_conf.get("partition_policy", "heuristic-adaptive"))
            scheduler_enabled = bool(smart_conf.get("scheduler_enabled", True))
            job["smart_config"] = smart_conf

        job["workers"] = workers
        job["filter_chain"] = filter_chain
        job["partition_policy"] = partition_policy
        job["scheduler_enabled"] = scheduler_enabled

        _set_job_progress(job, "extracting")
        feature_result = extract_video_features(
            input_path=input_path,
            enable_encode_time_proxy=bool(job.get("enable_encode_proxy")),
        )
        job["feature_summary"] = {
            "sample_fps": feature_result.sample_fps,
            "sample_width": feature_result.sample_width,
            "sample_height": feature_result.sample_height,
            "analysis_window_seconds": feature_result.analysis_window_seconds,
            "total_sample_frames": feature_result.total_sample_frames,
            "global_features": feature_result.global_features,
        }

        _set_job_progress(job, "benchmarking")
        if strict_benchmark:
            serial_baseline_time = run_serial_baseline_with_progress(
                input_path=input_path,
                output_path=str(serial_output_path),
                filter_chain=filter_chain,
                total_duration=metadata.duration,
                progress_callback=lambda value: (
                    job.__setitem__("serial_progress", value),
                    job.__setitem__("progress", 30 + int(value * 0.15)),
                ),
            )
            projected_serial_time = serial_baseline_time
            job["serial_output"] = _public_path(serial_output_path)
            job["serial_actual_time"] = _format_seconds(serial_baseline_time)
            job["projected_serial_time"] = _format_seconds(serial_baseline_time)
        else:
            serial_sample_time = benchmark_serial_sample(input_path, str(job_temp), filter_chain)
            benchmark_duration = min(2.0, metadata.duration)
            projected_serial_time = (metadata.duration / max(benchmark_duration, 1e-6)) * serial_sample_time
            job["projected_serial_time"] = _format_seconds(projected_serial_time)
            job["serial_progress"] = 100

        _set_job_progress(job, "planning")
        selection_result = None
        scheduler_time = 0.0
        if scheduler_enabled:
            scheduler_start = time.perf_counter()
            selection_result = search_best_configuration(
                input_path=input_path,
                metadata=metadata,
                feature_result=feature_result,
                filter_chain=filter_chain,
                temp_dir=str(job_temp),
                workers=scheduler_workers,
                chunk_multipliers=scheduler_chunk_multipliers,
                partition_policy=partition_policy,
                serial_sample_time=serial_sample_time,
                measured_overheads={
                    "probe": probe_time,
                    "feature": feature_result.extraction_time,
                },
            )
            scheduler_time = time.perf_counter() - scheduler_start
            workers = selection_result.selected.worker_count
            selected_chunk_count = selection_result.selected.chunk_count
            job["workers"] = workers
            job["selection"] = asdict(selection_result)
        else:
            selected_chunk_count = requested_chunk_count or max(1, workers)

        partition_plan = build_partition_plan(
            input_path=input_path,
            metadata=metadata,
            temp_dir=str(job_temp),
            policy=partition_policy,
            num_chunks=1 if partition_policy == "serial" else selected_chunk_count,
            feature_result=feature_result,
            estimated_total_runtime=(
                selection_result.estimated_serial_time
                if selection_result is not None
                else (projected_serial_time or metadata.duration)
            ),
        )
        job["chunk_count"] = len(partition_plan.chunks)
        job["planning_rationale"] = list(partition_plan.rationale)
        job["predicted_chunk_costs"] = (
            list(selection_result.selected.estimated_chunk_costs)
            if selection_result is not None
            else [float(chunk.estimated_cost or 0.0) for chunk in partition_plan.chunks]
        )
        job["planned_chunk_boundaries"] = [
            {
                "chunk_id": chunk.chunk_id,
                "start": chunk.start,
                "duration": chunk.duration,
                "estimated_cost": chunk.estimated_cost,
                "rationale": chunk.rationale,
            }
            for chunk in partition_plan.chunks
        ]

        execution_started = time.perf_counter()

        def phase_callback(phase: str) -> None:
            _set_job_progress(job, phase)

        def progress_callback(value: int) -> None:
            job["parallel_progress"] = value
            if job.get("phase") == "parallel":
                job["progress"] = min(95, 55 + int(value * 0.4))

        execution = execute_partition_plan(
            partition_plan=partition_plan,
            output_path=str(output_path),
            workers=workers,
            filter_chain=filter_chain,
            temp_dir=str(job_temp),
            progress_callback=progress_callback,
            phase_callback=phase_callback,
        )
        total_runtime = time.perf_counter() - execution_started

        quality_metrics = evaluate_output(
            input_path=input_path,
            output_path=str(output_path),
            sample_seconds=min(8.0, metadata.duration),
            enable_vmaf=bool(job.get("enable_vmaf")),
        )
        baseline_time = serial_baseline_time or projected_serial_time
        speedup = (baseline_time / total_runtime) if baseline_time and total_runtime > 0 else None
        efficiency = (speedup / workers) if speedup is not None and workers > 0 else None
        throughput = (metadata.duration / total_runtime) if total_runtime > 0 else None

        overheads = {
            "probe": probe_time,
            "feature": feature_result.extraction_time,
            "benchmark": serial_baseline_time or serial_sample_time or 0.0,
            "scheduler": scheduler_time,
            "partition": partition_plan.planning_time,
            "dispatch": execution["dispatch_time"],
            "merge": execution["merge_time"],
        }
        decision_cost = {
            "T_metadata": probe_time,
            "T_features": feature_result.extraction_time,
            "T_scheduler": scheduler_time,
            "T_decide": probe_time + feature_result.extraction_time + scheduler_time,
            "T_execute": total_runtime,
            "rho": ((probe_time + feature_result.extraction_time + scheduler_time) / total_runtime) if total_runtime > 0 else None,
        }
        performance = {
            "throughput": throughput,
            "speedup_vs_serial": speedup,
            "efficiency": efficiency,
            "chunk_imbalance_ratio": execution["straggler_ratio"],
            "straggler_ratio": execution["straggler_ratio"],
            "predicted_total_time": selection_result.selected.predicted_e2e_time if selection_result else None,
            "prediction_error": (
                abs(selection_result.selected.predicted_e2e_time - total_runtime)
                if selection_result is not None
                else None
            ),
        }
        comparison_report = build_comparison_report(
            quality_metrics=quality_metrics,
            sample_seconds=min(8.0, metadata.duration),
            speedup=speedup,
            serial_mode="full" if strict_benchmark else "projected",
        )

        actual_chunk_runtime = execution["results"]
        segment_records = _build_segment_records(
            input_path=input_path,
            partition_plan=partition_plan,
            feature_result=feature_result,
            actual_chunk_runtime=actual_chunk_runtime,
            workers=workers,
        )
        record = {
            "started_at": job["created_at"],
            "input_file": input_path,
            "video_id": Path(input_path).stem,
            "metadata": asdict(metadata),
            "feature_summary": job["feature_summary"],
            "partition_policy": partition_plan.policy,
            "worker_count": workers,
            "chunk_count": len(partition_plan.chunks),
            "planned_chunk_boundaries": job["planned_chunk_boundaries"],
            "planning_rationale": job["planning_rationale"],
            "predicted_chunk_costs": job["predicted_chunk_costs"],
            "actual_chunk_runtime": actual_chunk_runtime,
            "overheads": overheads,
            "decision_cost": decision_cost,
            "runtime": {
                "serial_sample_time": serial_sample_time,
                "projected_serial_time": projected_serial_time,
                "serial_baseline_time": serial_baseline_time,
                "actual_total_time": total_runtime,
            },
            "performance": performance,
            "quality": quality_metrics,
            "selection": asdict(selection_result) if selection_result is not None else None,
            "segment_records": segment_records,
            "api_job_id": job_id,
        }
        write_record(record, str(record_path))
        API_METRICS_LOGGER.log_run(record)
        API_METRICS_LOGGER.log_segments(segment_records)

        job["status"] = "completed"
        _set_job_progress(job, "completed")
        job["output"] = _public_path(output_path)
        job["duration"] = _format_seconds(total_runtime)
        job["comparison_report"] = comparison_report
        job["quality_metrics"] = quality_metrics
        job["actual_chunk_runtime"] = actual_chunk_runtime
        job["overheads"] = overheads
        job["decision_cost"] = decision_cost
        job["performance"] = performance
        job["experiment_record_path"] = _public_path(record_path)

        GLOBAL_STATS["successful_jobs"] += 1
        GLOBAL_STATS["total_processing_time"] += total_runtime
        GLOBAL_STATS["total_frames_processed"] += int(metadata.duration * metadata.fps)

    except Exception as exc:
        job["status"] = "failed"
        _set_job_progress(job, "completed", progress=max(job.get("progress", 0), 0))
        job["error"] = str(exc)
        GLOBAL_STATS["failed_jobs"] += 1
        print(f"Job {job_id} failed: {exc}", flush=True)
        import traceback

        traceback.print_exc()
    finally:
        if job_temp.exists():
            shutil.rmtree(job_temp)


@app.get("/stats", response_model=ClusterStats)
async def get_cluster_stats():
    mem = psutil.virtual_memory()
    active = sum(1 for job in JOBS.values() if job["status"] == "processing")
    queued = sum(1 for job in JOBS.values() if job["status"] == "queued")
    completed = sum(1 for job in JOBS.values() if job["status"] == "completed")
    failed = sum(1 for job in JOBS.values() if job["status"] == "failed")
    total = len(JOBS)

    avg_fps = (
        GLOBAL_STATS["total_frames_processed"] / GLOBAL_STATS["total_processing_time"]
        if GLOBAL_STATS["total_processing_time"] > 0
        else 0.0
    )
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
        v2_available=V2_AVAILABLE,
    )


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {allowed_extensions}")

    file_id = str(uuid.uuid4())[:8]
    filename = f"{file_id}_{file.filename}"
    filepath = (UPLOAD_DIR / filename).resolve()

    size_bytes = 0
    chunk_size = 1024 * 1024
    with open(filepath, "wb") as out_file:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size_bytes += len(chunk)
            out_file.write(chunk)
    await file.close()

    return {
        "filename": filename,
        "path": str(filepath.relative_to(PROJECT_ROOT)),
        "size_mb": round(size_bytes / (1024 * 1024), 2),
    }


@app.post("/jobs", response_model=JobStatus)
async def create_job(job_req: JobCreate, background_tasks: BackgroundTasks):
    resolved_input_path = resolve_input_path(job_req.input_path)

    engine_version = job_req.engine_version or "v1"
    if engine_version == "v2" and not V2_AVAILABLE:
        raise HTTPException(status_code=400, detail="V2 engine not available")

    workers = job_req.workers or os.cpu_count() or 4
    if workers < 1:
        raise HTTPException(status_code=400, detail="workers must be >= 1")

    partition_policy = job_req.partition_policy or ("heuristic-adaptive" if job_req.smart else "equal-duration")
    scheduler_enabled = (
        bool(job_req.scheduler_enabled)
        if job_req.scheduler_enabled is not None
        else bool(job_req.smart)
    )

    job_id = str(uuid.uuid4())[:8]
    input_display_path = str(resolved_input_path.relative_to(PROJECT_ROOT))
    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "phase": "queued",
        "progress": 0,
        "input": input_display_path,
        "workers": workers,
        "filter_chain": job_req.filter_chain or "unsharp=5:5:1.5:5:5:0.5",
        "serial_actual_time": None,
        "serial_progress": 0,
        "serial_output": None,
        "parallel_progress": 0,
        "created_at": time.time(),
        "smart_config": None,
        "comparison_report": None,
        "engine_version": engine_version,
        "strict_benchmark": bool(job_req.strict_benchmark),
        "partition_policy": partition_policy,
        "chunk_count": job_req.chunk_count,
        "scheduler_enabled": scheduler_enabled,
        "scheduler_workers": job_req.scheduler_workers or list(DEFAULT_SCHEDULER_WORKERS),
        "scheduler_chunk_multipliers": job_req.scheduler_chunk_multipliers or list(DEFAULT_CHUNK_MULTIPLIERS),
        "enable_encode_proxy": bool(job_req.enable_encode_proxy),
        "enable_vmaf": bool(job_req.enable_vmaf),
        "planned_chunk_boundaries": None,
        "predicted_chunk_costs": None,
        "planning_rationale": None,
        "actual_chunk_runtime": None,
        "overheads": None,
        "decision_cost": None,
        "performance": None,
        "selection": None,
        "feature_summary": None,
        "quality_metrics": None,
        "experiment_record_path": None,
        "metadata": None,
    }

    GLOBAL_STATS["total_jobs"] += 1
    background_tasks.add_task(
        run_render_task,
        job_id,
        str(resolved_input_path),
        workers,
        JOBS[job_id]["filter_chain"],
        bool(job_req.smart),
        engine_version,
        bool(job_req.strict_benchmark),
    )
    return JOBS[job_id]


@app.get("/jobs", response_model=List[JobStatus])
async def list_jobs():
    return sorted(JOBS.values(), key=lambda item: item.get("created_at", 0), reverse=True)


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
    files = []
    for file_path in UPLOAD_DIR.iterdir():
        if file_path.is_file():
            files.append(
                {
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(PROJECT_ROOT)),
                    "size_mb": round(os.path.getsize(file_path) / (1024 * 1024), 2),
                }
            )
    return sorted(files, key=lambda item: item["filename"], reverse=True)


@app.get("/files/{file_path:path}")
async def get_source_file(file_path: str):
    resolved = resolve_input_path(file_path)
    media_type, _ = mimetypes.guess_type(str(resolved))
    return FileResponse(str(resolved), media_type=media_type or "application/octet-stream")


app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


if __name__ == "__main__":
    import uvicorn

    try:
        print("=" * 60, flush=True)
        print("  Distributed Video Engine Research API v2.1", flush=True)
        print("  Baseline Engine: Available", flush=True)
        print(f"  Adaptive Compatibility Engine: {'Available' if V2_AVAILABLE else 'Not Found'}", flush=True)
        print("=" * 60, flush=True)
        print("Starting on http://0.0.0.0:8000", flush=True)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as exc:
        print(f"CRITICAL SERVER ERROR: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
