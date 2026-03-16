#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cost_estimator import LinearCostEstimator
from video_types import SegmentFeature


def _load_segments(input_path: str) -> tuple[list[SegmentFeature], list[float]]:
    segments: list[SegmentFeature] = []
    runtimes: list[float] = []
    with open(input_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            runtime = payload.get("actual_chunk_runtime")
            if runtime is None:
                continue
            segments.append(
                SegmentFeature(
                    segment_id=int(payload["segment_id"]),
                    start=float(payload["start"]),
                    end=float(payload["end"]),
                    duration=float(payload["duration"]),
                    sample_count=int(payload.get("sample_count", 0)),
                    bitrate=payload.get("bitrate"),
                    bpp=payload.get("bpp"),
                    motion_proxy=float(payload.get("motion_proxy", 0.0)),
                    scene_change_ratio=float(payload.get("scene_change_ratio", 0.0)),
                    luma_variance=float(payload.get("luma_variance", 0.0)),
                    texture_proxy=float(payload.get("texture_proxy", 0.0)),
                    estimated_complexity=float(payload.get("estimated_complexity", 0.0)),
                    predicted_runtime=None,
                )
            )
            runtimes.append(float(runtime))
    return segments, runtimes


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a lightweight linear segment-cost model from logged segment data.")
    parser.add_argument("input", help="Path to segments.jsonl")
    parser.add_argument("--output", default="experiments/cost_model.json", help="Model output path")
    args = parser.parse_args()

    segments, runtimes = _load_segments(args.input)
    model = LinearCostEstimator()
    model.fit(segments, runtimes)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output)


if __name__ == "__main__":
    main()
