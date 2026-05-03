# Research Demo UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional presentation-focused UI that explains the Distributed Video Engine research novelty and demonstrates adaptive execution selection.

**Architecture:** Keep the existing React/Vite frontend and replace the current single operations dashboard entry point with a hybrid research demo shell. Add static presentation data for class-safe fallback, then layer live backend status and jobs on top when available.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS 4, lucide-react, recharts, existing compatibility API endpoints from `server.py`.

---

## File Structure

- Create `frontend/src/data/research-demo.ts`: presentation-safe paper metrics, scenarios, architecture stages, story steps, and strongly typed helper data.
- Create `frontend/src/components/research/research-shell.tsx`: top-level section navigation and layout shell for Story, Live Demo, Evidence, and Architecture.
- Create `frontend/src/components/research/research-hero.tsx`: first-viewport thesis and novelty framing.
- Create `frontend/src/components/research/story-mode.tsx`: presenter-driven walkthrough.
- Create `frontend/src/components/research/demo-controls.tsx`: scenario, workload, and worker-budget controls.
- Create `frontend/src/components/research/selector-decision-panel.tsx`: serial vs parallel decision rationale and scheduler configuration.
- Create `frontend/src/components/research/evidence-dashboard.tsx`: paper-aligned metrics and charts.
- Create `frontend/src/components/research/architecture-flow.tsx`: pipeline diagram and module mapping.
- Modify `frontend/src/App.tsx`: replace the legacy dashboard composition with the research shell and preserve backend polling/job deployment logic where useful.
- Modify `frontend/src/index.css`: add small layout utilities only if needed for scrollbar or projection-safe rendering.

---

### Task 1: Add Presentation Data Model

**Files:**
- Create: `frontend/src/data/research-demo.ts`

- [ ] **Step 1: Create the research demo data module**

Create `frontend/src/data/research-demo.ts` with these exports:

```ts
import {
  Activity,
  BarChart3,
  Brain,
  Cpu,
  Film,
  GitBranch,
  Layers3,
  LineChart,
  LucideIcon,
  Merge,
  ScanSearch,
  ShieldCheck,
  Timer,
  Workflow,
  Zap,
} from 'lucide-react';

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
      'The UI should connect every live demo decision back to reviewer-facing metrics so the project reads as research, not only a dashboard.',
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
  },
  {
    id: 'medium-action',
    name: 'Medium action clip',
    context: 'Vision enhancement before analytics',
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
  },
  {
    id: 'long-heavy',
    name: 'Long noisy clip',
    context: 'Robust preprocessing for noisy media',
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
```

- [ ] **Step 2: Verify the TypeScript module compiles**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript either passes or reports only currently existing unrelated errors. If this new file causes an error, fix the import, type, or object shape before continuing.

- [ ] **Step 3: Commit the data module**

```bash
git add frontend/src/data/research-demo.ts
git commit -m "feat: add research demo presentation data"
```

---

### Task 2: Build The Research Shell And Hero

**Files:**
- Create: `frontend/src/components/research/research-shell.tsx`
- Create: `frontend/src/components/research/research-hero.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the research component directory**

Run:

```bash
mkdir -p frontend/src/components/research
```

- [ ] **Step 2: Create `ResearchHero`**

Create `frontend/src/components/research/research-hero.tsx`:

```tsx
import { ArrowRight, Brain, Cpu, GraduationCap } from 'lucide-react';
import { contributionCards } from '../../data/research-demo';
import type { ResearchSection } from '../../data/research-demo';

interface ResearchHeroProps {
  onNavigate: (section: ResearchSection) => void;
  backendAvailable: boolean;
}

export function ResearchHero({ onNavigate, backendAvailable }: ResearchHeroProps) {
  return (
    <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 p-6 shadow-2xl shadow-black/20">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200">
            <GraduationCap className="h-3.5 w-3.5" />
            Class Research Demo
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs font-semibold text-zinc-300">
            <span className={backendAvailable ? 'h-2 w-2 rounded-full bg-emerald-400' : 'h-2 w-2 rounded-full bg-amber-400'} />
            {backendAvailable ? 'Live backend connected' : 'Presentation dataset mode'}
          </span>
        </div>

        <h1 className="max-w-4xl text-4xl font-semibold tracking-normal text-white md:text-5xl">
          Overhead-aware adaptive execution selection for cloud AI video preprocessing
        </h1>

        <p className="mt-5 max-w-3xl text-base leading-7 text-zinc-300">
          This project does not merely parallelize video processing. It predicts whether parallelism is worth it,
          then chooses serial execution or a worker/chunk plan using video features and an overhead-aware cost model.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => onNavigate('story')}
            className="inline-flex items-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-200"
          >
            Start Story Mode
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onNavigate('demo')}
            className="inline-flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-100 transition hover:border-zinc-500"
          >
            <Cpu className="h-4 w-4" />
            Open Live Demo
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-zinc-200">
          <Brain className="h-4 w-4 text-cyan-300" />
          Research Contributions
        </div>
        <div className="grid gap-3">
          {contributionCards.map((item) => (
            <div key={item.title} className="rounded-md border border-zinc-800 bg-zinc-900/70 p-4">
              <div className="flex items-start gap-3">
                <item.icon className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
                <div>
                  <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                  <p className="mt-1 text-xs leading-5 text-zinc-400">{item.detail}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create `ResearchShell`**

Create `frontend/src/components/research/research-shell.tsx`:

```tsx
import { BarChart3, BookOpen, Cpu, Network } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ResearchSection } from '../../data/research-demo';
import { ResearchHero } from './research-hero';

interface ResearchShellProps {
  activeSection: ResearchSection;
  onSectionChange: (section: ResearchSection) => void;
  backendAvailable: boolean;
  children: ReactNode;
}

const navItems: Array<{ id: ResearchSection; label: string; icon: LucideIcon }> = [
  { id: 'story', label: 'Story', icon: BookOpen },
  { id: 'demo', label: 'Live Demo', icon: Cpu },
  { id: 'evidence', label: 'Evidence', icon: BarChart3 },
  { id: 'architecture', label: 'Architecture', icon: Network },
];

export function ResearchShell({ activeSection, onSectionChange, backendAvailable, children }: ResearchShellProps) {
  return (
    <div className="min-h-screen bg-[#08090b] text-white">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-[#08090b]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <div className="text-sm font-semibold text-white">Distributed Video Engine</div>
            <div className="text-xs text-zinc-500">Research demonstration console</div>
          </div>
          <nav className="flex gap-2 overflow-x-auto">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSectionChange(item.id)}
                className={
                  activeSection === item.id
                    ? 'inline-flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm font-semibold text-zinc-950'
                    : 'inline-flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm font-semibold text-zinc-300 hover:border-zinc-600'
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1500px] flex-col gap-6 px-4 py-6 md:px-8">
        <ResearchHero onNavigate={onSectionChange} backendAvailable={backendAvailable} />
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Wire the shell into `App.tsx` with a temporary section panel**

Modify `frontend/src/App.tsx` so it imports `ResearchShell`, uses `ResearchSection`, and renders the shell with temporary section content while later tasks add the full screens:

```tsx
import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { ResearchShell } from './components/research/research-shell';
import type { ResearchSection } from './data/research-demo';
import { apiUrl } from './lib/api';

function App() {
  const [activeSection, setActiveSection] = useState<ResearchSection>('story');
  const [backendAvailable, setBackendAvailable] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(apiUrl('/health'));
        setBackendAvailable(res.ok);
      } catch {
        setBackendAvailable(false);
      }
    };

    checkHealth();
  }, []);

  return (
    <ResearchShell
      activeSection={activeSection}
      onSectionChange={setActiveSection}
      backendAvailable={backendAvailable}
    >
      <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <h2 className="text-xl font-semibold capitalize text-white">{activeSection}</h2>
        <p className="mt-2 text-sm text-zinc-400">This section will be implemented in the next tasks.</p>
      </section>
      <Toaster position="bottom-right" theme="dark" closeButton />
    </ResearchShell>
  );
}

export default App;
```

- [ ] **Step 5: Build-check the shell**

Run:

```bash
cd frontend
npm run build
```

Expected: the app compiles and Vite emits a `dist` build.

- [ ] **Step 6: Commit the shell**

```bash
git add frontend/src/App.tsx frontend/src/components/research/research-shell.tsx frontend/src/components/research/research-hero.tsx
git commit -m "feat: add research demo shell"
```

---

### Task 3: Implement Story Mode

**Files:**
- Create: `frontend/src/components/research/story-mode.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `StoryMode`**

Create `frontend/src/components/research/story-mode.tsx`:

```tsx
import { storySteps } from '../../data/research-demo';

export function StoryMode() {
  return (
    <section className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Presenter Flow</div>
        <h2 className="mt-2 text-2xl font-semibold text-white">What makes the project novel?</h2>
        <p className="mt-3 text-sm leading-6 text-zinc-400">
          The project moves beyond fixed video parallelism. It predicts whether orchestration overhead will erase
          speedup, then selects the execution regime and resource configuration before the full job runs.
        </p>
        <div className="mt-5 rounded-md border border-cyan-500/30 bg-cyan-500/10 p-4">
          <div className="text-sm font-semibold text-cyan-100">Central contribution</div>
          <p className="mt-2 text-sm leading-6 text-cyan-50/80">
            Overhead-aware serial-versus-parallel selection for cloud AI media preprocessing.
          </p>
        </div>
      </div>

      <div className="grid gap-3">
        {storySteps.map((step, index) => (
          <article key={step.id} className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
            <div className="flex gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-zinc-900 text-cyan-300">
                <step.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  {index + 1}. {step.eyebrow}
                </div>
                <h3 className="mt-1 text-lg font-semibold text-white">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-zinc-400">{step.summary}</p>
                <p className="mt-2 text-sm leading-6 text-zinc-300">{step.detail}</p>
                <div className="mt-3 rounded-md border border-zinc-800 bg-zinc-900 p-3 text-xs leading-5 text-zinc-300">
                  {step.contribution}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Render Story Mode from `App.tsx`**

Import and render the component when `activeSection === 'story'`:

```tsx
import { StoryMode } from './components/research/story-mode';
```

Use this content selection:

```tsx
const sectionContent = activeSection === 'story'
  ? <StoryMode />
  : (
      <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <h2 className="text-xl font-semibold capitalize text-white">{activeSection}</h2>
        <p className="mt-2 text-sm text-zinc-400">This section will be implemented in the next tasks.</p>
      </section>
    );
```

Render `{sectionContent}` inside `ResearchShell`.

- [ ] **Step 3: Build-check Story Mode**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 4: Commit Story Mode**

```bash
git add frontend/src/App.tsx frontend/src/components/research/story-mode.tsx
git commit -m "feat: add research story mode"
```

---

### Task 4: Implement Live Demo Panels

**Files:**
- Create: `frontend/src/components/research/demo-controls.tsx`
- Create: `frontend/src/components/research/selector-decision-panel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `DemoControls`**

Create `frontend/src/components/research/demo-controls.tsx`:

```tsx
import { demoScenarios } from '../../data/research-demo';

interface DemoControlsProps {
  selectedScenarioId: string;
  onScenarioChange: (scenarioId: string) => void;
  workerBudget: number;
  onWorkerBudgetChange: (budget: number) => void;
  liveAvailable: boolean;
}

export function DemoControls({
  selectedScenarioId,
  onScenarioChange,
  workerBudget,
  onWorkerBudgetChange,
  liveAvailable,
}: DemoControlsProps) {
  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Live Demo</div>
          <h2 className="mt-1 text-2xl font-semibold text-white">Run the selector decision</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Use paper-backed scenarios for presentation safety. Live backend mode can be layered in when connected.
          </p>
        </div>
        <span className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs font-semibold text-zinc-300">
          {liveAvailable ? 'Backend connected' : 'Presentation dataset'}
        </span>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_220px]">
        <label className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Scenario</span>
          <select
            value={selectedScenarioId}
            onChange={(event) => onScenarioChange(event.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
          >
            {demoScenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.name} - {scenario.context}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Worker budget</span>
          <select
            value={workerBudget}
            onChange={(event) => onWorkerBudgetChange(Number(event.target.value))}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
          >
            {[2, 4, 8].map((budget) => (
              <option key={budget} value={budget}>
                max {budget} workers
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Create `SelectorDecisionPanel`**

Create `frontend/src/components/research/selector-decision-panel.tsx`:

```tsx
import { Brain, GitBranch } from 'lucide-react';
import type { DemoScenario } from '../../data/research-demo';

interface SelectorDecisionPanelProps {
  scenario: DemoScenario;
  workerBudget: number;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/70 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

export function SelectorDecisionPanel({ scenario, workerBudget }: SelectorDecisionPanelProps) {
  const cappedWorkers = Math.min(scenario.selector.workers, workerBudget);
  const isSerial = scenario.selector.regime === 'serial';

  return (
    <section className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-cyan-300">
          <Brain className="h-4 w-4" />
          Scheduler Decision
        </div>
        <div className="mt-4 rounded-md border border-cyan-500/30 bg-cyan-500/10 p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-200">Selected regime</div>
          <div className="mt-2 text-3xl font-semibold text-white">
            {isSerial ? 'Serial execution' : 'Adaptive parallel execution'}
          </div>
          <p className="mt-3 text-sm leading-6 text-cyan-50/80">
            {isSerial
              ? 'The model predicts orchestration overhead would dominate useful work.'
              : 'The model predicts enough useful work to amortize orchestration overhead.'}
          </p>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <Metric label="Workers" value={`${cappedWorkers}`} />
          <Metric label="Chunks" value={`${scenario.selector.chunks}`} />
          <Metric label="Policy" value={scenario.selector.policy} />
          <Metric label="Speedup" value={`${scenario.selector.predictedSpeedup.toFixed(2)}x`} />
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Duration" value={`${scenario.durationSeconds}s`} />
          <Metric label="Resolution" value={scenario.resolution} />
          <Metric label="Content" value={scenario.contentClass} />
          <Metric label="Workload" value={scenario.workload} />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          <Metric label="Motion" value={`${scenario.featureSummary.motion}%`} />
          <Metric label="Scene cuts" value={`${scenario.featureSummary.sceneCuts}`} />
          <Metric label="Texture" value={`${scenario.featureSummary.texture}%`} />
          <Metric label="Bitrate" value={`${scenario.featureSummary.bitrateMbps} Mbps`} />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="Predicted serial" value={`${scenario.selector.predictedSerialSeconds.toFixed(1)}s`} />
          <Metric label="Predicted parallel" value={`${scenario.selector.predictedParallelSeconds.toFixed(1)}s`} />
          <Metric label="Overhead" value={`${scenario.selector.overheadSeconds.toFixed(1)}s`} />
        </div>

        <div className="mt-5 rounded-md border border-zinc-800 bg-zinc-900/70 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <GitBranch className="h-4 w-4 text-cyan-300" />
            Why this plan?
          </div>
          <ul className="space-y-2 text-sm leading-6 text-zinc-300">
            {scenario.selector.rationale.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Render Live Demo from `App.tsx`**

Add state and content rendering:

```tsx
import { DemoControls } from './components/research/demo-controls';
import { SelectorDecisionPanel } from './components/research/selector-decision-panel';
import { demoScenarios } from './data/research-demo';
```

Inside `App`:

```tsx
const [selectedScenarioId, setSelectedScenarioId] = useState(demoScenarios[0].id);
const [workerBudget, setWorkerBudget] = useState(4);
const selectedScenario = demoScenarios.find((scenario) => scenario.id === selectedScenarioId) ?? demoScenarios[0];
```

Extend `sectionContent`:

```tsx
const sectionContent =
  activeSection === 'story' ? (
    <StoryMode />
  ) : activeSection === 'demo' ? (
    <div className="grid gap-5">
      <DemoControls
        selectedScenarioId={selectedScenarioId}
        onScenarioChange={setSelectedScenarioId}
        workerBudget={workerBudget}
        onWorkerBudgetChange={setWorkerBudget}
        liveAvailable={backendAvailable}
      />
      <SelectorDecisionPanel scenario={selectedScenario} workerBudget={workerBudget} />
    </div>
  ) : (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
      <h2 className="text-xl font-semibold capitalize text-white">{activeSection}</h2>
      <p className="mt-2 text-sm text-zinc-400">This section will be implemented in the next tasks.</p>
    </section>
  );
```

- [ ] **Step 4: Build-check Live Demo**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 5: Commit Live Demo**

```bash
git add frontend/src/App.tsx frontend/src/components/research/demo-controls.tsx frontend/src/components/research/selector-decision-panel.tsx
git commit -m "feat: add selector live demo panels"
```

---

### Task 5: Implement Evidence Dashboard

**Files:**
- Create: `frontend/src/components/research/evidence-dashboard.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `EvidenceDashboard`**

Create `frontend/src/components/research/evidence-dashboard.tsx`:

```tsx
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { budgetTradeoffs, keyResults, runtimeComparison } from '../../data/research-demo';

export function EvidenceDashboard() {
  return (
    <section className="grid gap-5">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Reviewer Evidence</div>
        <h2 className="mt-1 text-2xl font-semibold text-white">Paper-aligned results</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">
          These metrics connect the classroom demo to the project evaluation: runtime wins, selector quality,
          prediction calibration, and resource-budget behavior.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {keyResults.map((result) => (
          <article key={result.label} className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
            <result.icon className="h-5 w-5 text-cyan-300" />
            <div className="mt-4 text-3xl font-semibold text-white">{result.value}</div>
            <div className="mt-1 text-sm font-semibold text-zinc-200">{result.label}</div>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{result.detail}</p>
          </article>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
          <h3 className="text-sm font-semibold text-white">Runtime comparison</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={runtimeComparison}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="case" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }} />
                <Bar dataKey="serial" fill="#71717a" radius={[4, 4, 0, 0]} />
                <Bar dataKey="static" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="adaptive" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
          <h3 className="text-sm font-semibold text-white">Worker budget tradeoffs</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={budgetTradeoffs}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="budget" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }} />
                <Line type="monotone" dataKey="speedup" stroke="#22c55e" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="efficiency" stroke="#38bdf8" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Render Evidence from `App.tsx`**

Import:

```tsx
import { EvidenceDashboard } from './components/research/evidence-dashboard';
```

Add this branch to `sectionContent` before the final fallback:

```tsx
  ) : activeSection === 'evidence' ? (
    <EvidenceDashboard />
```

- [ ] **Step 3: Build-check Evidence**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 4: Commit Evidence**

```bash
git add frontend/src/App.tsx frontend/src/components/research/evidence-dashboard.tsx
git commit -m "feat: add research evidence dashboard"
```

---

### Task 6: Implement Architecture Flow

**Files:**
- Create: `frontend/src/components/research/architecture-flow.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `ArchitectureFlow`**

Create `frontend/src/components/research/architecture-flow.tsx`:

```tsx
import { ArrowRight } from 'lucide-react';
import { architectureStages } from '../../data/research-demo';

export function ArchitectureFlow() {
  return (
    <section className="grid gap-5">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">System Architecture</div>
        <h2 className="mt-1 text-2xl font-semibold text-white">From video input to research evidence</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">
          The scheduler is the central research block: it receives content features and predicts whether serial or
          parallel execution is the better plan before the full preprocessing job runs.
        </p>
      </div>

      <div className="grid gap-3">
        {architectureStages.map((stage, index) => (
          <article key={stage.title} className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
            <div className="grid gap-4 lg:grid-cols-[220px_1fr_220px] lg:items-center">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-900 text-cyan-300">
                  <stage.icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Stage {index + 1}</div>
                  <h3 className="text-lg font-semibold text-white">{stage.title}</h3>
                </div>
              </div>

              <div>
                <p className="text-sm leading-6 text-zinc-300">{stage.description}</p>
                <div className="mt-2 font-mono text-xs text-cyan-300">{stage.module}</div>
              </div>

              <div className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-900 p-3 text-sm text-zinc-300">
                <ArrowRight className="h-4 w-4 shrink-0 text-zinc-500" />
                {stage.output}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Render Architecture from `App.tsx`**

Import:

```tsx
import { ArchitectureFlow } from './components/research/architecture-flow';
```

Add this branch to `sectionContent` before the final fallback:

```tsx
  ) : activeSection === 'architecture' ? (
    <ArchitectureFlow />
```

- [ ] **Step 3: Build-check Architecture**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 4: Commit Architecture**

```bash
git add frontend/src/App.tsx frontend/src/components/research/architecture-flow.tsx
git commit -m "feat: add architecture flow view"
```

---

### Task 7: Polish Integration And Presentation Safety

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css` if needed

- [ ] **Step 1: Confirm `App.tsx` has complete section routing**

The final section routing should have all four concrete branches:

```tsx
const sectionContent =
  activeSection === 'story' ? (
    <StoryMode />
  ) : activeSection === 'demo' ? (
    <div className="grid gap-5">
      <DemoControls
        selectedScenarioId={selectedScenarioId}
        onScenarioChange={setSelectedScenarioId}
        workerBudget={workerBudget}
        onWorkerBudgetChange={setWorkerBudget}
        liveAvailable={backendAvailable}
      />
      <SelectorDecisionPanel scenario={selectedScenario} workerBudget={workerBudget} />
    </div>
  ) : activeSection === 'evidence' ? (
    <EvidenceDashboard />
  ) : (
    <ArchitectureFlow />
  );
```

- [ ] **Step 2: Confirm backend fallback behavior**

Ensure the `/health` check is defensive:

```tsx
useEffect(() => {
  const checkHealth = async () => {
    try {
      const res = await fetch(apiUrl('/health'));
      setBackendAvailable(res.ok);
    } catch {
      setBackendAvailable(false);
    }
  };

  checkHealth();
}, []);
```

Expected behavior: when the backend is unavailable, the UI still renders Story, Live Demo, Evidence, and Architecture with presentation data.

- [ ] **Step 3: Add projection-safe body sizing only if visual inspection needs it**

If the page shows unwanted horizontal scrolling, add this to `frontend/src/index.css`:

```css
html {
  background: #08090b;
}

body {
  min-width: 320px;
}
```

- [ ] **Step 4: Run production build**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 5: Start the local Vite server**

Run:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL, usually `http://127.0.0.1:5173/`.

- [ ] **Step 6: Browser verify the four sections**

Open the Vite URL and verify:

- First viewport shows project name and research thesis.
- Story section explains problem, novelty, method, evidence, and contributions.
- Live Demo works without backend by switching scenarios and worker budgets.
- Evidence charts render.
- Architecture section shows the pipeline and module mapping.
- No text overlaps at desktop width.
- At narrow width, navigation scrolls horizontally and cards stack cleanly.

- [ ] **Step 7: Commit polish**

```bash
git add frontend/src/App.tsx frontend/src/index.css
git commit -m "feat: finalize presentation-safe research UI"
```

---

## Self-Review

Spec coverage:

- Audience and novelty framing are covered by `ResearchHero` and `StoryMode`.
- Hybrid section structure is covered by `ResearchShell`.
- Live demo and presentation fallback are covered by `DemoControls`, `SelectorDecisionPanel`, and static scenario data.
- Evidence metrics are covered by `EvidenceDashboard`.
- Architecture mapping is covered by `ArchitectureFlow`.
- Verification requirements are covered by Task 7.

Scope check:

- This plan touches only the frontend and static presentation data.
- It does not rewrite the backend, alter the research pipeline, create a slide deck, or upload to GitHub.

Type consistency:

- `ResearchSection`, `DemoScenario`, and component props are defined in Task 1 and reused consistently in later tasks.
- `activeSection` values match the four top-level UI sections: `story`, `demo`, `evidence`, and `architecture`.
