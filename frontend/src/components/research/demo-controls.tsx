import { demoScenarios } from '../../research-demo-data';

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
