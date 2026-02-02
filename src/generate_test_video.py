#!/usr/bin/env python3
"""
Generate a test video using FFmpeg for demo purposes.
Creates a 60-second video with animated patterns.
"""

import subprocess
import sys
import os

def generate_test_video(output_path: str = "test_input.mp4", duration: int = 60):
    """Generate a test video with animated patterns."""

    # FFmpeg command to generate a test video with:
    # - Mandelbrot fractal animation (CPU intensive to decode/process)
    # - 1280x720 resolution
    # - 30fps
    # - Specified duration
    # - Simple beep audio

    cmd = [
        'ffmpeg', '-y',
        # Video: animated mandelbrot pattern
        '-f', 'lavfi',
        '-i', f'mandelbrot=size=1280x720:rate=30,format=yuv420p',
        # Audio: simple sine wave
        '-f', 'lavfi',
        '-i', f'sine=frequency=440:duration={duration}',
        # Duration limit
        '-t', str(duration),
        # Encoding
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        output_path
    ]

    print(f"Generating {duration}s test video: {output_path}")
    print("This may take a moment...")

    try:
        subprocess.run(cmd, check=True)

        # Get file size
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Done! Generated: {output_path} ({size_mb:.1f} MB)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error generating video: {e}")
        return False
    except FileNotFoundError:
        print("Error: FFmpeg not found. Install with: sudo apt install ffmpeg")
        return False

if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    output = sys.argv[2] if len(sys.argv) > 2 else "test_input.mp4"

    success = generate_test_video(output, duration)
    sys.exit(0 if success else 1)
