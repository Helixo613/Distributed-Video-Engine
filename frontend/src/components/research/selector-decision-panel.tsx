import { Brain, GitBranch } from 'lucide-react';
import type { DemoScenario } from '../../research-demo-data';

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
