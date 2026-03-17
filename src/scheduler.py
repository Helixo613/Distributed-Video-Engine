from __future__ import annotations

from typing import Optional

from adaptive_partitioner import build_partition_plan
from cost_estimator import LinearCostEstimator
from video_types import CandidatePlan, FeatureExtractionResult, SchedulerDecision, SelectionResult, VideoMetadata


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

MIN_CHUNK_DURATION_SECONDS = 3.0
PARALLEL_SPEEDUP_MARGIN = 0.08
MIN_PARALLEL_GAIN_SECONDS = 0.3


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


def _resolution_factor(metadata: VideoMetadata) -> float:
    return metadata.pixel_count / float(1920 * 1080) if metadata.pixel_count else 1.0


def _parallel_penalty(metadata: VideoMetadata, workers: int, chunk_count: int) -> float:
    resolution_factor = _resolution_factor(metadata)
    return 1.0 + 0.10 * max(0, workers - 1) + 0.03 * max(0, chunk_count - 1) + 0.08 * min(3.0, resolution_factor)


def _serial_decision(serial_time: float, rationale: list[str] | None = None) -> SchedulerDecision:
    return SchedulerDecision(
        worker_count=1,
        chunk_count=1,
        partition_policy="serial",
        predicted_total_time=serial_time,
        estimated_serial_time=serial_time,
        estimated_chunk_costs=[serial_time],
        predicted_compute_time=serial_time,
        overheads={"probe": 0.0, "feature": 0.0, "partition": 0.0, "dispatch": 0.0, "merge": 0.0, "overhead": 0.0},
        rationale=rationale or ["Serial execution retained as a scheduler candidate."],
    )


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
    serial_reference_time: Optional[float] = None,
    measured_overheads: Optional[dict[str, float]] = None,
    estimator: Optional[LinearCostEstimator] = None,
    rate_profile: Optional[list[tuple[float, float]]] = None,
) -> SchedulerDecision:
    estimated_serial = serial_reference_time or estimate_serial_runtime(
        metadata=metadata,
        feature_result=feature_result,
        filter_chain=filter_chain,
        serial_sample_time=serial_sample_time,
    )
    max_segments = len(feature_result.segment_features) if feature_result is not None else num_chunks
    effective_chunk_count = min(num_chunks, max_segments) if partition_policy in {"heuristic-adaptive", "ml-adaptive"} else num_chunks
    partition_plan = build_partition_plan(
        input_path=input_path,
        metadata=metadata,
        temp_dir=temp_dir,
        policy=partition_policy,
        num_chunks=effective_chunk_count,
        feature_result=feature_result,
        estimated_total_runtime=estimated_serial,
        estimator=estimator,
        rate_profile=rate_profile,
    )
    chunk_costs = [float(chunk.estimated_cost or 0.0) for chunk in partition_plan.chunks]
    raw_makespan = simulate_makespan(chunk_costs, workers)
    compute_time = raw_makespan * _parallel_penalty(metadata, workers, len(partition_plan.chunks))

    measured_overheads = measured_overheads or {}
    chunk_count = len(partition_plan.chunks)
    # Probe and feature extraction are sunk costs — already paid before the scheduler
    # runs, and paid equally by serial and parallel paths.  Excluding them from the
    # go/no-go comparison removes the systematic bias toward serial that inflated
    # parallel predictions by 0.3-0.9 s while serial predictions carried no such term.
    # Dispatch, merge, and per-process overhead estimates are calibrated against
    # measured values from V3 benchmark runs (actual dispatch ≈ 0.002 s,
    # actual merge ≈ 0.09-0.17 s for 4 chunks).
    overheads = {
        "probe": 0.0,
        "feature": 0.0,
        "partition": float(measured_overheads.get("partition", partition_plan.planning_time)),
        "dispatch": float(measured_overheads.get("dispatch", 0.005)),
        "merge": float(
            measured_overheads.get(
                "merge",
                0.06 + 0.012 * chunk_count + 0.002 * metadata.duration,
            )
        ),
        "overhead": float(
            measured_overheads.get(
                "overhead",
                0.01 * chunk_count + 0.01 * max(0, workers - 1),
            )
        ),
    }
    total = sum(overheads.values()) + compute_time
    rationale = [
        f"Predicted with workers={workers}, chunks={num_chunks}, policy={partition_policy}.",
        f"Estimated serial runtime: {estimated_serial:.3f}s.",
        f"Predicted compute makespan after list scheduling: {compute_time:.3f}s.",
        f"Conservative parallel penalty factor: {_parallel_penalty(metadata, workers, len(partition_plan.chunks)):.3f}.",
    ] + list(partition_plan.rationale[:3])
    return SchedulerDecision(
        worker_count=workers,
        chunk_count=effective_chunk_count,
        partition_policy=partition_policy,
        predicted_total_time=total,
        estimated_serial_time=estimated_serial,
        estimated_chunk_costs=chunk_costs,
        predicted_compute_time=compute_time,
        overheads=overheads,
        rationale=rationale,
    )


def _decision_to_candidate(
    decision: SchedulerDecision,
    label: str,
) -> CandidatePlan:
    """Convert a SchedulerDecision into a CandidatePlan for symmetric comparison."""
    regime = "serial" if decision.worker_count <= 1 and decision.partition_policy == "serial" else "parallel"
    return CandidatePlan(
        label=label,
        regime=regime,
        worker_count=decision.worker_count,
        chunk_count=decision.chunk_count,
        partition_policy=decision.partition_policy,
        predicted_compute_time=decision.predicted_compute_time,
        predicted_e2e_time=decision.predicted_total_time,
        estimated_serial_time=decision.estimated_serial_time,
        estimated_chunk_costs=list(decision.estimated_chunk_costs),
        overheads=dict(decision.overheads),
        rationale=list(decision.rationale),
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
    serial_reference_time: Optional[float] = None,
    measured_overheads: Optional[dict[str, float]] = None,
    estimator: Optional[LinearCostEstimator] = None,
    rate_profile: Optional[list[tuple[float, float]]] = None,
    max_workers: Optional[int] = None,
) -> SelectionResult:
    # Apply resource budget: restrict to workers within budget
    if max_workers is not None:
        workers = [w for w in workers if w <= max_workers]
        if not workers:
            workers = [1]

    search_trace: list[dict[str, float | int | str]] = []
    serial_time = serial_reference_time or estimate_serial_runtime(
        metadata=metadata,
        feature_result=feature_result,
        filter_chain=filter_chain,
        serial_sample_time=serial_sample_time,
    )
    serial_decision = _serial_decision(
        serial_time,
        rationale=[
            f"Serial candidate predicted at {serial_time:.3f}s.",
            "Serial remains eligible when estimated parallel benefit is not decisively better than overhead.",
        ],
    )
    serial_candidate = _decision_to_candidate(serial_decision, "serial")
    search_trace.append(
        {
            "workers": 1,
            "chunks": 1,
            "policy": "serial",
            "predicted_total_time": serial_decision.predicted_total_time,
            "predicted_compute_time": serial_decision.predicted_compute_time,
        }
    )

    # Build the set of partition policies to search.  Always include the
    # requested policy and equal-duration.  When a rate profile is available,
    # include rate-adjusted as a candidate — the partitioner will fall back to
    # equal-duration automatically if the profile is too uniform.
    policies_to_try: list[str] = []
    if partition_policy not in policies_to_try:
        policies_to_try.append(partition_policy)
    if "equal-duration" not in policies_to_try:
        policies_to_try.append("equal-duration")
    if rate_profile and len(rate_profile) >= 2 and "rate-adjusted" not in policies_to_try:
        policies_to_try.append("rate-adjusted")

    # Classify policies into static (equal-duration) vs adaptive (everything else)
    static_policies = {"equal-duration"}
    # Track best candidate per category: static-equal and adaptive-searched
    best_static_equal: Optional[SchedulerDecision] = None
    best_adaptive: Optional[SchedulerDecision] = None

    max_useful_workers = max(1, min(max(workers), int(metadata.duration // MIN_CHUNK_DURATION_SECONDS)))
    for worker_count in workers:
        if worker_count > max_useful_workers:
            continue
        for multiplier in chunk_multipliers:
            chunk_count = max(worker_count, int(round(worker_count * multiplier)))
            if metadata.duration / max(1, chunk_count) < MIN_CHUNK_DURATION_SECONDS:
                continue
            for policy in policies_to_try:
                decision = predict_total_time(
                    input_path=input_path,
                    metadata=metadata,
                    feature_result=feature_result,
                    workers=worker_count,
                    num_chunks=chunk_count,
                    partition_policy=policy,
                    filter_chain=filter_chain,
                    temp_dir=temp_dir,
                    serial_sample_time=serial_sample_time,
                    serial_reference_time=serial_reference_time,
                    measured_overheads=measured_overheads,
                    estimator=estimator,
                    rate_profile=rate_profile,
                )
                search_trace.append(
                    {
                        "workers": worker_count,
                        "chunks": chunk_count,
                        "policy": policy,
                        "predicted_total_time": decision.predicted_total_time,
                        "predicted_compute_time": decision.predicted_compute_time,
                    }
                )
                if policy in static_policies:
                    if best_static_equal is None or decision.predicted_total_time < best_static_equal.predicted_total_time:
                        best_static_equal = decision
                else:
                    if best_adaptive is None or decision.predicted_total_time < best_adaptive.predicted_total_time:
                        best_adaptive = decision

    # Build symmetric candidate list
    candidates: list[CandidatePlan] = [serial_candidate]
    if best_static_equal is not None:
        candidates.append(_decision_to_candidate(best_static_equal, "static-equal"))
    if best_adaptive is not None:
        candidates.append(_decision_to_candidate(best_adaptive, "adaptive-searched"))

    # Select winner: best predicted e2e time, subject to safety margin vs serial
    parallel_candidates = [c for c in candidates if c.regime == "parallel"]
    best_parallel = min(parallel_candidates, key=lambda c: c.predicted_e2e_time) if parallel_candidates else None

    selection_rationale: list[str] = []
    if best_parallel is None:
        selected = serial_candidate
        selection_rationale.append("All parallel candidates were pruned by conservative scheduler guardrails.")
    else:
        serial_threshold = min(
            serial_time - MIN_PARALLEL_GAIN_SECONDS,
            serial_time * (1.0 - PARALLEL_SPEEDUP_MARGIN),
        )
        if best_parallel.predicted_e2e_time < serial_threshold:
            selected = best_parallel
            selection_rationale.append(
                f"Best parallel prediction {best_parallel.predicted_e2e_time:.3f}s "
                f"({best_parallel.label}, {best_parallel.partition_policy}, "
                f"w={best_parallel.worker_count}, c={best_parallel.chunk_count}) "
                f"cleared serial {serial_time:.3f}s by the configured safety margin."
            )
        else:
            selected = serial_candidate
            selection_rationale.append(
                f"Best parallel prediction was {best_parallel.predicted_e2e_time:.3f}s "
                f"versus serial {serial_time:.3f}s; safety margin kept serial."
            )

    n_policies = len(policies_to_try)
    n_candidates = len(search_trace)
    budget_note = f" (worker budget: max_workers={max_workers})" if max_workers is not None else " (unconstrained)"
    selection_rationale.append(
        f"Searched {n_candidates} candidates across {n_policies} partition policies: {policies_to_try}.{budget_note}"
    )

    # Summarize all category candidates for transparency
    for candidate in candidates:
        selection_rationale.append(
            f"  [{candidate.label}] regime={candidate.regime}, "
            f"w={candidate.worker_count}, c={candidate.chunk_count}, "
            f"policy={candidate.partition_policy}, "
            f"predicted_e2e={candidate.predicted_e2e_time:.3f}s"
        )

    return SelectionResult(
        selected=selected,
        candidates=candidates,
        selection_rationale=selection_rationale,
        search_trace=search_trace,
        estimated_serial_time=serial_time,
    )
