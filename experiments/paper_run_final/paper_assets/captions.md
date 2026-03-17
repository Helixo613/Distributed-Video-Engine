# Paper Captions

## Table Captions

### Table 1 (table1_main_comparison.csv)

**Execution selection results across 13 preprocessing configurations.** Each row represents a unique (video, workload) case evaluated with 3 trials. Serial and static-equal (fixed w=4) baselines are compared against the adaptive-scheduled selector. The selector wins outright in 10/13 cases and makes a good decision (matching or beating the best baseline within trial noise) in 12/13 cases. The one miss is a conservative serial selection on a 3-second clip where parallel overhead is overestimated.

### Table 2 (table2_calibration.csv)

**Cost model prediction accuracy.** Mean absolute error (MAE) of predicted vs. measured runtime for adaptive-scheduled runs. Overall MAE is 7.2% (7.8% on parallel predictions only). The model is most accurate on compute-dominated heavy workloads (2.9% MAE) and least accurate on overhead-dominated light workloads (13.2% MAE), where small absolute errors produce large relative errors.

### Table 3 (table3_budget_tradeoffs.csv)

**Selector efficiency under worker budget constraints.** Mean speedup and efficiency (speedup per worker) across 13 cases at four budget levels. Efficiency decreases from 80.5% at w<=2 to 52.5% at w<=8, reflecting diminishing returns from additional workers. The selector adapts its configuration to each budget, choosing fewer workers when constrained rather than defaulting to the maximum.

## Figure Captions

### Figure 1 (figure1_speedup_comparison)

**Execution time comparison across preprocessing workloads.** Grouped bars show serial (gray), static-equal with w=4 (blue), and adaptive-scheduled (orange) runtimes for each of 13 cases. The selector matches or improves on static-equal in 12/13 cases, with the largest gains on 30-second heavy and medium workloads (up to 26% faster than static-equal). The 3-second light case shows the selector's conservative serial choice, which is slower than the static-equal baseline.

### Figure 2 (figure2_calibration_scatter)

**Cost model calibration: predicted vs. measured runtime.** Each point represents one adaptive-scheduled trial (n=39), colored by workload intensity. Points near the diagonal indicate accurate predictions. Heavy (red) and medium (blue) predictions cluster tightly along the line; light (green) predictions show more scatter due to the overhead-dominated regime where small absolute errors produce larger relative deviations.

### Figure 3 (figure3_budget_tradeoffs)

**Resource-budgeted selection: speedup and efficiency vs. worker budget.** Mean speedup (orange, left axis) increases from 1.56x at w<=2 to 2.84x at w<=8, then plateaus at the unconstrained level. Mean efficiency (blue, right axis) decreases from 80.5% to 52.5% over the same range, showing diminishing returns. The plateau between w<=8 and unconstrained indicates that 8 workers capture the available parallelism for these workloads.

### Figure 4 (figure4_selector_decisions)

**Selector decisions per case.** Bar height indicates the number of workers selected; color indicates decision quality (green = good parallel, yellow = good serial, red = miss). The selector chooses w=8 for 30-second clips, w=4 for 12-second clips, and serial (w=1) for the 3-second clip. The single red bar marks the conservative serial selection on the 3-second light case, where the cost model overestimates orchestration overhead.
