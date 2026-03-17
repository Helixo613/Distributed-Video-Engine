from __future__ import annotations

import json
import os
import subprocess
import time
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


def _common_encode_args() -> list[str]:
    return [
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
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


def process_chunk(task: ChunkTask, filter_chain: str, threads_per_worker: int = 1) -> ChunkResult:
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
        "-threads",
        str(max(1, threads_per_worker)),
        *_common_encode_args(),
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


def benchmark_serial_sample(input_path: str, temp_dir: str, filter_chain: str, sample_seconds: float = 2.0) -> float:
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
        "-threads",
        "1",
        *_common_encode_args(),
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
            "-threads",
            "1",
            *_common_encode_args(),
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


def run_serial_baseline(input_path: str, output_path: str, filter_chain: str) -> float:
    """Encode the full video serially for a baseline measurement."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        filter_chain,
        "-threads",
        "1",
        *_common_encode_args(),
        output_path,
    ]
    start_time = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start_time


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
