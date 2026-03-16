from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _flatten(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            _flatten(next_prefix, item, output)
    elif isinstance(value, list):
        output[prefix] = json.dumps(value)
    else:
        output[prefix] = value


class MetricsLogger:
    """Persist experiment outputs in both JSONL and CSV forms for aggregation."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_jsonl = self.output_dir / "runs.jsonl"
        self.run_csv = self.output_dir / "runs.csv"
        self.segment_jsonl = self.output_dir / "segments.jsonl"

    def log_run(self, record: dict[str, Any]) -> None:
        with self.run_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        flat: dict[str, Any] = {}
        _flatten("", record, flat)
        if not self.run_csv.exists():
            with self.run_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(flat.keys()))
                writer.writeheader()
                writer.writerow(flat)
            return

        with self.run_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            existing_rows = list(reader)
            existing_fields = reader.fieldnames or []

        merged_fields = sorted(set(existing_fields) | set(flat.keys()))
        if merged_fields != existing_fields:
            with self.run_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=merged_fields)
                writer.writeheader()
                for row in existing_rows:
                    writer.writerow(row)
                writer.writerow(flat)
            return

        with self.run_csv.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=existing_fields)
            writer.writerow(flat)

    def log_segments(self, segments: list[dict[str, Any]]) -> None:
        if not segments:
            return
        with self.segment_jsonl.open("a", encoding="utf-8") as handle:
            for record in segments:
                handle.write(json.dumps(record) + "\n")
