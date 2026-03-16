from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised in environments without numpy
    np = None

from ffmpeg_utils import analyze_video
from video_types import FeatureExtractionResult, SegmentFeature, VideoMetadata


def _effective_sample_fps(duration: float, requested_fps: float, max_samples: int) -> float:
    if duration <= 0:
        return requested_fps
    return max(0.2, min(requested_fps, max_samples / duration))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _sample_frames(input_path: str, sample_fps: float, width: int, height: int):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-vf",
        f"fps={sample_fps},scale={width}:{height}:flags=fast_bilinear,format=gray",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    run = subprocess.run(cmd, capture_output=True, check=True)
    frame_bytes = width * height
    if frame_bytes == 0 or not run.stdout:
        if np is not None:
            return np.empty((0, height, width), dtype=np.uint8)
        return []
    usable = len(run.stdout) // frame_bytes
    if usable == 0:
        if np is not None:
            return np.empty((0, height, width), dtype=np.uint8)
        return []
    raw = run.stdout[: usable * frame_bytes]
    if np is not None:
        data = np.frombuffer(raw, dtype=np.uint8)
        return data.reshape((usable, height, width))
    return [raw[index * frame_bytes : (index + 1) * frame_bytes] for index in range(usable)]


def _encode_time_proxy(input_path: str, seconds: float) -> Optional[float]:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        proxy_output = handle.name
    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-t",
            str(seconds),
            "-i",
            input_path,
            "-vf",
            "scale=160:-2",
            "-threads",
            "1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            proxy_output,
        ]
        start_time = time.perf_counter()
        subprocess.run(cmd, capture_output=True, check=True)
        return time.perf_counter() - start_time
    except Exception:
        return None
    finally:
        Path(proxy_output).unlink(missing_ok=True)


def _segment_complexity(
    duration: float,
    resolution_factor: float,
    bpp: Optional[float],
    motion_proxy: float,
    scene_change_ratio: float,
    luma_variance: float,
    texture_proxy: float,
) -> float:
    motion_term = motion_proxy / 255.0
    variance_term = luma_variance / (255.0 * 255.0)
    texture_term = texture_proxy / 255.0
    bpp_term = min(2.0, (bpp or 0.1) / 0.1)
    complexity_multiplier = (
        0.45
        + 0.25 * motion_term
        + 0.15 * scene_change_ratio
        + 0.10 * variance_term
        + 0.05 * texture_term
    )
    return max(1e-6, duration * resolution_factor * complexity_multiplier * (0.8 + 0.2 * bpp_term))


def extract_video_features(
    input_path: str,
    sample_fps: float = 2.0,
    sample_width: int = 96,
    sample_height: int = 54,
    max_samples: int = 600,
    max_segments: int = 60,
    enable_encode_time_proxy: bool = False,
    output_path: str | None = None,
) -> FeatureExtractionResult:
    """
    Compute low-cost complexity features from a video by sampling low-resolution grayscale frames.
    """
    start_time = time.perf_counter()
    metadata = analyze_video(input_path)
    eff_sample_fps = _effective_sample_fps(metadata.duration, sample_fps, max_samples)
    frames = _sample_frames(input_path, eff_sample_fps, sample_width, sample_height)

    if np is not None:
        total_frames = int(frames.shape[0])
        if total_frames:
            frame_var = frames.var(axis=(1, 2))
            texture_proxy = (
                np.abs(np.diff(frames.astype(np.float32), axis=2)).mean(axis=(1, 2))
                + np.abs(np.diff(frames.astype(np.float32), axis=1)).mean(axis=(1, 2))
            ) / 2.0
            frame_diffs = np.abs(np.diff(frames.astype(np.float32), axis=0)).mean(axis=(1, 2))
            motion_values = np.concatenate(([0.0], frame_diffs))
        else:
            frame_var = np.array([])
            texture_proxy = np.array([])
            motion_values = np.array([])
        if motion_values.size:
            threshold = float(motion_values.mean() + motion_values.std())
            scene_events = motion_values > threshold
        else:
            threshold = 0.0
            scene_events = np.array([], dtype=bool)
    else:
        total_frames = len(frames)
        frame_var: list[float] = []
        texture_proxy: list[float] = []
        motion_values: list[float] = []
        previous_frame = None
        pixels_per_frame = sample_width * sample_height
        for frame in frames:
            values = list(frame)
            mean_value = sum(values) / max(1, pixels_per_frame)
            variance = sum((value - mean_value) ** 2 for value in values) / max(1, pixels_per_frame)
            frame_var.append(variance)

            horiz_diffs = 0.0
            horiz_count = 0
            vert_diffs = 0.0
            vert_count = 0
            for row in range(sample_height):
                row_start = row * sample_width
                for col in range(1, sample_width):
                    horiz_diffs += abs(values[row_start + col] - values[row_start + col - 1])
                    horiz_count += 1
            for row in range(1, sample_height):
                row_start = row * sample_width
                prev_row_start = (row - 1) * sample_width
                for col in range(sample_width):
                    vert_diffs += abs(values[row_start + col] - values[prev_row_start + col])
                    vert_count += 1
            texture_proxy.append(((horiz_diffs / max(1, horiz_count)) + (vert_diffs / max(1, vert_count))) / 2.0)

            if previous_frame is None:
                motion_values.append(0.0)
            else:
                diff = sum(abs(current - previous) for current, previous in zip(values, previous_frame)) / max(
                    1, pixels_per_frame
                )
                motion_values.append(diff)
            previous_frame = values

        threshold = _mean(motion_values) + _std(motion_values)
        scene_events = [value > threshold for value in motion_values]

    resolution_factor = max(1e-6, metadata.pixel_count / float(1920 * 1080))
    bitrate = metadata.bitrate
    bpp = None
    if bitrate and metadata.fps > 0 and metadata.pixel_count > 0:
        bpp = bitrate / (metadata.pixel_count * metadata.fps)

    target_segments = min(max_segments, max(1, math.ceil(metadata.duration))) if metadata.duration > 0 else 1
    analysis_window_seconds = metadata.duration / target_segments if target_segments else metadata.duration
    analysis_window_seconds = max(1.0, analysis_window_seconds or 1.0)

    segment_features: list[SegmentFeature] = []
    for segment_id in range(target_segments):
        start = segment_id * analysis_window_seconds
        end = metadata.duration if segment_id == target_segments - 1 else min(metadata.duration, start + analysis_window_seconds)
        duration = max(0.001, end - start)

        if total_frames:
            start_frame = min(total_frames, int(start * eff_sample_fps))
            end_frame = min(total_frames, max(start_frame + 1, int(math.ceil(end * eff_sample_fps))))
            if np is not None:
                indices = slice(start_frame, end_frame)
                samples = motion_values[indices]
                scenes = scene_events[indices]
                vars_ = frame_var[indices]
                textures = texture_proxy[indices]
            else:
                samples = motion_values[start_frame:end_frame]
                scenes = scene_events[start_frame:end_frame]
                vars_ = frame_var[start_frame:end_frame]
                textures = texture_proxy[start_frame:end_frame]
            sample_count = int(max(0, end_frame - start_frame))
            if np is not None:
                motion_proxy = float(samples.mean()) if sample_count else 0.0
                scene_change_ratio = float(scenes.mean()) if sample_count else 0.0
                luma_variance = float(vars_.mean()) if sample_count else 0.0
                texture_value = float(textures.mean()) if sample_count else 0.0
            else:
                motion_proxy = _mean(samples) if sample_count else 0.0
                scene_change_ratio = (_mean([1.0 if item else 0.0 for item in scenes])) if sample_count else 0.0
                luma_variance = _mean(vars_) if sample_count else 0.0
                texture_value = _mean(textures) if sample_count else 0.0
        else:
            sample_count = 0
            motion_proxy = 0.0
            scene_change_ratio = 0.0
            luma_variance = 0.0
            texture_value = 0.0

        complexity = _segment_complexity(
            duration=duration,
            resolution_factor=resolution_factor,
            bpp=bpp,
            motion_proxy=motion_proxy,
            scene_change_ratio=scene_change_ratio,
            luma_variance=luma_variance,
            texture_proxy=texture_value,
        )
        segment_features.append(
            SegmentFeature(
                segment_id=segment_id,
                start=round(start, 6),
                end=round(end, 6),
                duration=round(duration, 6),
                sample_count=sample_count,
                bitrate=bitrate,
                bpp=bpp,
                motion_proxy=motion_proxy,
                scene_change_ratio=scene_change_ratio,
                luma_variance=luma_variance,
                texture_proxy=texture_value,
                estimated_complexity=complexity,
            )
        )

    encode_proxy = _encode_time_proxy(input_path, min(3.0, metadata.duration)) if enable_encode_time_proxy else None
    extraction_time = time.perf_counter() - start_time
    global_features = {
        "duration": metadata.duration,
        "width": metadata.width,
        "height": metadata.height,
        "fps": metadata.fps,
        "bitrate": bitrate,
        "bpp": bpp,
        "scene_change_proxy": float(scene_events.mean()) if np is not None and scene_events.size else (
            _mean([1.0 if item else 0.0 for item in scene_events]) if scene_events else 0.0
        ),
        "motion_proxy": float(motion_values.mean()) if np is not None and motion_values.size else (
            _mean(motion_values) if motion_values else 0.0
        ),
        "luma_variance": float(frame_var.mean()) if np is not None and frame_var.size else (
            _mean(frame_var) if frame_var else 0.0
        ),
        "texture_proxy": float(texture_proxy.mean()) if np is not None and texture_proxy.size else (
            _mean(texture_proxy) if texture_proxy else 0.0
        ),
        "encode_time_proxy": encode_proxy,
        "analysis_scene_threshold": threshold,
    }
    result = FeatureExtractionResult(
        metadata=metadata,
        extraction_time=extraction_time,
        sample_fps=eff_sample_fps,
        sample_width=sample_width,
        sample_height=sample_height,
        analysis_window_seconds=analysis_window_seconds,
        total_sample_frames=total_frames,
        global_features=global_features,
        segment_features=segment_features,
        encode_time_proxy=encode_proxy,
    )
    if output_path:
        save_feature_summary(result, output_path)
    return result


def save_feature_summary(result: FeatureExtractionResult, output_path: str) -> None:
    payload = asdict(result)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
