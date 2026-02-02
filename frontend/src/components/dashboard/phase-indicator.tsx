import { Activity, Gauge, Cpu, CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { JobPhase } from '../../types';

interface PhaseIndicatorProps {
  phase?: JobPhase;
}

export function PhaseIndicator({ phase = 'queued' }: PhaseIndicatorProps) {
  const steps = [
    { id: 'analyzing', label: 'Analysis', icon: Activity },
    { id: 'benchmarking', label: 'Serial Benchmark', icon: Gauge },
    { id: 'parallel', label: 'Parallel Render', icon: Cpu },
    { id: 'completed', label: 'Finalize', icon: CheckCircle2 },
  ];

  // Map phase to index
  const phaseMap: Record<string, number> = {
    'queued': -1,
    'analyzing': 0,
    'benchmarking': 1,
    'parallel': 2,
    'merging': 2, // Merging is part of parallel/finalize transition
    'completed': 3
  };

  const currentStepIndex = phaseMap[phase] ?? -1;

  return (
    <div className="flex items-center justify-between w-full bg-[#111111] border border-[#222] rounded-xl p-4 mb-4">
      {steps.map((step, i) => {
        const isActive = i === currentStepIndex;
        const isCompleted = i < currentStepIndex;

        return (
          <div key={step.id} className="flex flex-col items-center gap-2 relative z-10 w-full">
            {/* Connector Line */}
            {i < steps.length - 1 && (
              <div className="absolute top-3 left-1/2 w-full h-[2px] -z-10 bg-[#222]">
                <div 
                  className="h-full bg-emerald-500 transition-all duration-500" 
                  style={{ width: isCompleted ? '100%' : '0%' }} 
                />
              </div>
            )}

            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all duration-300 bg-[#0a0a0a]",
              isActive ? "border-indigo-500 text-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.5)]" :
              isCompleted ? "border-emerald-500 text-emerald-500 bg-emerald-500/10" :
              "border-[#333] text-zinc-600"
            )}>
              {isActive ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <step.icon className="w-4 h-4" />
              )}
            </div>
            
            <span className={cn(
              "text-[10px] font-bold uppercase tracking-wider transition-colors",
              isActive ? "text-indigo-400" :
              isCompleted ? "text-emerald-500" :
              "text-zinc-600"
            )}>
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
