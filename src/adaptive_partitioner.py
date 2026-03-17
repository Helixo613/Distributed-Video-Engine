from __future__ import annotations

import time
from typing import Optional

from cost_estimator import LinearCostEstimator
from video_types import ChunkTask, FeatureExtractionResult, PartitionPlan, SegmentFeature, VideoMetadata


def _chunk_output_path(temp_dir: str, chunk_id: int) -> str:
    return f"{temp_dir}/chunk_{chunk_id:03d}.mp4"


def _equal_duration_plan(
    input_path: str,
    metadata: VideoMetadata,
    num_chunks: int,
    temp_dir: str,
    estimated_total_runtime: Optional[float] = None,
) -> PartitionPlan:
    start_time = time.perf_counter()
    chunk_duration = metadata.duration / max(1, num_chunks)
    chunks: list[ChunkTask] = []
    default_cost = (estimated_total_runtime / num_chunks) if estimated_total_runtime else None
    for chunk_id in range(num_chunks):
        start = chunk_id * chunk_duration
        duration = chunk_duration if chunk_id < num_chunks - 1 else max(0.001, metadata.duration - start)
        chunks.append(
            ChunkTask(
                chunk_id=chunk_id,
                start=round(start, 6),
                duration=round(duration, 6),
                input_path=input_path,
                output_path=_chunk_output_path(temp_dir, chunk_id),
                estimated_cost=default_cost,
                rationale="Equal-duration baseline partition",
            )
        )
    planning_time = time.perf_counter() - start_time
    rationale = [f"Equal-duration baseline with {num_chunks} chunks."]
    return PartitionPlan(
        policy="equal-duration",
        chunks=chunks,
        rationale=rationale,
        total_estimated_cost=float(estimated_total_runtime or num_chunks),
        planning_time=planning_time,
    )


def _serial_plan(input_path: str, metadata: VideoMetadata, temp_dir: str, estimated_total_runtime: Optional[float] = None) -> PartitionPlan:
    start_time = time.perf_counter()
    chunk = ChunkTask(
        chunk_id=0,
        start=0.0,
        duration=round(metadata.duration, 6),
        input_path=input_path,
        output_path=_chunk_output_path(temp_dir, 0),
        estimated_cost=estimated_total_runtime,
        rationale="Serial baseline: single chunk spans full duration",
    )
    planning_time = time.perf_counter() - start_time
    return PartitionPlan(
        policy="serial",
        chunks=[chunk],
        rationale=["Serial baseline requested; chunking disabled."],
        total_estimated_cost=float(estimated_total_runtime or 1.0),
        planning_time=planning_time,
    )


def _window_costs(
    feature_result: FeatureExtractionResult,
    policy: str,
    estimator: Optional[LinearCostEstimator] = None,
) -> list[float]:
    segments = feature_result.segment_features
    if policy == "ml-adaptive" and estimator is not None:
        return estimator.predict(segments)
    return [max(1e-6, segment.estimated_complexity) for segment in segments]


def _build_cost_balanced_chunks(
    input_path: str,
    metadata: VideoMetadata,
    segments: list[SegmentFeature],
    segment_costs: list[float],
    num_chunks: int,
    temp_dir: str,
    policy: str,
    estimated_total_runtime: Optional[float] = None,
) -> PartitionPlan:
    start_time = time.perf_counter()
    if not segments or len(segments) < num_chunks:
        return _equal_duration_plan(input_path, metadata, num_chunks, temp_dir, estimated_total_runtime)

    # If segment costs are nearly uniform, cost-balanced partitioning cannot improve
    # over equal-duration and risks creating runt chunks from noisy cost estimates.
    mean_cost = sum(segment_costs) / len(segment_costs)
    if mean_cost > 0:
        variance = sum((c - mean_cost) ** 2 for c in segment_costs) / len(segment_costs)
        cv = (variance ** 0.5) / mean_cost
        if cv < 0.20:
            return _equal_duration_plan(input_path, metadata, num_chunks, temp_dir, estimated_total_runtime)

    total_cost = float(sum(segment_costs))
    target_cost = total_cost / max(1, num_chunks)
    chunks: list[ChunkTask] = []
    rationale = [
        f"{policy} partitioning targets cost-balanced contiguous chunks.",
        f"Target chunk cost: {target_cost:.4f} estimated seconds-equivalent.",
    ]
    current_start = segments[0].start
    current_cost = 0.0
    current_ids: list[int] = []
    current_segment_start = 0
    chunk_id = 0

    for index, segment in enumerate(segments):
        current_cost += segment_costs[index]
        current_ids.append(segment.segment_id)
        segments_left = len(segments) - (index + 1)
        chunks_left = num_chunks - (chunk_id + 1)
        should_cut = chunks_left > 0 and current_cost >= target_cost and segments_left >= chunks_left
        is_last_segment = index == len(segments) - 1
        if should_cut or is_last_segment:
            end = segment.end if is_last_segment else segment.end
            duration = max(0.001, end - current_start)
            estimated_cost = current_cost
            if estimated_total_runtime and total_cost > 0:
                estimated_cost = estimated_total_runtime * (current_cost / total_cost)
            chunks.append(
                ChunkTask(
                    chunk_id=chunk_id,
                    start=round(current_start, 6),
                    duration=round(duration, 6),
                    input_path=input_path,
                    output_path=_chunk_output_path(temp_dir, chunk_id),
                    estimated_cost=estimated_cost,
                    source_segment_ids=list(current_ids),
                    rationale=f"Balanced segments {current_segment_start}-{segment.segment_id} under {policy}.",
                )
            )
            rationale.append(
                f"Chunk {chunk_id}: start={current_start:.3f}s duration={duration:.3f}s estimated_cost={estimated_cost:.3f}"
            )
            chunk_id += 1
            if chunk_id >= num_chunks:
                break
            current_ids = []
            current_cost = 0.0
            if index + 1 < len(segments):
                current_segment_start = segments[index + 1].segment_id
                current_start = segments[index + 1].start

    if chunk_id < num_chunks and chunks:
        remaining = num_chunks - chunk_id
        tail_start = chunks[-1].start + chunks[-1].duration
        tail_duration = metadata.duration - tail_start
        if tail_duration > 1e-3:
            for extra_id in range(remaining):
                duration = tail_duration / remaining if extra_id < remaining - 1 else max(
                    0.001, metadata.duration - tail_start - (tail_duration / remaining) * extra_id
                )
                chunk_start = tail_start + (tail_duration / remaining) * extra_id
                chunks.append(
                    ChunkTask(
                        chunk_id=chunk_id + extra_id,
                        start=round(chunk_start, 6),
                        duration=round(duration, 6),
                        input_path=input_path,
                        output_path=_chunk_output_path(temp_dir, chunk_id + extra_id),
                        estimated_cost=None,
                        rationale="Tail refinement after cost-balanced partitioning",
                    )
                )
        else:
            rationale.append(
                f"Generated {len(chunks)} chunks instead of requested {num_chunks}; no remaining tail duration after cost balancing."
            )

    planning_time = time.perf_counter() - start_time
    return PartitionPlan(
        policy=policy,
        chunks=chunks[:num_chunks],
        rationale=rationale,
        total_estimated_cost=estimated_total_runtime or total_cost,
        planning_time=planning_time,
    )


def _interpolate_rate(profile: list[tuple[float, float]], pos: float) -> float:
    """Linearly interpolate encode rate at a given position from a sorted profile."""
    if pos <= profile[0][0]:
        return profile[0][1]
    if pos >= profile[-1][0]:
        return profile[-1][1]
    for i in range(len(profile) - 1):
        p0, r0 = profile[i]
        p1, r1 = profile[i + 1]
        if p0 <= pos <= p1:
            t = (pos - p0) / max(1e-9, p1 - p0)
            return r0 + t * (r1 - r0)
    return profile[-1][1]


def _rate_adjusted_plan(
    input_path: str,
    metadata: VideoMetadata,
    num_chunks: int,
    temp_dir: str,
    rate_profile: list[tuple[float, float]],
    estimated_total_runtime: Optional[float] = None,
) -> PartitionPlan:
    """Create chunks with durations inversely proportional to local encode rate.

    The rate profile maps video positions to measured encode rates (seconds of
    encode per second of video).  Chunks are placed so that each chunk has
    approximately equal predicted encode time, reducing straggler-driven
    makespan inflation.
    """
    start_time = time.perf_counter()

    if len(rate_profile) < 2 or num_chunks <= 1:
        return _equal_duration_plan(input_path, metadata, num_chunks, temp_dir, estimated_total_runtime)

    profile = sorted(rate_profile, key=lambda x: x[0])

    # Check rate uniformity — if uniform, equal-duration is optimal.
    rates = [r for _, r in profile]
    mean_rate = sum(rates) / len(rates)
    if mean_rate > 0:
        max_dev = max(abs(r - mean_rate) / mean_rate for r in rates)
        if max_dev < 0.05:
            plan = _equal_duration_plan(input_path, metadata, num_chunks, temp_dir, estimated_total_runtime)
            plan.rationale.append(
                f"Rate-adjusted: rate profile uniform (max deviation {max_dev:.1%}), using equal-duration."
            )
            return plan

    # Compute cumulative work using midpoint integration.
    n_steps = 200
    step = metadata.duration / n_steps
    cum_work = [0.0]
    for i in range(n_steps):
        mid = (i + 0.5) * step
        cum_work.append(cum_work[-1] + _interpolate_rate(profile, mid) * step)
    total_work = cum_work[-1]
    target_per_chunk = total_work / num_chunks

    # Find chunk boundaries that equalize predicted work.
    boundaries: list[float] = [0.0]
    for c in range(1, num_chunks):
        target = c * target_per_chunk
        for j in range(1, len(cum_work)):
            if cum_work[j] >= target:
                frac = (target - cum_work[j - 1]) / max(1e-9, cum_work[j] - cum_work[j - 1])
                pos = ((j - 1) + frac) * step
                boundaries.append(min(metadata.duration, max(boundaries[-1] + 0.1, pos)))
                break
        else:
            boundaries.append(min(metadata.duration, boundaries[-1] + metadata.duration / num_chunks))
    boundaries.append(metadata.duration)

    chunks: list[ChunkTask] = []
    for chunk_id in range(num_chunks):
        s = boundaries[chunk_id]
        d = max(0.001, boundaries[chunk_id + 1] - s)
        # Predicted cost from rate integration.
        chunk_work = 0.0
        ns = max(1, int(d / step * 2))
        for i in range(ns):
            mid = s + (i + 0.5) * d / ns
            chunk_work += _interpolate_rate(profile, mid) * d / ns
        est_cost = chunk_work
        if estimated_total_runtime and total_work > 0:
            est_cost = estimated_total_runtime * (chunk_work / total_work)

        chunks.append(
            ChunkTask(
                chunk_id=chunk_id,
                start=round(s, 6),
                duration=round(d, 6),
                input_path=input_path,
                output_path=_chunk_output_path(temp_dir, chunk_id),
                estimated_cost=est_cost,
                rationale=f"Rate-adjusted chunk {chunk_id}: {s:.3f}-{s + d:.3f}s",
            )
        )

    planning_time = time.perf_counter() - start_time
    durations = [c.duration for c in chunks]
    equal_dur = metadata.duration / num_chunks
    return PartitionPlan(
        policy="rate-adjusted",
        chunks=chunks,
        rationale=[
            f"Rate-adjusted partitioning: {num_chunks} chunks from {len(rate_profile)}-point profile.",
            f"Duration range: {min(durations):.3f}-{max(durations):.3f}s (vs equal {equal_dur:.3f}s).",
        ],
        total_estimated_cost=float(estimated_total_runtime or total_work),
        planning_time=planning_time,
    )


def build_partition_plan(
    input_path: str,
    metadata: VideoMetadata,
    temp_dir: str,
    policy: str,
    num_chunks: int,
    feature_result: Optional[FeatureExtractionResult] = None,
    estimated_total_runtime: Optional[float] = None,
    estimator: Optional[LinearCostEstimator] = None,
    rate_profile: Optional[list[tuple[float, float]]] = None,
) -> PartitionPlan:
    if policy == "serial":
        return _serial_plan(input_path, metadata, temp_dir, estimated_total_runtime)
    if policy == "rate-adjusted" and rate_profile:
        return _rate_adjusted_plan(
            input_path, metadata, num_chunks, temp_dir, rate_profile, estimated_total_runtime,
        )
    if policy == "equal-duration" or feature_result is None:
        return _equal_duration_plan(input_path, metadata, num_chunks, temp_dir, estimated_total_runtime)
    if policy not in {"heuristic-adaptive", "ml-adaptive"}:
        raise ValueError(f"Unsupported partition policy: {policy}")
    costs = _window_costs(feature_result, policy, estimator)
    return _build_cost_balanced_chunks(
        input_path=input_path,
        metadata=metadata,
        segments=feature_result.segment_features,
        segment_costs=costs,
        num_chunks=num_chunks,
        temp_dir=temp_dir,
        policy=policy,
        estimated_total_runtime=estimated_total_runtime,
    )
