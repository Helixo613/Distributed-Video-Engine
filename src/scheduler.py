from __future__ import annotations

from typing import Optional

from adaptive_partitioner import build_partition_plan
from cost_estimator import LinearCostEstimator
from video_types import FeatureExtractionResult, SchedulerDecision, VideoMetadata


FILTER_COMPLEXITY_WEIGHTS = {
    "hqdn3d": 1.8,
    "unsharp": 1.3,
    "eq": 1.05,
    "boxblur": 1.4,
    "gblur": 1.4,
    "scale": 1.1,
    "fps": 1.0,
    "yadif": 1.5,
}


def estimate_filter_complexity(filter_chain: str) -> float:
    weight = 1.0
    for token in filter_chain.split(","):
        name = token.split("=", 1)[0].strip()
        weight *= FILTER_COMPLEXITY_WEIGHTS.get(name, 1.0)
    return max(0.75, min(weight, 4.0))


def estimate_serial_runtime(
    metadata: VideoMetadata,
    feature_result: Optional[FeatureExtractionResult],
    filter_chain: str,
    serial_sample_time: Optional[float],
    sample_seconds: float = 2.0,
) -> float:
    if serial_sample_time is not None and metadata.duration > 0:
        bench_duration = min(sample_seconds, metadata.duration)
        return (metadata.duration / bench_duration) * serial_sample_time

    resolution_factor = metadata.pixel_count / float(1920 * 1080) if metadata.pixel_count else 1.0
    motion_factor = 1.0
    if feature_result is not None:
        motion_factor += min(1.0, feature_result.global_features.get("motion_proxy", 0.0) / 64.0) * 0.5
        motion_factor += feature_result.global_features.get("scene_change_proxy", 0.0) * 0.25
    return metadata.duration * max(0.2, resolution_factor) * estimate_filter_complexity(filter_chain) * motion_factor


def simulate_makespan(chunk_costs: list[float], workers: int) -> float:
    if not chunk_costs:
        return 0.0
    lanes = [0.0 for _ in range(max(1, workers))]
    for cost in sorted(chunk_costs, reverse=True):
        lane = min(range(len(lanes)), key=lanes.__getitem__)
        lanes[lane] += cost
    return max(lanes)


def predict_total_time(
    input_path: str,
    metadata: VideoMetadata,
    feature_result: Optional[FeatureExtractionResult],
    workers: int,
    num_chunks: int,
    partition_policy: str,
    filter_chain: str,
    temp_dir: str,
    serial_sample_time: Optional[float] = None,
    measured_overheads: Optional[dict[str, float]] = None,
    estimator: Optional[LinearCostEstimator] = None,
) -> SchedulerDecision:
    estimated_serial = estimate_serial_runtime(
        metadata=metadata,
        feature_result=feature_result,
        filter_chain=filter_chain,
        serial_sample_time=serial_sample_time,
    )
    partition_plan = build_partition_plan(
        input_path=input_path,
        metadata=metadata,
        temp_dir=temp_dir,
        policy=partition_policy,
        num_chunks=num_chunks,
        feature_result=feature_result,
        estimated_total_runtime=estimated_serial,
        estimator=estimator,
    )
    chunk_costs = [float(chunk.estimated_cost or 0.0) for chunk in partition_plan.chunks]
    compute_time = simulate_makespan(chunk_costs, workers)

    measured_overheads = measured_overheads or {}
    overheads = {
        "probe": float(measured_overheads.get("probe", 0.05)),
        "feature": float(measured_overheads.get("feature", feature_result.extraction_time if feature_result else 0.0)),
        "partition": float(measured_overheads.get("partition", partition_plan.planning_time)),
        "dispatch": float(measured_overheads.get("dispatch", 0.025 * num_chunks + 0.01 * workers)),
        "merge": float(measured_overheads.get("merge", 0.15 + 0.01 * num_chunks)),
        "overhead": float(measured_overheads.get("overhead", 0.02 * num_chunks + 0.01 * max(0, workers - 1))),
    }
    total = sum(overheads.values()) + compute_time
    rationale = [
        f"Predicted with workers={workers}, chunks={num_chunks}, policy={partition_policy}.",
        f"Estimated serial runtime: {estimated_serial:.3f}s.",
        f"Predicted compute makespan after list scheduling: {compute_time:.3f}s.",
    ] + list(partition_plan.rationale[:3])
    return SchedulerDecision(
        worker_count=workers,
        chunk_count=num_chunks,
        partition_policy=partition_policy,
        predicted_total_time=total,
        estimated_serial_time=estimated_serial,
        estimated_chunk_costs=chunk_costs,
        predicted_compute_time=compute_time,
        overheads=overheads,
        rationale=rationale,
    )


def search_best_configuration(
    input_path: str,
    metadata: VideoMetadata,
    feature_result: Optional[FeatureExtractionResult],
    filter_chain: str,
    temp_dir: str,
    workers: list[int],
    chunk_multipliers: list[float],
    partition_policy: str,
    serial_sample_time: Optional[float] = None,
    measured_overheads: Optional[dict[str, float]] = None,
    estimator: Optional[LinearCostEstimator] = None,
) -> SchedulerDecision:
    search_trace: list[dict[str, float | int | str]] = []
    best: Optional[SchedulerDecision] = None
    for worker_count in workers:
        for multiplier in chunk_multipliers:
            chunk_count = max(worker_count, int(round(worker_count * multiplier)))
            decision = predict_total_time(
                input_path=input_path,
                metadata=metadata,
                feature_result=feature_result,
                workers=worker_count,
                num_chunks=chunk_count,
                partition_policy=partition_policy,
                filter_chain=filter_chain,
                temp_dir=temp_dir,
                serial_sample_time=serial_sample_time,
                measured_overheads=measured_overheads,
                estimator=estimator,
            )
            search_trace.append(
                {
                    "workers": worker_count,
                    "chunks": chunk_count,
                    "policy": partition_policy,
                    "predicted_total_time": decision.predicted_total_time,
                    "predicted_compute_time": decision.predicted_compute_time,
                }
            )
            if best is None or decision.predicted_total_time < best.predicted_total_time:
                best = decision

    if best is None:
        raise ValueError("No scheduler candidates were evaluated")
    best.search_trace = search_trace
    best.rationale.append("Scheduler performed a bounded search over worker and chunk-count candidates.")
    return best
