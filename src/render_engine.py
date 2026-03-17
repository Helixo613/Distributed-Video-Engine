#!/usr/bin/env python3
"""
Adaptive partitioning and scheduling framework for FFmpeg-based parallel video processing.

This module keeps the original entry points available for the server and legacy scripts,
but the underlying implementation is now organized around research-oriented components:
feature extraction, adaptive partitioning, scheduling, and structured evaluation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency in constrained environments
    psutil = None

from adaptive_partitioner import build_partition_plan
from cost_estimator import LinearCostEstimator
from feature_extractor import extract_video_features, save_feature_summary
from ffmpeg_utils import analyze_video, benchmark_serial_sample, ensure_dir, run_serial_baseline
from pipeline import execute_partition_plan, run_processing_pipeline, write_record
from scheduler import search_best_configuration
from video_types import ChunkResult, VideoMetadata

console = Console()


def benchmark_serial(input_path: str, temp_dir: str, filter_chain: str) -> float:
    """Backward-compatible alias for the short serial runtime sample."""
    return benchmark_serial_sample(input_path, temp_dir, filter_chain)


def get_smart_config(metadata: VideoMetadata, max_cpu: int) -> dict:
    """
    Backward-compatible heuristic selection.

    The returned structure now frames the decision as adaptive scheduling rather than demo tuning.
    """
    total_pixels = metadata.width * metadata.height
    config = {
        "workers": max_cpu,
        "filter": "unsharp=5:5:1.0:5:5:0.0",
        "partition_policy": "heuristic-adaptive",
        "scheduler_enabled": True,
        "reason": "Adaptive research mode selected a balanced default configuration.",
    }
    if total_pixels > 3000000:
        config["workers"] = min(max_cpu, 8)
        config["filter"] = "hqdn3d=5:5:5:5"
        config["reason"] = (
            "High-resolution input detected; capping worker count to limit memory pressure while preserving "
            "adaptive partitioning for scheduling experiments."
        )
    elif total_pixels <= 1920 * 1080:
        config["workers"] = max(1, int(max_cpu * 0.75))
        config["filter"] = "unsharp=5:5:1.0:5:5:0.0,eq=saturation=1.1"
        config["reason"] = (
            "Moderate-resolution input detected; reserving some cores and using a stable filter chain for "
            "baseline-versus-adaptive comparisons."
        )
    return config


def run_parallel(
    input_path: str,
    output_path: str,
    metadata: VideoMetadata,
    num_workers: int,
    filter_chain: str,
    temp_dir: str,
    quiet: bool = False,
    progress_callback=None,
) -> tuple[float, list[ChunkResult]]:
    """
    Backward-compatible equal-duration execution path used by the server and legacy scripts.
    """
    ensure_dir(temp_dir)
    num_chunks = max(num_workers, int(round(num_workers * 1.5)))
    partition_plan = build_partition_plan(
        input_path=input_path,
        metadata=metadata,
        temp_dir=temp_dir,
        policy="equal-duration",
        num_chunks=num_chunks,
    )
    execution = execute_partition_plan(
        partition_plan=partition_plan,
        output_path=output_path,
        workers=num_workers,
        filter_chain=filter_chain,
        temp_dir=temp_dir,
        progress_callback=progress_callback,
    )
    results = [ChunkResult(**record) for record in execution["results"]]
    total_time = execution["dispatch_time"] + execution["compute_time"] + execution["merge_time"]
    return total_time, results


def run_scaling_sweep(
    input_path: str,
    metadata: VideoMetadata,
    filter_chain: str,
    max_workers: int,
    temp_dir: str,
    partition_policy: str = "equal-duration",
) -> dict:
    """Run a bounded worker sweep and capture chunk-level runtime data."""
    results = {}
    worker_counts = [1]
    worker = 2
    while worker <= max_workers:
        worker_counts.append(worker)
        worker *= 2
    if max_workers not in worker_counts:
        worker_counts.append(max_workers)
    worker_counts = sorted(set(worker_counts))

    for worker_count in worker_counts:
        run_dir = ensure_dir(Path(temp_dir) / f"{worker_count}w")
        output_path = run_dir / f"output_{worker_count}w.mp4"
        try:
            record = run_processing_pipeline(
                input_path=input_path,
                output_path=str(output_path),
                filter_chain=filter_chain,
                partition_policy=partition_policy,
                worker_count=worker_count,
                chunk_count=max(worker_count, int(round(worker_count * 1.5))),
                scheduler_enabled=False,
                enable_quality_metrics=False,
                temp_dir=str(run_dir),
            )
            results[worker_count] = {
                "time": record["runtime"]["actual_total_time"],
                "success": True,
                "chunk_times": [chunk["elapsed"] for chunk in record["actual_chunk_runtime"]],
                "chunk_boundaries": record["planned_chunk_boundaries"],
            }
        except Exception as exc:
            results[worker_count] = {
                "time": None,
                "success": False,
                "error": str(exc),
            }
    return results


def display_results(
    metadata: VideoMetadata,
    serial_time: float,
    sweep_results: dict,
    max_workers: int,
) -> None:
    """Display a concise research-oriented result summary."""
    console.print(
        Panel.fit(
            "[bold white]ADAPTIVE VIDEO PROCESSING RESEARCH PROTOTYPE[/bold white]\n"
            "[dim]Complexity-aware partitioning and overhead-aware scheduling for FFmpeg pipelines[/dim]",
            border_style="cyan",
        )
    )
    console.print(
        f"\n[bold]Input:[/bold] {metadata.duration:.1f}s, {metadata.width}x{metadata.height}, {metadata.fps:.2f}fps"
    )
    console.print(f"[bold]Max Workers Evaluated:[/bold] {max_workers}")
    console.print(f"[bold]Serial Baseline:[/bold] {serial_time:.2f}s")

    table = Table(title="Worker Sweep", show_header=True, header_style="bold cyan")
    table.add_column("Workers", justify="center")
    table.add_column("Time (s)", justify="right")
    table.add_column("Speedup", justify="right")
    table.add_column("Efficiency", justify="right")

    for workers, data in sorted(sweep_results.items()):
        if data.get("success") and data.get("time"):
            speedup = serial_time / data["time"]
            efficiency = (speedup / workers) * 100 if workers > 0 else 0.0
            table.add_row(str(workers), f"{data['time']:.2f}", f"{speedup:.2f}x", f"{efficiency:.1f}%")
        else:
            table.add_row(str(workers), "FAILED", "-", "-")
    console.print(table)


def _load_estimator(path: str | None) -> Optional[LinearCostEstimator]:
    if not path:
        return None
    return LinearCostEstimator.load(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adaptive FFmpeg-based parallel video processing research prototype.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/render_engine.py input.mp4
  python src/render_engine.py input.mp4 --partition-policy heuristic-adaptive --scheduler
  python src/render_engine.py input.mp4 --sweep --partition-policy equal-duration
  python src/render_engine.py input.mp4 --smart --record-output outputs/run_record.json
        """,
    )
    parser.add_argument("input", nargs="?", default="test_input.mp4", help="Input video file")
    parser.add_argument("-o", "--output", default="output_processed.mp4", help="Output video path")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Requested worker count (default: CPU count)")
    parser.add_argument("--chunks", type=int, default=None, help="Requested chunk count")
    parser.add_argument("--filter", default="unsharp=5:5:1.5:5:5:0.5", help="FFmpeg filter chain")
    parser.add_argument(
        "--partition-policy",
        choices=["serial", "equal-duration", "heuristic-adaptive", "ml-adaptive"],
        default="equal-duration",
        help="Partitioning strategy",
    )
    parser.add_argument("--scheduler", action="store_true", help="Enable bounded worker/chunk search")
    parser.add_argument("--scheduler-workers", default="1,2,4,6,8,12,16", help="Scheduler worker candidates")
    parser.add_argument("--scheduler-chunk-multipliers", default="1.0,1.5,2.0", help="Scheduler chunk multipliers")
    parser.add_argument("--model", help="Optional linear model for ml-adaptive partitioning")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files")
    parser.add_argument("--skip-serial", action="store_true", help="Skip full serial baseline")
    parser.add_argument("--sweep", action="store_true", help="Run a worker sweep for the selected partition policy")
    parser.add_argument("--export", help="Legacy export path for benchmark-style JSON output")
    parser.add_argument("--record-output", help="Write the full structured run record to JSON")
    parser.add_argument("--feature-output", help="Write extracted feature summary to JSON")
    parser.add_argument("--enable-vmaf", action="store_true", help="Attempt VMAF computation if supported")
    parser.add_argument("--enable-encode-proxy", action="store_true", help="Enable low-resolution encode-time proxy")
    parser.add_argument(
        "--smart",
        action="store_true",
        help="Compatibility flag: enable heuristic adaptive partitioning with scheduler search",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        if args.input == "test_input.mp4":
            console.print(f"[yellow]Input '{args.input}' not found. Generating synthetic test video...[/yellow]")
            try:
                import generate_test_video

                generate_test_video.generate_test_video(args.input, duration=30)
            except ImportError:
                console.print("[red]Error: generate_test_video.py not found in current directory.[/red]")
                sys.exit(1)
        else:
            console.print(f"[red]Error: Input file not found: {args.input}[/red]")
            sys.exit(1)

    worker_count = args.workers or (psutil.cpu_count(logical=True) if psutil else os.cpu_count()) or 4
    partition_policy = args.partition_policy
    scheduler_enabled = args.scheduler
    filter_chain = args.filter

    if args.smart:
        smart = get_smart_config(analyze_video(args.input), worker_count)
        worker_count = smart["workers"]
        filter_chain = smart["filter"]
        partition_policy = smart["partition_policy"]
        scheduler_enabled = bool(smart["scheduler_enabled"])
        console.print(
            Panel(
                f"[bold]Adaptive mode enabled[/bold]\n{smart['reason']}\n"
                f"Policy: [cyan]{partition_policy}[/cyan]\n"
                f"Workers: [cyan]{worker_count}[/cyan]\n"
                f"Filter: [cyan]{filter_chain}[/cyan]",
                title="Research Configuration",
            )
        )

    temp_dir = Path(".temp_chunks")
    temp_dir.mkdir(exist_ok=True)
    metadata = analyze_video(args.input)

    if args.feature_output:
        feature_result = extract_video_features(
            args.input,
            enable_encode_time_proxy=args.enable_encode_proxy,
            output_path=args.feature_output,
        )
        console.print(
            f"[green]Feature summary written to {args.feature_output} "
            f"({len(feature_result.segment_features)} sampled analysis windows).[/green]"
        )

    if args.sweep:
        serial_output = str(temp_dir / "serial_output.mp4")
        serial_time = benchmark_serial_sample(args.input, str(temp_dir), filter_chain)
        sweep_results = run_scaling_sweep(
            input_path=args.input,
            metadata=metadata,
            filter_chain=filter_chain,
            max_workers=worker_count,
            temp_dir=str(temp_dir),
            partition_policy=partition_policy,
        )
        display_results(metadata, serial_time, sweep_results, worker_count)
        if args.export:
            payload = {
                "metadata": asdict(metadata),
                "serial_time": serial_time,
                "sweep_results": sweep_results,
                "partition_policy": partition_policy,
                "scheduler_enabled": scheduler_enabled,
            }
            with open(args.export, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            console.print(f"[green]Sweep results written to {args.export}[/green]")
    else:
        estimator = _load_estimator(args.model)
        record = run_processing_pipeline(
            input_path=args.input,
            output_path=args.output,
            filter_chain=filter_chain,
            partition_policy=partition_policy,
            worker_count=worker_count,
            chunk_count=args.chunks,
            scheduler_enabled=scheduler_enabled,
            scheduler_workers=[int(item) for item in args.scheduler_workers.split(",") if item.strip()],
            scheduler_chunk_multipliers=[float(item) for item in args.scheduler_chunk_multipliers.split(",") if item.strip()],
            enable_full_serial_baseline=not args.skip_serial,
            enable_encode_time_proxy=args.enable_encode_proxy,
            enable_quality_metrics=True,
            enable_vmaf=args.enable_vmaf,
            estimator=estimator,
            temp_dir=str(temp_dir),
        )
        console.print(
            Panel(
                f"[bold]Run complete[/bold]\n"
                f"Policy: [cyan]{record['partition_policy']}[/cyan]\n"
                f"Workers: [cyan]{record['worker_count']}[/cyan]\n"
                f"Chunks: [cyan]{record['chunk_count']}[/cyan]\n"
                f"Runtime: [cyan]{record['runtime']['actual_total_time']:.2f}s[/cyan]\n"
                f"Speedup vs serial: [cyan]{(record['performance']['speedup_vs_serial'] or 0):.2f}x[/cyan]",
                title="Execution Summary",
            )
        )
        if args.export:
            legacy_payload = {
                "metadata": record["metadata"],
                "serial_time": record["runtime"]["serial_baseline_time"] or record["runtime"]["projected_serial_time"],
                "sweep_results": {
                    str(record["worker_count"]): {
                        "time": record["runtime"]["actual_total_time"],
                        "success": True,
                        "chunk_times": [chunk["elapsed"] for chunk in record["actual_chunk_runtime"]],
                    }
                },
                "selection": record.get("selection"),
            }
            with open(args.export, "w", encoding="utf-8") as handle:
                json.dump(legacy_payload, handle, indent=2)
            console.print(f"[green]Benchmark export written to {args.export}[/green]")
        if args.record_output:
            write_record(record, args.record_output)
            console.print(f"[green]Structured run record written to {args.record_output}[/green]")

    if not args.keep_temp and temp_dir.exists():
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
