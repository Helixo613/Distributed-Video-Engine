from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from video_types import ChunkResult, ChunkTask, VideoMetadata


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
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = map(int, fps_str.split("/"))
        fps = num / den if den else 30.0
    else:
        fps = float(fps_str)

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
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "copy",
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
        "-i",
        input_path,
        "-t",
        str(sample_seconds),
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
        sample_output,
    ]
    start_time = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start_time


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
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        output_path,
    ]
    start_time = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start_time


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
