import { ArrowRight } from 'lucide-react';
import { architectureStages } from '../../research-demo-data';

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
