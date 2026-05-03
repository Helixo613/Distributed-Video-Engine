import {
  Activity,
  BarChart3,
  Brain,
  Cpu,
  Film,
  GitBranch,
  Layers3,
  LineChart,
  Merge,
  ScanSearch,
  ShieldCheck,
  Timer,
  Workflow,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type ResearchSection = 'story' | 'demo' | 'evidence' | 'architecture';
export type WorkloadPreset = 'light' | 'medium' | 'heavy';
export type ExecutionRegime = 'serial' | 'parallel';

export interface StoryStep {
  id: string;
  title: string;
  eyebrow: string;
  summary: string;
  detail: string;
  contribution: string;
  icon: LucideIcon;
}

export interface DemoScenario {
  id: string;
  name: string;
  context: string;
  samplePath: string;
  sampleNote: string;
  durationSeconds: number;
  resolution: string;
  contentClass: string;
  workload: WorkloadPreset;
  featureSummary: {
    motion: number;
    sceneCuts: number;
    texture: number;
    bitrateMbps: number;
  };
  selector: {
    regime: ExecutionRegime;
    workers: number;
    chunks: number;
    policy: string;
    predictedSerialSeconds: number;
    predictedParallelSeconds: number;
    predictedSpeedup: number;
    overheadSeconds: number;
    rationale: string[];
  };
  replayComparison: BaselineComparison[];
}

export interface BaselineComparison {
  id: 'serial' | 'fixed' | 'adaptive';
  label: string;
  runtimeSeconds: number;
  workers: number;
  chunks: number;
  speedup: number;
  summary: string;
  highlight?: boolean;
}

export interface KeyResult {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
}

export interface ArchitectureStage {
  title: string;
  module: string;
  description: string;
  output: string;
  icon: LucideIcon;
}

export const storySteps: StoryStep[] = [
  {
    id: 'problem',
    eyebrow: 'Problem',
    title: 'Fixed parallelism is not always optimal',
    summary: 'Cloud AI pipelines often preprocess video with fixed worker counts.',
    detail:
      'Short or lightweight clips can spend more time on splitting, dispatching, startup, and merge overhead than on useful preprocessing work.',
    contribution:
      'The project frames execution-regime selection as the research problem, not just chunk scheduling.',
    icon: Film,
  },
  {
    id: 'features',
    eyebrow: 'Characterization',
    title: 'Cheap video features estimate processing cost before execution',
    summary: 'The system samples motion, scene changes, texture, bitrate, duration, and workload intensity.',
    detail:
      'These features are extracted at low cost so the selector can reason about the workload before launching the full preprocessing job.',
    contribution:
      'Content-aware selection lets static clips and high-motion clips receive different execution plans.',
    icon: ScanSearch,
  },
  {
    id: 'selector',
    eyebrow: 'Novelty',
    title: 'The scheduler decides whether parallelism is worth it',
    summary: 'It predicts serial runtime, parallel makespan, dispatch cost, startup cost, and merge cost.',
    detail:
      'The selector searches bounded worker and chunk candidates, then chooses serial when overhead dominates or parallel when expected speedup clears the margin.',
    contribution:
      'This is the central novelty: overhead-aware serial-versus-parallel regime selection before execution.',
    icon: Brain,
  },
  {
    id: 'evidence',
    eyebrow: 'Evidence',
    title: 'The evaluation ties the decision model to measured outcomes',
    summary: 'The paper package reports wins, speedups, prediction error, quality, and resource-budget tradeoffs.',
    detail:
      'The UI connects every live demo decision back to reviewer-facing metrics so the project reads as research, not only a dashboard.',
    contribution:
      'The system demonstrates both performance benefit and prediction quality across workload classes.',
    icon: BarChart3,
  },
];

export const demoScenarios: DemoScenario[] = [
  {
    id: 'short-light',
    name: 'Short lightweight clip',
    context: 'Overhead-dominated inference normalization',
    samplePath: 'test_input.mp4',
    sampleNote: 'Use a short clip or upload one on the demo laptop.',
    durationSeconds: 3,
    resolution: '720p',
    contentClass: 'low motion',
    workload: 'light',
    featureSummary: { motion: 18, sceneCuts: 4, texture: 26, bitrateMbps: 3.2 },
    selector: {
      regime: 'serial',
      workers: 1,
      chunks: 1,
      policy: 'serial',
      predictedSerialSeconds: 4.2,
      predictedParallelSeconds: 5.1,
      predictedSpeedup: 0.82,
      overheadSeconds: 1.4,
      rationale: [
        'The clip is short, so dispatch and merge overhead are a large fraction of total runtime.',
        'Predicted parallel speedup does not clear the safety margin.',
        'The selector conservatively chooses serial execution to avoid wasting workers.',
      ],
    },
    replayComparison: [
      {
        id: 'serial',
        label: 'Serial',
        runtimeSeconds: 4.2,
        workers: 1,
        chunks: 1,
        speedup: 1,
        summary: 'Lowest overhead path for a short lightweight sample.',
        highlight: true,
      },
      {
        id: 'fixed',
        label: 'Fixed Parallel',
        runtimeSeconds: 3.8,
        workers: 4,
        chunks: 4,
        speedup: 1.11,
        summary: 'Can be marginally faster, but spends a high fraction on orchestration.',
      },
      {
        id: 'adaptive',
        label: 'Adaptive Selector',
        runtimeSeconds: 4.2,
        workers: 1,
        chunks: 1,
        speedup: 1,
        summary: 'Chooses serial because predicted parallel gain does not clear the safety margin.',
      },
    ],
  },
  {
    id: 'medium-action',
    name: 'Medium action clip',
    context: 'Vision enhancement before analytics',
    samplePath: 'uploads/class_demo_medium.mp4',
    sampleNote: 'Upload or place a 12s motion-heavy clip at this path on the GPU laptop.',
    durationSeconds: 12,
    resolution: '1080p',
    contentClass: 'high motion',
    workload: 'medium',
    featureSummary: { motion: 72, sceneCuts: 21, texture: 64, bitrateMbps: 8.7 },
    selector: {
      regime: 'parallel',
      workers: 4,
      chunks: 6,
      policy: 'heuristic-adaptive',
      predictedSerialSeconds: 24.8,
      predictedParallelSeconds: 9.6,
      predictedSpeedup: 2.58,
      overheadSeconds: 2.1,
      rationale: [
        'Motion and texture indicate enough useful work to amortize orchestration cost.',
        'Four workers are predicted to capture most of the available speedup for this duration.',
        'Adaptive chunks reduce imbalance from uneven content complexity.',
      ],
    },
    replayComparison: [
      {
        id: 'serial',
        label: 'Serial',
        runtimeSeconds: 24.8,
        workers: 1,
        chunks: 1,
        speedup: 1,
        summary: 'Useful baseline, but leaves parallel work available.',
      },
      {
        id: 'fixed',
        label: 'Fixed Parallel',
        runtimeSeconds: 9.8,
        workers: 4,
        chunks: 4,
        speedup: 2.53,
        summary: 'Strong speedup, but equal chunks can still leave imbalance.',
      },
      {
        id: 'adaptive',
        label: 'Adaptive Selector',
        runtimeSeconds: 9.6,
        workers: 4,
        chunks: 6,
        speedup: 2.58,
        summary: 'Chooses adaptive chunking and matches the best observed path.',
        highlight: true,
      },
    ],
  },
  {
    id: 'long-heavy',
    name: 'Long noisy clip',
    context: 'Robust preprocessing for noisy media',
    samplePath: 'uploads/class_demo_heavy.mp4',
    sampleNote: 'Use a longer noisy clip on the GPU laptop for the most visible live run.',
    durationSeconds: 30,
    resolution: '1080p',
    contentClass: 'mixed motion',
    workload: 'heavy',
    featureSummary: { motion: 58, sceneCuts: 17, texture: 81, bitrateMbps: 11.4 },
    selector: {
      regime: 'parallel',
      workers: 8,
      chunks: 12,
      policy: 'heuristic-adaptive',
      predictedSerialSeconds: 86.4,
      predictedParallelSeconds: 22.7,
      predictedSpeedup: 3.81,
      overheadSeconds: 3.9,
      rationale: [
        'The heavy filter chain creates enough compute work for higher parallelism.',
        'The longer duration means startup and merge overhead are small relative to useful work.',
        'The selected worker budget gives strong speedup while avoiding excessive diminishing returns.',
      ],
    },
    replayComparison: [
      {
        id: 'serial',
        label: 'Serial',
        runtimeSeconds: 86.4,
        workers: 1,
        chunks: 1,
        speedup: 1,
        summary: 'Clear lower bound for heavy preprocessing.',
      },
      {
        id: 'fixed',
        label: 'Fixed Parallel',
        runtimeSeconds: 27.5,
        workers: 8,
        chunks: 8,
        speedup: 3.14,
        summary: 'Parallelism helps, but fixed chunks do not fully exploit the workload.',
      },
      {
        id: 'adaptive',
        label: 'Adaptive Selector',
        runtimeSeconds: 22.7,
        workers: 8,
        chunks: 12,
        speedup: 3.81,
        summary: 'Chooses more chunks and stronger parallelism after overhead is amortized.',
        highlight: true,
      },
    ],
  },
];

export const keyResults: KeyResult[] = [
  {
    label: 'Outright wins',
    value: '10 / 13',
    detail: 'Adaptive-scheduled wins across the evaluated cases.',
    icon: ShieldCheck,
  },
  {
    label: 'Good decisions',
    value: '12 / 13',
    detail: 'Selector decisions match or nearly match the best baseline.',
    icon: Brain,
  },
  {
    label: 'Speedup range',
    value: '1.9x-4.0x',
    detail: 'Measured over serial on parallel-favorable cases.',
    icon: Zap,
  },
  {
    label: 'Prediction error',
    value: '~7%',
    detail: 'Overall mean absolute prediction error from calibration analysis.',
    icon: LineChart,
  },
];

export const runtimeComparison = [
  { case: '3s light', serial: 4.2, static: 3.8, adaptive: 4.2 },
  { case: '12s medium', serial: 24.8, static: 9.8, adaptive: 9.6 },
  { case: '30s heavy', serial: 86.4, static: 27.5, adaptive: 22.7 },
];

export const budgetTradeoffs = [
  { budget: 'w<=2', efficiency: 80, speedup: 1.9 },
  { budget: 'w<=4', efficiency: 63, speedup: 2.8 },
  { budget: 'w<=8', efficiency: 53, speedup: 3.8 },
];

export const architectureStages: ArchitectureStage[] = [
  {
    title: 'Probe',
    module: 'src/ffmpeg_utils.py',
    description: 'Extract duration, resolution, FPS, codec, audio, and bitrate.',
    output: 'Video metadata',
    icon: Activity,
  },
  {
    title: 'Feature Extraction',
    module: 'src/feature_extractor.py',
    description: 'Estimate motion, scene-cut frequency, texture, and bitrate distribution.',
    output: 'Low-cost content features',
    icon: ScanSearch,
  },
  {
    title: 'Scheduler',
    module: 'src/scheduler.py',
    description: 'Predict serial and parallel runtime while modeling dispatch, startup, and merge overhead.',
    output: 'Execution regime and resource plan',
    icon: Brain,
  },
  {
    title: 'Partitioning',
    module: 'src/adaptive_partitioner.py',
    description: 'Create serial, equal-duration, heuristic-adaptive, or ml-adaptive chunk plans.',
    output: 'Chunk boundaries',
    icon: GitBranch,
  },
  {
    title: 'Execution',
    module: 'src/pipeline.py',
    description: 'Run FFmpeg workers through the selected plan.',
    output: 'Processed chunks',
    icon: Cpu,
  },
  {
    title: 'Merge',
    module: 'src/pipeline.py',
    description: 'Merge processed chunks into a final output.',
    output: 'Processed video',
    icon: Merge,
  },
  {
    title: 'Evaluation',
    module: 'src/evaluator.py',
    description: 'Compute runtime, speedup, PSNR, SSIM, and structured experiment records.',
    output: 'Research evidence',
    icon: Layers3,
  },
];

export const contributionCards = [
  {
    title: 'Execution-regime selection',
    detail: 'Chooses serial or parallel before execution instead of assuming parallelism is always beneficial.',
    icon: Workflow,
  },
  {
    title: 'Overhead-aware cost model',
    detail: 'Models dispatch, worker startup, chunk makespan, and merge overhead in the selection decision.',
    icon: Timer,
  },
  {
    title: 'Resource-budgeted planning',
    detail: 'Searches candidate worker and chunk plans under cloud-style resource limits.',
    icon: Cpu,
  },
  {
    title: 'Reproducible evidence',
    detail: 'Connects live decisions to paper metrics, calibration quality, and budget tradeoff results.',
    icon: BarChart3,
  },
];
