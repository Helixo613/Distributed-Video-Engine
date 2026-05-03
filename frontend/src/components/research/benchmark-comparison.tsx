import { PlayCircle } from 'lucide-react';
import type { DemoScenario } from '../../research-demo-data';

interface BenchmarkComparisonProps {
  scenario: DemoScenario;
}

export function BenchmarkComparison({ scenario }: BenchmarkComparisonProps) {
  const bestRuntime = Math.min(...scenario.replayComparison.map((item) => item.runtimeSeconds));

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Benchmark Replay</div>
          <h2 className="mt-1 text-2xl font-semibold text-white">Serial vs fixed parallel vs adaptive selector</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            Recorded presentation data keeps the classroom demo reliable. Live mode can run the same selected input
            when the backend is available on the GPU laptop.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-100">
          <PlayCircle className="h-3.5 w-3.5" />
          Replay ready
        </span>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {scenario.replayComparison.map((item) => {
          const isFastest = item.runtimeSeconds === bestRuntime;
          const isSelectorChoice = Boolean(item.highlight);
          const isEmphasized = isSelectorChoice || isFastest;
          return (
            <article
              key={item.id}
              className={
                isEmphasized
                  ? 'rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4'
                  : 'rounded-lg border border-zinc-800 bg-zinc-900/70 p-4'
              }
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-white">{item.label}</h3>
                {isSelectorChoice && (
                  <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                    Selector choice
                  </span>
                )}
                {!isSelectorChoice && isFastest && (
                  <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-200">
                    Fastest replay
                  </span>
                )}
              </div>
              <div className="mt-4 text-3xl font-semibold text-white">{item.runtimeSeconds.toFixed(1)}s</div>
              <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                {item.speedup.toFixed(2)}x vs serial
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-md border border-zinc-800 bg-zinc-950/70 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Workers</div>
                  <div className="mt-1 text-lg font-semibold text-white">{item.workers}</div>
                </div>
                <div className="rounded-md border border-zinc-800 bg-zinc-950/70 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Chunks</div>
                  <div className="mt-1 text-lg font-semibold text-white">{item.chunks}</div>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-zinc-300">{item.summary}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
