import { cn } from '../../lib/utils';
import type { RenderingJob } from '../../types';

interface ChunkVisualizerProps {
  activeJob: RenderingJob | null;
}

export function ChunkVisualizer({ activeJob }: ChunkVisualizerProps) {
  // Mock chunks based on progress if real chunk data isn't available
  const getChunks = () => {
    if (!activeJob) return Array(16).fill('idle');
    
    // If job is done, everything is green
    const totalChunks = activeJob.workers * 2 || 16;
    if (activeJob.status === 'completed') return Array(totalChunks).fill('completed');

    const completed = Math.floor((activeJob.progress / 100) * totalChunks);
    
    return Array(totalChunks).fill(0).map((_, i) => {
      if (i < completed) return 'completed';
      if (i === completed && activeJob.status === 'processing') return 'processing';
      return 'queued';
    });
  };

  const chunks = getChunks();

  return (
    <div className="bg-[#111111] border border-[#222222] rounded-2xl p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-wider">Parallel Chunk Map</h3>
        <div className="flex gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-sm bg-emerald-500" />
            <span className="text-[10px] font-medium text-zinc-400">Done</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-sm bg-indigo-500 animate-pulse" />
            <span className="text-[10px] font-medium text-zinc-400">Active</span>
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-4 sm:grid-cols-8 gap-2 content-start overflow-y-auto pr-1 custom-scrollbar">
        {chunks.map((status, i) => (
          <div 
            key={i}
            className={cn(
              "aspect-square rounded-md border transition-all duration-300 flex items-center justify-center text-[10px] font-bold",
              status === 'completed' 
                ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-500" 
                : status === 'processing'
                  ? "bg-indigo-500/20 border-indigo-500/50 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.3)] scale-105 z-10"
                  : "bg-[#1a1a1a] border-[#222] text-zinc-700"
            )}
          >
            {i + 1}
          </div>
        ))}
      </div>
      
      {activeJob && (
        <div className="mt-4 pt-4 border-t border-[#222] flex justify-between items-center">
            <span className="text-xs font-medium text-zinc-400">
                Strategy: <span className="text-white">{activeJob.smart_config ? 'Adaptive Split' : 'Uniform Split'}</span>
            </span>
            <span className="text-xs font-mono text-zinc-500">
                {activeJob.workers} Workers
            </span>
        </div>
      )}
    </div>
  );
}