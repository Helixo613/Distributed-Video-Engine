from __future__ import annotations

import json
import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from video_types import ChunkResult, ChunkTask, VideoMetadata


def _parse_fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        fps_str = stream.get(key)
        if not fps_str or fps_str in {"0/0", "N/A"}:
            continue
        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            if den:
                return num / den
        else:
            return float(fps_str)
    return 30.0


@lru_cache(maxsize=1)
def _nvenc_available() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    if "h264_nvenc" not in result.stdout:
        return False
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=64x64:rate=1",
                "-frames:v",
                "1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def resolve_execution_backend(requested: str | None = None) -> str:
    """Resolve cpu/cuda/auto to the backend used by FFmpeg commands."""
    raw = (requested or os.getenv("DVE_EXECUTION_BACKEND") or "auto").strip().lower()
    if raw in {"gpu", "cuda", "nvenc"}:
        if not _nvenc_available():
            raise RuntimeError("CUDA/NVENC backend requested, but h264_nvenc is not available in FFmpeg")
        return "cuda"
    if raw == "auto":
        return "cuda" if _nvenc_available() else "cpu"
    if raw != "cpu":
        raise ValueError(f"Unknown execution backend: {requested}")
    return "cpu"


def execution_backend_info(requested: str | None = None) -> dict[str, object]:
    backend = resolve_execution_backend(requested)
    return {
        "requested": requested or os.getenv("DVE_EXECUTION_BACKEND") or "auto",
        "resolved": backend,
        "nvenc_available": _nvenc_available(),
    }


def _common_encode_args(execution_backend: str | None = None) -> list[str]:
    backend = resolve_execution_backend(execution_backend)
    video_args = (
        [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "fast",
            "-cq",
            "23",
            "-pix_fmt",
            "yuv420p",
        ]
        if backend == "cuda"
        else [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ]
    )
    return [
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        *video_args,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
    ]


def analyze_video(input_path: str) -> VideoMetadata:
    """Extract container and primary video stream metadata with ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    video_stream = next((stream for stream in data["streams"] if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError("No video stream found")

    has_audio = any(stream.get("codec_type") == "audio" for stream in data["streams"])
    fps = _parse_fps(video_stream)

    bitrate_raw = data.get("format", {}).get("bit_rate")
    bitrate = float(bitrate_raw) if bitrate_raw not in (None, "N/A") else None

    return VideoMetadata(
        duration=float(data["format"]["duration"]),
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        codec=video_stream.get("codec_name", "unknown"),
        has_audio=has_audio,
        bitrate=bitrate,
        pix_fmt=video_stream.get("pix_fmt"),
    )


def process_chunk(
    task: ChunkTask,
    filter_chain: str,
    threads_per_worker: int = 1,
    execution_backend: str | None = None,
) -> ChunkResult:
    """Process one planned chunk using FFmpeg with single-threaded worker execution."""
    start_time = time.perf_counter()
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(task.start),
        "-i",
        task.input_path,
        "-t",
        str(task.duration),
        "-vf",
        filter_chain,
        *_thread_args(threads_per_worker, execution_backend),
        *_common_encode_args(execution_backend),
        "-reset_timestamps",
        "1",
        "-avoid_negative_ts",
        "make_zero",
        task.output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        elapsed = time.perf_counter() - start_time
        return ChunkResult(
            chunk_id=task.chunk_id,
            success=True,
            elapsed=elapsed,
            return_code=0,
            output_path=task.output_path,
        )
    except subprocess.CalledProcessError as exc:
        elapsed = time.perf_counter() - start_time
        error = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or str(exc))
        return ChunkResult(
            chunk_id=task.chunk_id,
            success=False,
            elapsed=elapsed,
            error=error,
            return_code=exc.returncode,
            output_path=task.output_path,
        )


def _thread_args(threads_per_worker: int, execution_backend: str | None = None) -> list[str]:
    return [] if resolve_execution_backend(execution_backend) == "cuda" else ["-threads", str(max(1, threads_per_worker))]


def merge_chunks(chunk_paths: list[str], output_path: str, temp_dir: str) -> bool:
    """Merge processed chunks using concat demuxer, then fallback to re-encode if needed."""
    concat_file = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as handle:
        for path in chunk_paths:
            handle.write(f"file '{os.path.abspath(path)}'\n")

    fast_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        output_path,
    ]
    try:
        subprocess.run(fast_cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        fallback_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            output_path,
        ]
        try:
            subprocess.run(fallback_cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


def benchmark_serial_sample(
    input_path: str,
    temp_dir: str,
    filter_chain: str,
    sample_seconds: float = 2.0,
    execution_backend: str | None = None,
) -> float:
    """Encode a short clip to estimate single-worker runtime."""
    sample_output = os.path.join(temp_dir, "serial_sample.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "0",
        "-i",
        input_path,
        "-t",
        str(sample_seconds),
        "-vf",
        filter_chain,
        *_thread_args(1, execution_backend),
        *_common_encode_args(execution_backend),
        sample_output,
    ]
    start_time = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start_time


def benchmark_serial_profile(
    input_path: str,
    temp_dir: str,
    filter_chain: str,
    duration: float,
    sample_seconds: float = 2.0,
    sample_fractions: list[float] | None = None,
    execution_backend: str | None = None,
) -> dict[str, float | list[float]]:
    """Benchmark several short serial samples to reduce scheduler bias from a single easy clip."""
    fractions = sample_fractions or [0.1, 0.5, 0.9]
    effective_seconds = min(sample_seconds, max(duration, 0.0))
    if effective_seconds <= 0.0:
        return {
            "sample_seconds": 0.0,
            "positions": [0.0],
            "samples": [0.0],
            "mean_time": 0.0,
            "max_time": 0.0,
        }

    max_start = max(duration - effective_seconds, 0.0)
    positions = sorted({round(min(max_start, max(0.0, fraction * max_start)), 3) for fraction in fractions})
    if not positions:
        positions = [0.0]

    samples: list[float] = []
    for index, start_offset in enumerate(positions):
        sample_output = os.path.join(temp_dir, f"serial_sample_{index}.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_offset),
            "-i",
            input_path,
            "-t",
            str(effective_seconds),
            "-vf",
            filter_chain,
            *_thread_args(1, execution_backend),
            *_common_encode_args(execution_backend),
            sample_output,
        ]
        start_time = time.perf_counter()
        subprocess.run(cmd, capture_output=True, check=True)
        samples.append(time.perf_counter() - start_time)

    mean_time = sum(samples) / max(1, len(samples))
    return {
        "sample_seconds": effective_seconds,
        "positions": positions,
        "samples": samples,
        "mean_time": mean_time,
        "max_time": max(samples, default=0.0),
    }


def run_serial_baseline(
    input_path: str,
    output_path: str,
    filter_chain: str,
    execution_backend: str | None = None,
) -> float:
    """Encode the full video serially for a baseline measurement."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        filter_chain,
        *_thread_args(1, execution_backend),
        *_common_encode_args(execution_backend),
        output_path,
    ]
    start_time = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start_time


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
