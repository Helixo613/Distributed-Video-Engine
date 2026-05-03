# Research Demo UI Design

Date: 2026-05-03

## Purpose

Create a professional React UI for the Distributed Video Engine project that supports a class presentation and makes the research novelty clear to students and a teacher/reviewer.

The UI should not present the project as a generic video processing dashboard. It should explain and demonstrate the research contribution: an overhead-aware adaptive execution selector for media preprocessing workloads in cloud AI pipelines.

## Audience

Primary audience:

- Students in a class presentation who need a clear, visual explanation of the project.
- A teacher who will also act as a reviewer and needs to understand the novelty, contribution, method, and evidence.

Design implication:

- The first screen should establish the research thesis quickly.
- Controls should support the story rather than compete with it.
- The interface should be presentation-safe if the backend is unavailable.

## Core Thesis

The UI should repeatedly reinforce one sentence:

> This project does not merely parallelize video preprocessing; it decides whether parallelism is worth it, then chooses a resource plan using video features and an overhead-aware prediction model.

## Approved Direction

Use a hybrid **Story + Demonstration** interface.

The application should have four top-level sections:

1. Story Mode
2. Live Demo
3. Evidence
4. Architecture

This preserves the strengths of the current dashboard while reframing it as a research demonstration.

## Screen Design

### Story Mode

Story Mode is the presenter-driven walkthrough.

It should explain:

1. Cloud AI pipelines preprocess media before downstream models.
2. Fixed parallel preprocessing is not always optimal.
3. Short or lightweight clips can become overhead-dominated.
4. Longer or heavier clips may benefit from more workers.
5. The project novelty is pre-execution regime selection: serial vs parallel, worker count, chunk count, and partitioning policy.

Expected UI elements:

- Research thesis header.
- Step navigation: Problem, Baseline Failure, Method, Selector Decision, Results, Contributions.
- Simple serial vs fixed-parallel comparison.
- Clear novelty callout.
- Contribution list.

### Live Demo

Live Demo is the working demonstration surface.

It should allow the presenter to choose or upload a video, choose workload intensity, set a worker budget, and run or simulate the selector.

Expected UI elements:

- Video/workload selection.
- Workload presets: light, medium, heavy.
- Worker budget control.
- Scheduler decision panel.
- Feature summary: motion, scene cuts, texture, duration, bitrate, workload intensity.
- Execution plan: serial or parallel, workers, chunks, partition policy.
- Runtime visualization or chunk timeline.

The most important element is the scheduler decision panel. It should explain why the selected execution regime was chosen, not only show the output configuration.

### Evidence

Evidence is the reviewer-facing proof section.

It should show paper-aligned results from the repository:

- Adaptive-scheduled wins outright in 10/13 cases.
- Selector decisions are good in 12/13 cases.
- Speedup of 1.9x-4.0x over serial on parallel-favorable cases.
- Cost model mean absolute prediction error around 7% overall.
- Parallel-only prediction error around 8%.
- Quality preservation with PSNR/SSIM.
- Resource budget tradeoffs showing diminishing returns under worker budgets.

Expected UI elements:

- Key result cards.
- Runtime comparison chart.
- Prediction error chart or compact calibration panel.
- Resource budget tradeoff chart.
- Quality preservation summary.

### Architecture

Architecture explains how the system works internally.

It should show the pipeline:

1. ffprobe metadata extraction
2. Low-cost feature extraction
3. Overhead-aware scheduler
4. Adaptive partitioning
5. FFmpeg worker execution
6. Merge
7. Evaluation and logging

Expected UI elements:

- Horizontal or vertical pipeline diagram.
- Highlighted scheduler block.
- Inputs and outputs for each stage.
- Brief mapping to repository modules such as `src/feature_extractor.py`, `src/scheduler.py`, `src/adaptive_partitioner.py`, `src/pipeline.py`, and `src/evaluator.py`.

## Component Plan

Use the existing React/Vite frontend and add focused research-demo components.

Recommended components:

- `ResearchHero`: thesis, novelty, and guided demo entry.
- `StoryMode`: presentation sequence and contribution framing.
- `SelectorDecisionPanel`: serial vs parallel decision, workers, chunks, predicted speedup, overhead reasoning.
- `EvidenceDashboard`: paper metrics and charts.
- `ArchitectureFlow`: visual pipeline and module mapping.
- `DemoControls`: video choice, workload intensity, budget, and run controls.

Existing components can be reused or restyled where useful:

- `VideoUpload`
- `ChunkVisualizer`
- `SpeedupComparison`
- `LiveBenchmarkComparison`
- `JobList`

## Data Flow

The UI should support two modes:

1. Live backend mode
2. Presentation dataset mode

Live backend mode:

- Use existing endpoints such as `/health`, `/jobs`, and `/stats` where available.
- Populate job progress, selected engine version, scheduler outputs, and runtime metrics from backend responses.

Presentation dataset mode:

- If the backend is unavailable, use static paper-backed scenarios from repository results and documentation.
- The UI should clearly indicate that it is showing presentation data.
- The presentation should remain complete and professional without a running backend.

This fallback is required because the UI is intended for a class presentation.

## Error Handling

If backend calls fail:

- Do not show a broken empty dashboard.
- Switch to presentation dataset mode.
- Keep the Story, Evidence, and Architecture sections usable.
- Disable or label live-only actions clearly.

If a job fails:

- Show the failure in the Live Demo section.
- Keep Evidence and Architecture sections available.
- Preserve the selected scenario and controls so the presenter can continue.

## Visual Direction

The UI should feel like a professional research system dashboard, not a marketing landing page.

Visual requirements:

- Clean dark or neutral technical theme.
- Strong hierarchy for novelty, contribution, and decision rationale.
- Avoid decorative visuals that do not explain the system.
- Use charts, pipeline diagrams, compact cards, and decision panels.
- Keep the layout presentation-friendly on a laptop projector.
- Ensure the first viewport communicates the project name and research thesis.

## Testing And Verification

Implementation should be verified with:

- `npm run build` in `frontend/`.
- Browser inspection of the Vite app.
- Desktop screenshot check for presentation layout.
- Mobile or narrow viewport check to ensure text and controls do not overlap.

If the backend is not available during verification, presentation dataset mode must still render a complete demo.

## Out Of Scope

This design does not require:

- Rewriting the backend API.
- Replacing the research pipeline.
- Building a full slide deck.
- Adding authentication or multi-user behavior.
- Uploading changes to GitHub.

## Approval Status

Approved direction from the user:

- Audience: class presentation for students and teacher/reviewer.
- Priority: make novelty and contributions clearer.
- Structure: hybrid Story + Demonstration UI.
- Screen set: Story Mode, Live Demo, Evidence, Architecture.
