import { storySteps } from '../../research-demo-data';

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
