#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from feature_extractor import extract_video_features
from ffmpeg_utils import analyze_video, ensure_dir


REAL_SOURCE_SPECS = [
    {"source": "test_input.mp4", "clip_id": "real_test_input_720p_12s", "start": 6.0, "duration": 12, "width": 1280, "height": 720},
    {"source": "test_input.mp4", "clip_id": "real_test_input_720p_30s", "start": 0.0, "duration": 30, "width": 1280, "height": 720},
    {"source": "0f282b8c_43295-436026111.mp4", "clip_id": "real_phone_1080p_12s", "start": 4.0, "duration": 12, "width": 1920, "height": 1080},
    {"source": "4a2a3887_Untitled video - Made with Clipchamp (4) (1) (1).mp4", "clip_id": "real_clipchamp_720p_12s", "start": 12.0, "duration": 12, "width": 1280, "height": 720},
    {"source": "4a2a3887_Untitled video - Made with Clipchamp (4) (1) (1).mp4", "clip_id": "real_clipchamp_1080p_30s", "start": 48.0, "duration": 30, "width": 1920, "height": 1080},
    {"source": "4a2a3887_Untitled video - Made with Clipchamp (4) (1) (1).mp4", "clip_id": "real_clipchamp_1080p_60s", "start": 96.0, "duration": 60, "width": 1920, "height": 1080},
    {"source": "2e4d0e39_203678-922748476.mp4", "clip_id": "real_4k_primary_12s", "start": 5.0, "duration": 12, "width": 3840, "height": 2160},
    {"source": "2e4d0e39_203678-922748476.mp4", "clip_id": "real_4k_primary_30s", "start": 1.0, "duration": 30, "width": 3840, "height": 2160},
    {"source": "2e4d0e39_203678-922748476.mp4", "clip_id": "real_4k_downscaled_30s", "start": 1.0, "duration": 30, "width": 1920, "height": 1080},
    {"source": "0fd92ee0_203678-922748476.mp4", "clip_id": "real_4k_alt_12s", "start": 14.0, "duration": 12, "width": 3840, "height": 2160},
]

SYNTHETIC_SPECS = [
    {"kind": "smptebars", "clip_id": "synthetic_smptebars_720p_12s", "duration": 12, "width": 1280, "height": 720},
    {"kind": "smptebars", "clip_id": "synthetic_smptebars_1080p_30s", "duration": 30, "width": 1920, "height": 1080},
    {"kind": "smptebars", "clip_id": "synthetic_smptebars_1080p_60s", "duration": 60, "width": 1920, "height": 1080},
    {"kind": "testsrc2", "clip_id": "synthetic_testsrc2_720p_12s", "duration": 12, "width": 1280, "height": 720},
    {"kind": "testsrc2", "clip_id": "synthetic_testsrc2_1080p_30s", "duration": 30, "width": 1920, "height": 1080},
    {"kind": "testsrc2", "clip_id": "synthetic_testsrc2_1080p_60s", "duration": 60, "width": 1920, "height": 1080},
    {"kind": "scenecut", "clip_id": "synthetic_scenecut_1080p_12s", "duration": 12, "width": 1920, "height": 1080},
    {"kind": "scenecut", "clip_id": "synthetic_scenecut_1080p_30s", "duration": 30, "width": 1920, "height": 1080},
    {"kind": "scenecut", "clip_id": "synthetic_scenecut_1080p_60s", "duration": 60, "width": 1920, "height": 1080},
    {"kind": "stress", "clip_id": "synthetic_stress_1080p_30s", "duration": 30, "width": 1920, "height": 1080},
    {"kind": "stress", "clip_id": "synthetic_stress_2160p_12s", "duration": 12, "width": 3840, "height": 2160},
]


def _resolution_label(width: int, height: int) -> str:
    if height >= 2160:
        return "2160p"
    if height >= 1080:
        return "1080p"
    return "720p"


def _duration_label(seconds: int) -> str:
    return f"{seconds}s"


def _content_class(feature_summary: dict) -> str:
    motion = feature_summary.get("motion_proxy", 0.0)
    scene_change = feature_summary.get("scene_change_proxy", 0.0)
    texture = feature_summary.get("texture_proxy", 0.0)
    if scene_change >= 0.25:
        return "scene-cut-heavy"
    if motion < 4.0 and texture < 8.0:
        return "static-low-motion"
    if motion >= 16.0 and texture >= 16.0:
        return "high-motion-high-texture"
    if texture >= 20.0:
        return "high-texture"
    if motion >= 10.0:
        return "medium-to-high-motion"
    return "medium-motion"


def _run_ffmpeg(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _extract_real_clip(repo_root: Path, output_path: Path, spec: dict) -> None:
    source_path = repo_root / spec["source"]
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(spec["start"]),
        "-i",
        str(source_path),
        "-t",
        str(spec["duration"]),
        "-vf",
        f"scale={spec['width']}:{spec['height']}:flags=lanczos",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]
    _run_ffmpeg(cmd)


def _generate_synthetic_clip(output_path: Path, spec: dict) -> None:
    width = spec["width"]
    height = spec["height"]
    duration = spec["duration"]
    kind = spec["kind"]

    if kind == "smptebars":
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"smptebars=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]
    elif kind == "testsrc2":
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=660:sample_rate=48000:duration={duration}",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]
    elif kind == "scenecut":
        segment = max(2, duration // 6)
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            str(segment),
            "-i",
            f"smptebars=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-t",
            str(segment),
            "-i",
            f"testsrc2=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-t",
            str(segment),
            "-i",
            f"color=c=red:size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-t",
            str(duration - 3 * segment),
            "-i",
            f"mandelbrot=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=880:sample_rate=48000:duration={duration}",
            "-filter_complex",
            "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "4:a",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]
    elif kind == "stress":
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"mandelbrot=size={width}x{height}:rate=30",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=523:sample_rate=48000:duration={duration}",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]
    else:
        raise ValueError(f"Unsupported synthetic kind: {kind}")

    _run_ffmpeg(cmd)


def _build_manifest_entry(path: Path, source_kind: str, source_path: str | None, clip_id: str, duration: int) -> dict:
    metadata = analyze_video(str(path))
    features = extract_video_features(str(path))
    return {
        "clip_id": clip_id,
        "path": str(path.resolve()),
        "source_kind": source_kind,
        "source_path": source_path,
        "duration_label": _duration_label(duration),
        "resolution_label": _resolution_label(metadata.width, metadata.height),
        "content_class": _content_class(features.global_features),
        "metadata": {
            "duration": metadata.duration,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "bitrate": metadata.bitrate,
        },
        "feature_summary": features.global_features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a reproducible benchmark suite of real and synthetic video clips.")
    parser.add_argument("--output-dir", default="experiments/benchmark_suite", help="Benchmark suite output directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = ensure_dir(repo_root / args.output_dir)
    inputs_dir = ensure_dir(output_dir / "inputs")
    clips: list[dict] = []

    for spec in REAL_SOURCE_SPECS:
        output_path = inputs_dir / f"{spec['clip_id']}.mp4"
        if not output_path.exists():
            _extract_real_clip(repo_root, output_path, spec)
        clips.append(
            _build_manifest_entry(
                path=output_path,
                source_kind="real",
                source_path=str((repo_root / spec["source"]).resolve()),
                clip_id=spec["clip_id"],
                duration=spec["duration"],
            )
        )

    for spec in SYNTHETIC_SPECS:
        output_path = inputs_dir / f"{spec['clip_id']}.mp4"
        if not output_path.exists():
            _generate_synthetic_clip(output_path, spec)
        clips.append(
            _build_manifest_entry(
                path=output_path,
                source_kind="synthetic",
                source_path=spec["kind"],
                clip_id=spec["clip_id"],
                duration=spec["duration"],
            )
        )

    manifest = {
        "schema_version": "research-prototype.v3",
        "clips": clips,
    }
    manifest_path = output_dir / "benchmark_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote benchmark suite manifest to {manifest_path}")
    print(f"Prepared {len(clips)} clips in {inputs_dir}")


if __name__ == "__main__":
    main()
