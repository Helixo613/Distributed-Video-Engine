import { Gauge, Zap } from 'lucide-react';
import type { ReactElement } from 'react';

interface LiveBenchmarkComparisonProps {
  thumbnail: string | null;
  serialProgress: number;
  parallelProgress: number;
  phase?: string;
}

export function LiveBenchmarkComparison({
  thumbnail,
  serialProgress,
  parallelProgress,
  phase,
}: LiveBenchmarkComparisonProps) {
  const safeSerial = Math.max(0, Math.min(100, serialProgress));
  const safeParallel = Math.max(0, Math.min(100, parallelProgress));
  const lead = safeParallel - safeSerial;

  return (
    <div className="bg-[#111111] border border-[#222] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Live Serial vs Parallel</h3>
        <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">{phase || 'processing'}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <LaneCard title="Serial Lane" icon={<Gauge className="w-4 h-4 text-orange-300" />} progress={safeSerial} tone="from-orange-500 to-amber-400" thumbnail={thumbnail} />
        <LaneCard title="Parallel Lane" icon={<Zap className="w-4 h-4 text-cyan-300" />} progress={safeParallel} tone="from-cyan-500 to-indigo-500" thumbnail={thumbnail} />
      </div>

      <div className="mt-3 p-2 rounded-lg bg-[#0b0b0b] border border-[#222] text-xs text-zinc-300 flex items-center justify-between">
        <span>Live Lead</span>
        <span className={lead >= 0 ? 'text-cyan-300 font-bold' : 'text-orange-300 font-bold'}>
          {lead >= 0 ? 'Parallel +' : 'Serial +'}
          {Math.abs(lead).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

function LaneCard({
  title,
  icon,
  progress,
  tone,
  thumbnail,
}: {
  title: string;
  icon: ReactElement;
  progress: number;
  tone: string;
  thumbnail: string | null;
}) {
  return (
    <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">{title}</p>
        </div>
        <span className="text-xs text-white font-bold">{progress}%</span>
      </div>

      <div className="relative h-24 rounded-lg overflow-hidden border border-[#2a2a2a] mb-2 bg-[#111]">
        {thumbnail ? (
          <>
            <img src={thumbnail} alt={`${title} preview`} className="w-full h-full object-cover opacity-45 grayscale" />
            <div className="absolute inset-y-0 left-0 overflow-hidden" style={{ width: `${progress}%` }}>
              <img src={thumbnail} alt={`${title} progress`} className="w-full h-full object-cover opacity-95" />
            </div>
          </>
        ) : (
          <div className="w-full h-full bg-[radial-gradient(circle_at_top,#1f2937,transparent_70%)]" />
        )}
      </div>

      <div className="h-2 w-full bg-black/45 rounded-full overflow-hidden border border-white/10">
        <div className={`h-full bg-gradient-to-r ${tone} transition-all duration-300`} style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
