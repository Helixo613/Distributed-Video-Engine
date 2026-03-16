from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional path
    np = None

from video_types import SegmentFeature


DEFAULT_FEATURE_FIELDS = [
    "duration",
    "bitrate",
    "bpp",
    "motion_proxy",
    "scene_change_ratio",
    "luma_variance",
    "texture_proxy",
    "estimated_complexity",
]


def _segment_value(segment: SegmentFeature, field: str) -> float:
    value = getattr(segment, field, 0.0)
    if value is None:
        return 0.0
    return float(value)


class LinearCostEstimator:
    """A lightweight linear regressor for per-segment runtime prediction."""

    def __init__(
        self,
        feature_fields: list[str] | None = None,
        means: np.ndarray | None = None,
        scales: np.ndarray | None = None,
        coefficients: np.ndarray | None = None,
        intercept: float = 0.0,
    ) -> None:
        self.feature_fields = feature_fields or list(DEFAULT_FEATURE_FIELDS)
        self.means = means
        self.scales = scales
        self.coefficients = coefficients
        self.intercept = intercept

    def _matrix(self, segments: Iterable[SegmentFeature]) -> np.ndarray:
        rows = [[_segment_value(segment, field) for field in self.feature_fields] for segment in segments]
        if not rows:
            return np.empty((0, len(self.feature_fields)))
        return np.asarray(rows, dtype=float)

    def fit(self, segments: list[SegmentFeature], runtimes: list[float]) -> None:
        if np is None:
            raise RuntimeError("numpy is required to train the optional linear cost estimator")
        x = self._matrix(segments)
        y = np.asarray(runtimes, dtype=float)
        if x.size == 0 or y.size == 0 or x.shape[0] != y.shape[0]:
            raise ValueError("Training data must include matching segment features and runtimes")

        self.means = x.mean(axis=0)
        self.scales = x.std(axis=0)
        self.scales[self.scales == 0] = 1.0
        x_norm = (x - self.means) / self.scales
        x_design = np.column_stack([np.ones(x_norm.shape[0]), x_norm])
        coefficients, *_ = np.linalg.lstsq(x_design, y, rcond=None)
        self.intercept = float(coefficients[0])
        self.coefficients = coefficients[1:]

    def predict(self, segments: list[SegmentFeature]) -> list[float]:
        if np is None:
            raise RuntimeError("numpy is required to use the optional linear cost estimator")
        if self.means is None or self.scales is None or self.coefficients is None:
            raise ValueError("Model is not trained")
        x = self._matrix(segments)
        if x.size == 0:
            return []
        x_norm = (x - self.means) / self.scales
        preds = self.intercept + x_norm @ self.coefficients
        return [max(1e-6, float(pred)) for pred in preds]

    def save(self, output_path: str) -> None:
        payload = {
            "feature_fields": self.feature_fields,
            "means": self.means.tolist() if self.means is not None else None,
            "scales": self.scales.tolist() if self.scales is not None else None,
            "coefficients": self.coefficients.tolist() if self.coefficients is not None else None,
            "intercept": self.intercept,
        }
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    @classmethod
    def load(cls, input_path: str) -> "LinearCostEstimator":
        if np is None:
            raise RuntimeError("numpy is required to load the optional linear cost estimator")
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        means = np.asarray(payload["means"], dtype=float) if payload.get("means") is not None else None
        scales = np.asarray(payload["scales"], dtype=float) if payload.get("scales") is not None else None
        coeffs = np.asarray(payload["coefficients"], dtype=float) if payload.get("coefficients") is not None else None
        return cls(
            feature_fields=payload.get("feature_fields"),
            means=means,
            scales=scales,
            coefficients=coeffs,
            intercept=float(payload.get("intercept", 0.0)),
        )
