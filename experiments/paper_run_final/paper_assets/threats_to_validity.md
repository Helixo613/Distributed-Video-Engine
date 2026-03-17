# Threats to Validity

## Internal Validity

**Conservative serial selection on very short clips.** The selector chooses serial execution for the 3s light-workload clip based on its overhead estimate, but the fixed-parallel baseline (static-equal, w=4) is actually 26% faster on this edge case. The selector's decision is principled — it reflects a real overhead concern — but the cost model overestimates orchestration cost relative to the very short compute time. This is the only case (1/13) where the selector makes a suboptimal regime choice.

**Weaker calibration on light workloads.** The cost model achieves 2.9% MAE on heavy and 3.9% on medium workloads, but 13.2% on light workloads. Light preprocessing has near-zero per-frame compute cost, so small absolute prediction errors produce large relative errors. The model is least accurate where the decision matters least (lightweight jobs complete quickly regardless of regime).

**Near-tie cases.** Two short 12s cases show static-equal marginally faster than adaptive-scheduled (within 0.2-0.7% of runtime). The selector still makes a good decision in both — the gap is within trial noise — but these cases do not demonstrate a clear selector advantage.

## External Validity

**Single-machine evaluation.** All experiments run on a single machine with a fixed core count. Cloud environments introduce additional variability (network latency, shared-tenancy noise, heterogeneous hardware) that the cost model does not currently account for.

**FFmpeg-specific overhead structure.** The overhead model (process startup, dispatch, merge) is calibrated to FFmpeg's multiprocess execution pattern. Other preprocessing frameworks may have different overhead profiles.

**Five input videos.** The benchmark covers 3 content classes and durations from 3s to 30s, but 5 source videos is a modest sample. Results may not generalize to all content types or very long videos (>60s).

## Construct Validity

**Budget validation scope.** The measured budget validation covers 3 representative cases (serial-favorable, budget-saturating, budget-scaling) with 2.8% MAE across 12 configurations. This validates the key behavioral regimes but does not measure all 13 cases under all budget levels.
