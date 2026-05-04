import { ArrowRight, Brain, Cpu, GraduationCap } from 'lucide-react';
import { contributionCards } from '../../research-demo-data';
import type { ResearchSection } from '../../research-demo-data';

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
          Decision-aware execution selection for media preprocessing
        </h1>

        <p className="mt-5 max-w-3xl text-base leading-7 text-zinc-300">
          This project does not merely parallelize video processing. It measures the cost of deciding, predicts whether
          parallelism is worth it, then chooses serial execution or a worker/chunk plan.
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
