#!/usr/bin/env python3
"""
Legacy V2 compatibility layer.

The original V2 path is preserved as a thin wrapper so existing callers keep working,
while the underlying project is reframed around research-oriented feature extraction
and adaptive scheduling rather than "smart AI" branding.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from feature_extractor import extract_video_features
from render_engine import main as research_main
from video_types import VideoMetadata


def get_content_aware_config(metadata: VideoMetadata, max_cpu: int, input_path: str) -> dict:
    """
    Backward-compatible adaptive configuration hook for callers that still expect the old V2 API.
    """
    features = extract_video_features(input_path)
    bpp = features.global_features.get("bpp") or 0.1
    motion = features.global_features.get("motion_proxy", 0.0)

    workers = min(max_cpu, 8) if metadata.pixel_count > 3000000 else max_cpu
    filter_chain = "unsharp=5:5:1.5:5:5:0.5"
    reason = f"Adaptive feature analysis selected a detail-preserving filter (bpp={bpp:.3f}, motion={motion:.2f})."
    if bpp < 0.05:
        filter_chain = "hqdn3d=10:10:10:10"
        reason = f"Adaptive feature analysis selected denoising for low bitrate content (bpp={bpp:.3f})."
    elif motion > 32.0:
        filter_chain = "eq=contrast=1.05:saturation=1.1,unsharp=3:3:0.5"
        reason = f"Adaptive feature analysis selected a mild enhancement chain for higher-motion content (motion={motion:.2f})."

    return {
        "workers": workers,
        "filter": filter_chain,
        "partition_policy": "heuristic-adaptive",
        "scheduler_enabled": True,
        "reason": reason,
        "feature_summary": features.global_features,
    }


if __name__ == "__main__":
    research_main()
