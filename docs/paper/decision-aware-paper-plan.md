# Decision-Aware Paper Rewrite Plan

## Working Title

Decision-Aware Execution Selection for Media Preprocessing

## Core Thesis

For short, content-variable media preprocessing jobs, both parallel execution overhead and decision overhead matter. We model the full cost of execution selection, including feature extraction and scheduling time, and only apply adaptive selection when its expected benefit exceeds its decision cost.

## Implementation Work

- Add explicit timing fields to every experiment record:
  - `T_metadata`: video/container probing time.
  - `T_features`: feature extraction time.
  - `T_scheduler`: selector and cost-model search time.
  - `T_decide`: `T_metadata + T_features + T_scheduler`.
  - `T_execute`: actual FFmpeg execution time.
  - `rho`: `T_decide / T_execute`.
- Expose the same fields through the live API so the UI can demonstrate decision overhead during class presentation.
- Extend the summary script so `summary.csv` and `summary.json` report mean decision time and mean rho for adaptive runs.
- Re-run the benchmark set after instrumentation so all paper claims use measured decision costs, not estimated values.

## Paper Rewrite Work

- Rewrite the abstract around short jobs, decision overhead, rho, and measured selector results.
- Rewrite the introduction with this gap: existing scheduling work often treats decision cost as negligible, but short media preprocessing jobs can make that assumption false.
- Add a formal subsection defining rho and explaining how decision cost is measured.
- Make the rho figure the central result:
  - x-axis: execution/runtime scale.
  - y-axis: `rho = T_decide / T_execute`.
  - color/marker: adaptive beneficial vs default safer.
- Keep the existing selector, cost model, partitioning strategies, quality validation, and benchmark comparisons as supporting evidence.
- Add a limitations section: one machine, limited workload count, rho is hardware-dependent, GPU behavior still needs separate validation.

## Claims We Should Avoid

- Do not claim microsecond or millisecond decision cost unless the rerun measures it.
- Do not claim a universal rho threshold; derive the threshold from the benchmark data.
- Do not claim no prior work models decision cost until the literature review verifies it.
- Do not present GPU acceleration as evaluated unless we run GPU experiments.

## LaTeX Rewrite Target

Use the IEEE template as the base and write the new paper around these sections:

1. Abstract
2. Introduction
3. Background and Motivation
4. Decision-Aware Execution Selection
5. Implementation
6. Experimental Methodology
7. Results
8. Related Work
9. Limitations and Threats to Validity
10. Conclusion
