from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    has_audio: bool
    bitrate: Optional[float] = None
    pix_fmt: Optional[str] = None

    @property
    def pixel_count(self) -> int:
        return self.width * self.height


@dataclass
class ChunkTask:
    chunk_id: int
    start: float
    duration: float
    input_path: str
    output_path: str
    estimated_cost: Optional[float] = None
    source_segment_ids: list[int] = field(default_factory=list)
    rationale: Optional[str] = None


@dataclass
class ChunkResult:
    chunk_id: int
    success: bool
    elapsed: float
    error: Optional[str] = None
    return_code: Optional[int] = None
    output_path: Optional[str] = None


@dataclass
class SegmentFeature:
    segment_id: int
    start: float
    end: float
    duration: float
    sample_count: int
    bitrate: Optional[float]
    bpp: Optional[float]
    motion_proxy: float
    scene_change_ratio: float
    luma_variance: float
    texture_proxy: float
    estimated_complexity: float
    predicted_runtime: Optional[float] = None


@dataclass
class FeatureExtractionResult:
    metadata: VideoMetadata
    extraction_time: float
    sample_fps: float
    sample_width: int
    sample_height: int
    analysis_window_seconds: float
    total_sample_frames: int
    global_features: dict[str, Any]
    segment_features: list[SegmentFeature]
    encode_time_proxy: Optional[float] = None


@dataclass
class PartitionPlan:
    policy: str
    chunks: list[ChunkTask]
    rationale: list[str]
    total_estimated_cost: float
    planning_time: float


@dataclass
class SchedulerDecision:
    worker_count: int
    chunk_count: int
    partition_policy: str
    predicted_total_time: float
    estimated_serial_time: float
    estimated_chunk_costs: list[float]
    predicted_compute_time: float
    overheads: dict[str, float]
    rationale: list[str]
    search_trace: list[dict[str, Any]] = field(default_factory=list)
