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


def evaluate_output(
    input_path: str,
    output_path: str,
    sample_seconds: float,
    enable_vmaf: bool = False,
) -> dict[str, Optional[float] | str]:
    """Compute basic output quality and size metrics for experiment logging."""
    input_meta = analyze_video(input_path)
    output_meta = analyze_video(output_path)
    input_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    size_change_pct = ((output_size_mb - input_size_mb) / input_size_mb * 100.0) if input_size_mb > 0 else 0.0

    psnr_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "info",
        "-t",
        f"{sample_seconds:.2f}",
        "-i",
        input_path,
        "-t",
        f"{sample_seconds:.2f}",
        "-i",
        output_path,
        "-lavfi",
        "[0:v][1:v]psnr",
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
        f"{sample_seconds:.2f}",
        "-i",
        input_path,
        "-t",
        f"{sample_seconds:.2f}",
        "-i",
        output_path,
        "-lavfi",
        "[0:v][1:v]ssim",
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
            f"{sample_seconds:.2f}",
            "-i",
            input_path,
            "-t",
            f"{sample_seconds:.2f}",
            "-i",
            output_path,
            "-lavfi",
            "[0:v][1:v]libvmaf",
            "-f",
            "null",
            "-",
        ]
        vmaf_score = _try_metric(vmaf_cmd, r"VMAF score: ([0-9.]+)")

    return {
        "input_bitrate": input_meta.bitrate,
        "output_bitrate": output_meta.bitrate,
        "input_size_mb": round(input_size_mb, 3),
        "output_size_mb": round(output_size_mb, 3),
        "size_change_pct": round(size_change_pct, 3),
        "psnr": round(psnr_avg, 4) if psnr_avg is not None else None,
        "ssim": round(ssim_all, 6) if ssim_all is not None else None,
        "vmaf": round(vmaf_score, 4) if vmaf_score is not None else None,
    }
