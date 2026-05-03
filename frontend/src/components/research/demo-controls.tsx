import { demoScenarios } from '../../research-demo-data';

interface DemoControlsProps {
  selectedScenarioId: string;
  onScenarioChange: (scenarioId: string) => void;
  workerBudget: number;
  onWorkerBudgetChange: (budget: number) => void;
  liveAvailable: boolean;
  liveInputPath: string;
  uploadedFileName: string | null;
  uploadStatus: string | null;
  liveStatus: string | null;
  isUploading: boolean;
  isRunningLive: boolean;
  onUpload: (file: File) => void;
  onRunLive: () => void;
}

export function DemoControls({
  selectedScenarioId,
  onScenarioChange,
  workerBudget,
  onWorkerBudgetChange,
  liveAvailable,
  liveInputPath,
  uploadedFileName,
  uploadStatus,
  liveStatus,
  isUploading,
  isRunningLive,
  onUpload,
  onRunLive,
}: DemoControlsProps) {
  const selectedScenario = demoScenarios.find((scenario) => scenario.id === selectedScenarioId) ?? demoScenarios[0];

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Live Demo</div>
          <h2 className="mt-1 text-2xl font-semibold text-white">Choose a sample or run live</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Use replay scenarios for presentation safety. On the GPU laptop, upload a video or run the selected sample
            path through the backend for an authentic live pass.
          </p>
        </div>
        <span className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs font-semibold text-zinc-300">
          {liveAvailable ? 'Backend connected' : 'Presentation dataset'}
        </span>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {demoScenarios.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            onClick={() => onScenarioChange(scenario.id)}
            className={
              selectedScenarioId === scenario.id
                ? 'rounded-lg border border-cyan-500/50 bg-cyan-500/10 p-4 text-left'
                : 'rounded-lg border border-zinc-800 bg-zinc-900/70 p-4 text-left transition hover:border-zinc-600'
            }
          >
            <div className="text-sm font-semibold text-white">{scenario.name}</div>
            <div className="mt-1 text-xs leading-5 text-zinc-400">{scenario.context}</div>
            <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
              <span className="rounded-full border border-zinc-700 px-2 py-0.5">{scenario.durationSeconds}s</span>
              <span className="rounded-full border border-zinc-700 px-2 py-0.5">{scenario.workload}</span>
              <span className="rounded-full border border-zinc-700 px-2 py-0.5">{scenario.contentClass}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_220px]">
        <label className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Selected sample path</span>
          <div className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 font-mono text-sm text-zinc-200">
            {selectedScenario.samplePath}
          </div>
          <span className="text-xs leading-5 text-zinc-500">{selectedScenario.sampleNote}</span>
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

      <div className="mt-5 grid gap-4 rounded-lg border border-zinc-800 bg-zinc-900/70 p-4 lg:grid-cols-[1fr_auto] lg:items-end">
        <label className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Upload live demo video</span>
          <input
            type="file"
            accept="video/mp4,video/webm,video/quicktime,video/x-matroska,video/x-msvideo"
            disabled={!liveAvailable || isUploading || isRunningLive}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.target.value = '';
            }}
            className="block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 file:mr-3 file:rounded-md file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <span className="text-xs leading-5 text-zinc-500">
            {uploadedFileName
              ? `Live input: ${uploadedFileName} (${liveInputPath})`
              : `Live input defaults to selected sample path: ${liveInputPath}`}
          </span>
        </label>

        <button
          type="button"
          onClick={onRunLive}
          disabled={!liveAvailable || isUploading || isRunningLive}
          className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
        >
          {isRunningLive ? 'Starting live run...' : liveAvailable ? 'Run Live on This Machine' : 'Backend unavailable'}
        </button>
      </div>

      {(uploadStatus || liveStatus) && (
        <div className="mt-4 rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm leading-6 text-zinc-300">
          {uploadStatus && <div>{uploadStatus}</div>}
          {liveStatus && <div>{liveStatus}</div>}
        </div>
      )}
    </section>
  );
}
