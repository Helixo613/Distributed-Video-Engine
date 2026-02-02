#!/usr/bin/env python3
"""
Distributed Video Rendering Engine - HPC Hackathon Demo
Demonstrates CPU parallelism and Amdahl's Law using Split-Process-Merge pattern.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Check dependencies
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    import psutil
except ImportError:
    print("Missing dependencies. Run: pip install rich psutil")
    sys.exit(1)

console = Console()

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    has_audio: bool

@dataclass
class ChunkTask:
    chunk_id: int
    start: float
    duration: float
    input_path: str
    output_path: str

@dataclass
class ChunkResult:
    chunk_id: int
    success: bool
    elapsed: float
    error: Optional[str] = None

# =============================================================================
# VIDEO ANALYSIS (ffprobe)
# =============================================================================

def analyze_video(input_path: str) -> VideoMetadata:
    """Extract video metadata using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_streams',
        input_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    # Find video stream
    video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    if not video_stream:
        raise ValueError("No video stream found")

    # Check for audio
    has_audio = any(s['codec_type'] == 'audio' for s in data['streams'])

    # Parse FPS (handle fractional like "30000/1001")
    fps_str = video_stream.get('r_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den else 30.0
    else:
        fps = float(fps_str)

    return VideoMetadata(
        duration=float(data['format']['duration']),
        width=int(video_stream['width']),
        height=int(video_stream['height']),
        fps=fps,
        codec=video_stream['codec_name'],
        has_audio=has_audio
    )

# =============================================================================
# CHUNK PLANNING
# =============================================================================

def plan_chunks(
    input_path: str,
    duration: float,
    num_chunks: int,
    temp_dir: str
) -> list[ChunkTask]:
    """Calculate chunk boundaries for parallel processing."""
    chunk_duration = duration / num_chunks
    chunks = []

    for i in range(num_chunks):
        start = i * chunk_duration
        # Last chunk gets any remaining duration
        chunk_dur = chunk_duration if i < num_chunks - 1 else (duration - start)

        chunks.append(ChunkTask(
            chunk_id=i,
            start=start,
            duration=chunk_dur,
            input_path=input_path,
            output_path=os.path.join(temp_dir, f"chunk_{i:03d}.mp4")
        ))

    return chunks

# =============================================================================
# WORKER FUNCTION (runs in separate process)
# =============================================================================

def process_chunk(task: ChunkTask, filter_chain: str) -> ChunkResult:
    """Process a single chunk with FFmpeg. Runs in worker process."""
    start_time = time.perf_counter()

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(task.start),
        '-i', task.input_path,
        '-t', str(task.duration),
        '-vf', filter_chain,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-c:a', 'copy',
        '-avoid_negative_ts', 'make_zero',
        task.output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        elapsed = time.perf_counter() - start_time
        return ChunkResult(chunk_id=task.chunk_id, success=True, elapsed=elapsed)
    except subprocess.CalledProcessError as e:
        elapsed = time.perf_counter() - start_time
        return ChunkResult(
            chunk_id=task.chunk_id,
            success=False,
            elapsed=elapsed,
            error=e.stderr.decode() if e.stderr else str(e)
        )

# =============================================================================
# MERGE
# =============================================================================

def merge_chunks(chunk_paths: list[str], output_path: str, temp_dir: str) -> bool:
    """Merge processed chunks using concat demuxer."""
    concat_file = os.path.join(temp_dir, "concat_list.txt")

    # Write concat list
    with open(concat_file, 'w') as f:
        for path in chunk_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")

    # Try stream copy first (fast)
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        # Fallback: re-encode merge
        console.print("[yellow]Stream copy failed, falling back to re-encode merge...[/yellow]")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-c:a', 'aac',
            output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

# =============================================================================
# SERIAL BASELINE
# =============================================================================

def run_serial_baseline(input_path: str, output_path: str, filter_chain: str) -> float:
    """Process entire video in single thread for baseline timing."""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', filter_chain,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-c:a', 'copy',
        output_path
    ]

    start = time.perf_counter()
    subprocess.run(cmd, capture_output=True, check=True)
    return time.perf_counter() - start

# =============================================================================
# PARALLEL PROCESSING
# =============================================================================

def get_cpu_bars():
    """Generate a string of progress bars for each CPU core."""
    per_cpu = psutil.cpu_percent(percpu=True)
    bars = []
    for i, pct in enumerate(per_cpu):
        # Color coding based on load
        color = "green" if pct < 50 else "yellow" if pct < 85 else "red"
        # Create a mini bar
        filled = int(pct / 10)
        bar = "█" * filled + "░" * (10 - filled)
        bars.append(f"CPU{i:02d}: [{color}]{bar}[/{color}] {pct:4.1f}%")
    
    # Split into columns for readability
    cols = 4
    rows = (len(bars) + cols - 1) // cols
    table = Table.grid(expand=True)
    for _ in range(cols):
        table.add_column()
    
    for r in range(rows):
        row_cells = []
        for c in range(cols):
            idx = r + c * rows
            if idx < len(bars):
                row_cells.append(bars[idx])
            else:
                row_cells.append("")
        table.add_row(*row_cells)
    
    return table

def run_parallel(
    input_path: str,
    output_path: str,
    metadata: VideoMetadata,
    num_workers: int,
    filter_chain: str,
    temp_dir: str
) -> tuple[float, list[ChunkResult]]:
    """Process video in parallel chunks with a live dashboard."""

    num_chunks = int(num_workers * 1.5)
    num_chunks = max(num_chunks, num_workers)
    chunks = plan_chunks(input_path, metadata.duration, num_chunks, temp_dir)

    results = []
    start_time = time.perf_counter()

    # Progress tracking
    overall_progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    )
    overall_task = overall_progress.add_task(f"Total Progress", total=len(chunks))

    # Worker status tracking
    worker_status = Table.grid(expand=True)
    worker_status.add_column("Worker")
    worker_status.add_column("Status")

    def make_layout():
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=10)
        )
        layout["header"].update(Panel(f"Running Distributed Render: {num_workers} Workers", style="bold cyan"))
        
        # Upper main: Progress
        layout["main"].split_row(
            Layout(name="progress", ratio=2),
            Layout(name="system", ratio=1)
        )
        
        layout["progress"].update(Panel(overall_progress, title="Job Progress", border_style="blue"))
        layout["system"].update(Panel(get_cpu_bars(), title="CPU Utilization", border_style="red"))
        
        return layout

    with Live(make_layout(), refresh_per_second=4) as live:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(process_chunk, chunk, filter_chain): chunk
                for chunk in chunks
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                overall_progress.advance(overall_task)
                # Update the system monitor in the live display
                live.update(make_layout())

    # Sort results for correct merge order
    results.sort(key=lambda r: r.chunk_id)

    # Check for failures
    failed = [r for r in results if not r.success]
    if failed:
        raise RuntimeError(f"{len(failed)} chunks failed")

    # Merge
    chunk_paths = [chunks[r.chunk_id].output_path for r in results]
    merge_success = merge_chunks(chunk_paths, output_path, temp_dir)

    if not merge_success:
        raise RuntimeError("Merge failed")

    total_time = time.perf_counter() - start_time
    return total_time, results

# =============================================================================
# BENCHMARK & DISPLAY
# =============================================================================

def run_scaling_sweep(
    input_path: str,
    metadata: VideoMetadata,
    filter_chain: str,
    max_workers: int,
    temp_dir: str
) -> dict:
    """Run benchmark across different worker counts."""

    results = {}
    worker_counts = [1]

    # Add powers of 2 up to max_workers
    w = 2
    while w <= max_workers:
        worker_counts.append(w)
        w *= 2

    # Add max_workers if not already included
    if max_workers not in worker_counts:
        worker_counts.append(max_workers)

    worker_counts = sorted(set(worker_counts))

    console.print("\n[bold cyan]Running scaling sweep...[/bold cyan]\n")

    for num_workers in worker_counts:
        output_path = os.path.join(temp_dir, f"output_{num_workers}w.mp4")

        try:
            elapsed, chunk_results = run_parallel(
                input_path, output_path, metadata,
                num_workers, filter_chain, temp_dir
            )
            results[num_workers] = {
                'time': elapsed,
                'success': True,
                'chunk_times': [r.elapsed for r in chunk_results]
            }
        except Exception as e:
            console.print(f"[red]Failed with {num_workers} workers: {e}[/red]")
            results[num_workers] = {'time': None, 'success': False}

    return results

def display_results(
    metadata: VideoMetadata,
    serial_time: float,
    sweep_results: dict,
    max_workers: int
):
    """Display benchmark results with rich formatting."""

    # Header
    console.print(Panel.fit(
        "[bold white]DISTRIBUTED VIDEO RENDERING ENGINE[/bold white]\n"
        "[dim]HPC Hackathon Demo - Amdahl's Law Demonstration[/dim]",
        border_style="cyan"
    ))

    # Video info
    console.print(f"\n[bold]Input:[/bold] {metadata.duration:.1f}s, {metadata.width}x{metadata.height}, {metadata.fps:.1f}fps")
    console.print(f"[bold]CPU Cores:[/bold] {max_workers}")
    console.print(f"[bold]Serial Baseline:[/bold] {serial_time:.2f}s\n")

    # Results table
    table = Table(title="Scaling Results", show_header=True, header_style="bold magenta")
    table.add_column("Workers", justify="center")
    table.add_column("Time (s)", justify="right")
    table.add_column("Speedup", justify="right")
    table.add_column("Efficiency", justify="right")

    for workers, data in sorted(sweep_results.items()):
        if data['success'] and data['time']:
            speedup = serial_time / data['time']
            efficiency = (speedup / workers) * 100
            table.add_row(
                str(workers),
                f"{data['time']:.2f}",
                f"{speedup:.2f}x",
                f"{efficiency:.1f}%"
            )
        else:
            table.add_row(str(workers), "FAILED", "-", "-")

    console.print(table)

    # Amdahl's Law analysis
    if sweep_results.get(max_workers, {}).get('success'):
        best_time = sweep_results[max_workers]['time']
        actual_speedup = serial_time / best_time

        # Estimate serial fraction: S = 1 / (f + (1-f)/N)
        # Solving for f: f = (N - S*N) / (S*N - S)
        # Simplified: f ≈ (1 - S/N) / (1 - 1/N) when S < N
        if actual_speedup < max_workers:
            serial_fraction = (1 - actual_speedup/max_workers) / (1 - 1/max_workers)
            serial_fraction = max(0, min(1, serial_fraction))  # Clamp
            theoretical_max = 1 / serial_fraction if serial_fraction > 0 else max_workers
            theoretical_max = min(theoretical_max, max_workers * 2)  # Reasonable cap

            console.print(f"\n[bold cyan]Amdahl's Law Analysis:[/bold cyan]")
            console.print(f"  Serial fraction: ~{serial_fraction*100:.1f}%")
            console.print(f"  Theoretical max speedup: ~{theoretical_max:.1f}x")
            console.print(f"  Achieved: {actual_speedup:.2f}x ({(actual_speedup/theoretical_max)*100:.0f}% of theoretical)")

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Distributed Video Rendering Engine - HPC Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python render_engine.py input.mp4
  python render_engine.py input.mp4 -w 8 -o output.mp4
  python render_engine.py input.mp4 --filter "boxblur=10:1"
        """
    )
    parser.add_argument("input", nargs="?", default="test_input.mp4", help="Input video file")
    parser.add_argument("-o", "--output", default="output_processed.mp4", help="Output file")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Max workers (default: CPU count)")
    parser.add_argument("--filter", default="unsharp=5:5:1.5:5:5:0.5", help="FFmpeg filter chain")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files")
    parser.add_argument("--skip-serial", action="store_true", help="Skip serial baseline (faster)")
    parser.add_argument("--sweep", action="store_true", help="Run full scaling sweep")
    parser.add_argument("--export", help="Export benchmark results to JSON file")

    args = parser.parse_args()

    # Automatic Test Video Generation
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

    # Setup
    max_workers = args.workers or psutil.cpu_count(logical=True)
    temp_dir = Path(".temp_chunks")
    temp_dir.mkdir(exist_ok=True)

    benchmark_data = {
        "metadata": None,
        "serial_time": None,
        "sweep_results": {},
        "timestamp": time.time()
    }

    try:
        # Analyze
        console.print("[bold]Analyzing video...[/bold]")
        metadata = analyze_video(args.input)
        benchmark_data["metadata"] = vars(metadata)
        console.print(f"  Duration: {metadata.duration:.1f}s, {metadata.width}x{metadata.height} @ {metadata.fps:.1f}fps")
        console.print(f"  Codec: {metadata.codec}, Audio: {'Yes' if metadata.has_audio else 'No'}")

        # Serial baseline
        serial_time = None
        if not args.skip_serial:
            console.print("\n[bold]Running serial baseline...[/bold]")
            serial_output = str(temp_dir / "serial_output.mp4")
            serial_time = run_serial_baseline(args.input, serial_output, args.filter)
            benchmark_data["serial_time"] = serial_time
            console.print(f"  Serial time: {serial_time:.2f}s")

        # Parallel processing
        if args.sweep:
            sweep_results = run_scaling_sweep(
                args.input, metadata, args.filter, max_workers, str(temp_dir)
            )
            benchmark_data["sweep_results"] = sweep_results
            # Copy best result to output
            best_output = temp_dir / f"output_{max_workers}w.mp4"
            if best_output.exists():
                shutil.copy(best_output, args.output)
        else:
            console.print(f"\n[bold]Running parallel processing ({max_workers} workers)...[/bold]")
            elapsed, results = run_parallel(
                args.input, args.output, metadata,
                max_workers, args.filter, str(temp_dir)
            )
            sweep_results = {max_workers: {'time': elapsed, 'success': True}}
            benchmark_data["sweep_results"] = sweep_results

        # Display results
        if serial_time:
            display_results(metadata, serial_time, sweep_results, max_workers)
        else:
            console.print(f"\n[green]Done![/green] Output: {args.output}")
            if sweep_results.get(max_workers, {}).get('time'):
                console.print(f"Parallel time: {sweep_results[max_workers]['time']:.2f}s")

        # Export if requested
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(benchmark_data, f, indent=4)
            console.print(f"[green]Benchmark exported to {args.export}[/green]")

        console.print(f"\n[green]Output saved to: {args.output}[/green]")

    finally:
        # Cleanup
        if not args.keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir)
            console.print("[dim]Temporary files cleaned up.[/dim]")

if __name__ == "__main__":
    main()
