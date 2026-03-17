from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from ffmpeg_utils import analyze_video


def _parse_metric(stderr: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, stderr)
    return float(match.group(1)) if match else None


def _try_metric(cmd: list[str], pattern: str) -> Optional[float]:
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return _parse_metric(run.stderr, pattern)
    except Exception:
        return None


def _metric_filter(metric_name: str) -> str:
    return f"[0:v]setpts=PTS-STARTPTS[ref];[1:v]setpts=PTS-STARTPTS[test];[ref][test]{metric_name}"


def _compute_quality_metrics(
    reference_path: str,
    output_path: str,
    compare_seconds: float,
    enable_vmaf: bool,
) -> dict[str, Optional[float]]:
    psnr_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "info",
        "-t",
        f"{compare_seconds:.2f}",
        "-i",
        reference_path,
        "-t",
        f"{compare_seconds:.2f}",
        "-i",
        output_path,
        "-lavfi",
        _metric_filter("psnr"),
        "-f",
        "null",
        "-",
    ]
    ssim_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "info",
        "-t",
        f"{compare_seconds:.2f}",
        "-i",
        reference_path,
        "-t",
        f"{compare_seconds:.2f}",
        "-i",
        output_path,
        "-lavfi",
        _metric_filter("ssim"),
        "-f",
        "null",
        "-",
    ]
    psnr_avg = _try_metric(psnr_cmd, r"average:([0-9.]+)")
    ssim_all = _try_metric(ssim_cmd, r"All:([0-9.]+)")

    vmaf_score = None
    if enable_vmaf:
        vmaf_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "info",
            "-t",
            f"{compare_seconds:.2f}",
            "-i",
            reference_path,
            "-t",
            f"{compare_seconds:.2f}",
            "-i",
            output_path,
            "-lavfi",
            _metric_filter("libvmaf"),
            "-f",
            "null",
            "-",
        ]
        vmaf_score = _try_metric(vmaf_cmd, r"VMAF score: ([0-9.]+)")

    return {
        "psnr": round(psnr_avg, 4) if psnr_avg is not None else None,
        "ssim": round(ssim_all, 6) if ssim_all is not None else None,
        "vmaf": round(vmaf_score, 4) if vmaf_score is not None else None,
    }


def evaluate_output(
    input_path: str,
    output_path: str,
    sample_seconds: float,
    enable_vmaf: bool = False,
    reference_path: Optional[str] = None,
    reference_label: str = "input",
) -> dict[str, Optional[float] | str | bool]:
    """Compute fair output quality and metadata metrics against a chosen reference output."""
    reference_path = reference_path or input_path
    reference_meta = analyze_video(reference_path)
    output_meta = analyze_video(output_path)

    compare_seconds = min(sample_seconds, reference_meta.duration, output_meta.duration)
    reference_size_mb = os.path.getsize(reference_path) / (1024 * 1024)
    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    size_change_pct = ((output_size_mb - reference_size_mb) / reference_size_mb * 100.0) if reference_size_mb > 0 else 0.0
    reference_metrics = _compute_quality_metrics(reference_path, output_path, compare_seconds, enable_vmaf)
    input_compare_seconds = min(sample_seconds, analyze_video(input_path).duration, output_meta.duration)
    input_metrics = (
        _compute_quality_metrics(input_path, output_path, input_compare_seconds, enable_vmaf)
        if os.path.abspath(reference_path) != os.path.abspath(input_path)
        else reference_metrics
    )

    return {
        "reference_path": reference_path,
        "reference_label": reference_label,
        "comparison_seconds": round(compare_seconds, 3),
        "reference_bitrate": reference_meta.bitrate,
        "output_bitrate": output_meta.bitrate,
        "reference_size_mb": round(reference_size_mb, 3),
        "output_size_mb": round(output_size_mb, 3),
        "size_change_pct": round(size_change_pct, 3),
        "reference_duration": round(reference_meta.duration, 6),
        "output_duration": round(output_meta.duration, 6),
        "duration_delta": round(output_meta.duration - reference_meta.duration, 6),
        "reference_width": reference_meta.width,
        "reference_height": reference_meta.height,
        "output_width": output_meta.width,
        "output_height": output_meta.height,
        "reference_fps": round(reference_meta.fps, 6),
        "output_fps": round(output_meta.fps, 6),
        "resolution_match": reference_meta.width == output_meta.width and reference_meta.height == output_meta.height,
        "psnr": reference_metrics["psnr"],
        "ssim": reference_metrics["ssim"],
        "vmaf": reference_metrics["vmaf"],
        "input_comparison_seconds": round(input_compare_seconds, 3),
        "input_psnr": input_metrics["psnr"],
        "input_ssim": input_metrics["ssim"],
        "input_vmaf": input_metrics["vmaf"],
    }
