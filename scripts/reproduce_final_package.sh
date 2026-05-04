#!/usr/bin/env bash
# reproduce_final_package.sh
#
# One-command reproduction of the canonical paper_run_final package.
# Runs the full experiment suite, merges the short-clip batch, and
# generates all analysis artifacts.
#
# Usage:
#   bash scripts/reproduce_final_package.sh [OUTPUT_DIR]
#
# Default output: experiments/paper_run_final
# Prerequisites: Python 3.10+, FFmpeg in PATH

set -euo pipefail

OUTPUT_DIR="${1:-experiments/paper_run_final}"
EXECUTION_BACKEND="${DVE_EXECUTION_BACKEND:-auto}"
SHORT_DIR="${OUTPUT_DIR}_short_tmp"
MANIFEST="experiments/benchmark_suite/benchmark_manifest.json"
COMMON_ARGS=(
  --baselines serial,static-equal,adaptive-scheduled
  --workers 1,2,4,6,8,12,16
  --chunk-multipliers 1.0,1.5,2.0
  --fixed-workers 4
  --trials 3
  --benchmark-manifest "$MANIFEST"
)

echo "=== Reproducing canonical final package ==="
echo "Output: $OUTPUT_DIR"
echo "Execution backend: $EXECUTION_BACKEND"
echo ""

# Stage 1: Main batch (4 clips, 3 workloads)
echo "[1/5] Running main experiment batch (4 clips x 3 workloads x 3 baselines x 3 trials = 108 runs)..."
PYTHONPATH=src python3 -m experiment_runner \
  experiments/benchmark_suite/inputs/real_clipchamp_720p_12s.mp4 \
  experiments/benchmark_suite/inputs/real_test_input_720p_30s.mp4 \
  experiments/benchmark_suite/inputs/real_phone_1080p_12s.mp4 \
  experiments/benchmark_suite/inputs/real_clipchamp_1080p_30s.mp4 \
  --output-dir "$OUTPUT_DIR" \
  --workloads light,medium,heavy \
  --execution-backend "$EXECUTION_BACKEND" \
  "${COMMON_ARGS[@]}"

# Stage 2: Short clip batch (3s, light only)
echo "[2/5] Running short-clip batch (1 clip x 1 workload x 3 baselines x 3 trials = 9 runs)..."
PYTHONPATH=src python3 -m experiment_runner \
  experiments/benchmark_suite/inputs/real_clipchamp_720p_3s.mp4 \
  --output-dir "$SHORT_DIR" \
  --workloads light \
  --execution-backend "$EXECUTION_BACKEND" \
  "${COMMON_ARGS[@]}"

# Stage 3: Merge
echo "[3/5] Merging batches..."
tail -n +2 "$SHORT_DIR/runs.csv" >> "$OUTPUT_DIR/runs.csv"
cat "$SHORT_DIR/segments.jsonl" >> "$OUTPUT_DIR/segments.jsonl"
cat "$SHORT_DIR/runs.jsonl" >> "$OUTPUT_DIR/runs.jsonl"
rm -rf "$SHORT_DIR"

# Stage 4: Generate analysis artifacts
echo "[4/5] Generating summaries, calibration report, and budget analysis..."
PYTHONPATH=src python3 -m summarize_experiment_results \
  "$OUTPUT_DIR/runs.csv" \
  --output-json "$OUTPUT_DIR/summary.json" \
  --output-csv "$OUTPUT_DIR/summary.csv"

PYTHONPATH=src python3 -m calibration_analysis \
  "$OUTPUT_DIR/runs.csv" \
  --output "$OUTPUT_DIR/calibration_report.json"

PYTHONPATH=src python3 -m budget_analysis \
  "$OUTPUT_DIR/runs.csv" \
  --output-json "$OUTPUT_DIR/budget_analysis.json" \
  --output-csv "$OUTPUT_DIR/budget_analysis.csv" \
  --execution-backend "$EXECUTION_BACKEND"

PYTHONPATH=src python3 -m decision_cost_analysis \
  "$OUTPUT_DIR/runs.csv" \
  --output-dir "$OUTPUT_DIR/paper_assets"

# Stage 5: Clean up temp dirs and output videos
echo "[5/5] Cleaning up..."
rm -rf "$OUTPUT_DIR"/tmp_run_* "$OUTPUT_DIR"/tmp_profile_* "$OUTPUT_DIR"/*.mp4

echo ""
echo "=== Done ==="
echo "Final package: $OUTPUT_DIR/"
echo "Files:"
ls -1 "$OUTPUT_DIR"/*.{json,csv,jsonl} 2>/dev/null | sed 's|^|  |'
TOTAL=$(( $(wc -l < "$OUTPUT_DIR/runs.csv") - 1 ))
echo "Total runs: $TOTAL"
