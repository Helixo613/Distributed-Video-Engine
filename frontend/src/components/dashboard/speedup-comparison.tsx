import { Zap, ArrowRight, Timer } from 'lucide-react';
import type { RenderingJob } from '../../types';

interface SpeedupComparisonProps {
  job: RenderingJob;
}

export function SpeedupComparison({ job }: SpeedupComparisonProps) {
  if (!job.duration || !job.projected_serial_time) return null;

  const parallelTime = parseFloat(job.duration.replace('s', ''));
  const serialTime = parseFloat(job.projected_serial_time.replace('s', ''));
  const speedup = (serialTime / parallelTime).toFixed(1);
  const savedTime = (serialTime - parallelTime).toFixed(1);

  // Determine bar widths (max 100%)
  const maxTime = Math.max(parallelTime, serialTime);
  const parallelWidth = (parallelTime / maxTime) * 100;
  const serialWidth = (serialTime / maxTime) * 100;

  return (
    <div className="bg-[#111111] border border-[#222] rounded-2xl p-6 relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        <Zap className="w-24 h-24 text-indigo-500" />
      </div>

      <div className="relative z-10">
        <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-wider mb-6 flex items-center gap-2">
          <Timer className="w-4 h-4" />
          Parallel Speedup Analysis
        </h3>

        <div className="space-y-6">
          {/* Serial Bar */}
          <div>
            <div className="flex justify-between text-xs font-medium mb-2">
              <span className="text-zinc-400">Estimated Serial (1 Worker)</span>
              <span className="text-zinc-300 font-mono">{serialTime}s</span>
            </div>
            <div className="h-2 w-full bg-[#1a1a1a] rounded-full overflow-hidden">
              <div 
                className="h-full bg-zinc-600 rounded-full" 
                style={{ width: `${serialWidth}%` }} 
              />
            </div>
          </div>

          {/* Parallel Bar */}
          <div>
            <div className="flex justify-between text-xs font-bold mb-2">
              <span className="text-indigo-400">Actual Distributed ({job.workers} Workers)</span>
              <span className="text-white font-mono">{parallelTime}s</span>
            </div>
            <div className="h-2 w-full bg-[#1a1a1a] rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full shadow-[0_0_15px_rgba(99,102,241,0.5)]" 
                style={{ width: `${parallelWidth}%` }} 
              />
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="mt-8 pt-6 border-t border-[#222] flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-zinc-500 uppercase">Time Saved</span>
            <span className="text-xl font-bold text-white tracking-tight">{savedTime}s</span>
          </div>

          <div className="flex items-center gap-4">
             <ArrowRight className="w-5 h-5 text-zinc-600" />
             <div className="flex flex-col items-end">
                <span className="text-[10px] font-bold text-indigo-400 uppercase">Speedup Factor</span>
                <span className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">
                  {speedup}x
                </span>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
