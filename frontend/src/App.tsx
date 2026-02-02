import { Sidebar } from './components/dashboard/sidebar';
import { JobList } from './components/dashboard/job-list';
import { VideoUpload } from './components/dashboard/video-upload';
import { RealtimeMonitor } from './components/dashboard/realtime-monitor';
import { ChunkVisualizer } from './components/dashboard/chunk-visualizer';
import { SpeedupComparison } from './components/dashboard/speedup-comparison';
import { VideoComparison } from './components/dashboard/video-comparison';
import { PhaseIndicator } from './components/dashboard/phase-indicator';
import { Button } from './components/ui/button';
import { Switch } from './components/ui/switch';
import { Plus, Sparkles, Cpu, Brain, FileJson } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { useState, useEffect } from 'react';
import type { EngineVersion, RenderingJob } from './types';
import { apiUrl } from './lib/api';

function App() {
  const [smartMode, setSmartMode] = useState(true);
  const [engineVersion, setEngineVersion] = useState<EngineVersion>('v1');
  const [v2Available, setV2Available] = useState(false);
  const [selectedVideoPath, setSelectedVideoPath] = useState<string | null>('test_input.mp4');
  const [thumbnailPreview, setThumbnailPreview] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<RenderingJob | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Check if V2 is available and poll active job status
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(apiUrl('/health'));
        if (res.ok) {
          const data = await res.json();
          setV2Available(data.v2_available);
        }
      } catch (e) {
        console.error("Backend not connected", e);
      }
    };

    const fetchJobs = async () => {
      try {
        const res = await fetch(apiUrl('/jobs'));
        if (res.ok) {
          const data: RenderingJob[] = await res.json();
          
          // 1. Check for active processing jobs
          const processing = data.find(j => j.status === 'processing');
          
          if (processing) {
            setActiveJob(processing);
            setIsProcessing(true);
          } else {
            setIsProcessing(false);
            // 2. If nothing is running, show the most recent completed job (for results)
            if (data.length > 0) {
                 // data is already sorted by created_at desc from backend
                 setActiveJob(data[0]);
            }
          }
        }
      } catch {
        // Silently fail
      }
    };

    checkHealth();
    fetchJobs();
    const interval = setInterval(fetchJobs, 1000);
    return () => clearInterval(interval);
  }, []); // Intentionally minimal deps

  const deployJob = async () => {
    if (!selectedVideoPath) {
      toast.error("Please select or upload a video file first");
      return;
    }

    try {
      const engineLabel = engineVersion === 'v2' ? 'V2 Smart AI' : 'V1 CPU Burn';
      const fileName = selectedVideoPath.split('/').pop() || selectedVideoPath;
      const modeText = smartMode ? "Auto-Tune" : "Manual";
      toast.info(`Deploying ${engineLabel} (${modeText}) for ${fileName}...`);

      const res = await fetch(apiUrl('/jobs'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_path: selectedVideoPath,
          workers: 4,
          filter_chain: 'unsharp=5:5:1.5:5:5:0.5',
          smart: smartMode,
          engine_version: engineVersion
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start job");
      }

      const data = await res.json();
      toast.success(`Job ${data.id} started!`);
      setActiveJob(data);
      setIsProcessing(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to deploy job");
      console.error(e);
    }
  };

  const exportResults = async () => {
    try {
      const res = await fetch(apiUrl('/jobs'));
      if (!res.ok) throw new Error("Failed to fetch jobs");

      const data = await res.json();
      const exportData = {
        exported_at: new Date().toISOString(),
        total_jobs: data.length,
        jobs: data
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hpc-benchmark-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);

      toast.success("Results exported!");
    } catch {
      toast.error("Failed to export results");
    }
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white font-sans selection:bg-indigo-500/30">
      <Sidebar />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Background Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />

        {/* Top Bar */}
        <header className="border-b border-[#222] bg-[#0a0a0a]/80 backdrop-blur-md px-8 py-5 flex items-center justify-between sticky top-0 z-20">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Control Plane</h1>
              <div className="flex items-center gap-2 mt-1">
                <div className={`w-1.5 h-1.5 rounded-full ${isProcessing ? 'bg-orange-500 animate-pulse' : 'bg-emerald-500'}`} />
                <p className="text-xs font-medium text-zinc-500">
                    {isProcessing ? 'Cluster Busy' : 'System Operational'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Engine Toggle */}
              <div className="flex items-center gap-1 bg-[#111111] border border-[#222] p-1 rounded-xl">
                <button
                  onClick={() => setEngineVersion('v1')}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all text-xs font-bold ${
                    engineVersion === 'v1'
                      ? 'bg-zinc-800 text-white shadow-sm'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Cpu className="w-3.5 h-3.5" />
                  V1 Core
                </button>
                <button
                  onClick={() => v2Available && setEngineVersion('v2')}
                  disabled={!v2Available}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all text-xs font-bold ${
                    engineVersion === 'v2'
                      ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'
                      : v2Available
                        ? 'text-zinc-500 hover:text-zinc-300'
                        : 'text-zinc-700 cursor-not-allowed opacity-50'
                  }`}
                >
                  <Brain className="w-3.5 h-3.5" />
                  V2 Neural
                </button>
              </div>

              <div className="h-8 w-px bg-[#222]" />

              {/* Auto-Tune Toggle */}
              <div className="flex items-center gap-3 bg-[#111111] border border-[#222] px-3 py-1.5 rounded-xl">
                <div className={`p-1 rounded-md ${smartMode ? 'bg-indigo-500/20' : 'bg-zinc-800'}`}>
                    <Sparkles className={`w-3.5 h-3.5 ${smartMode ? 'text-indigo-400' : 'text-zinc-500'}`} />
                </div>
                <div className="flex flex-col">
                    <span className={`text-[10px] font-bold uppercase leading-none ${smartMode ? 'text-indigo-400' : 'text-zinc-500'}`}>
                    Smart Scaling
                    </span>
                    <span className="text-[9px] text-zinc-600 font-medium">Heuristic Opt.</span>
                </div>
                <Switch
                  checked={smartMode}
                  onCheckedChange={setSmartMode}
                  className="ml-1 scale-75 data-[state=checked]:bg-indigo-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={exportResults}
                    className="gap-2 border-[#222] bg-[#111111] hover:bg-[#1a1a1a] h-9 text-xs"
                >
                    <FileJson className="w-3.5 h-3.5 text-zinc-400" />
                    Export
                </Button>

                <Button
                    size="sm"
                    onClick={deployJob}
                    disabled={isProcessing}
                    className={`gap-2 h-9 shadow-lg cursor-pointer min-w-[120px] transition-all duration-500 ${
                    isProcessing
                        ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed border border-zinc-700'
                        : 'bg-white text-black hover:bg-zinc-200 border border-transparent'
                    }`}
                >
                    {isProcessing ? (
                        <>
                            <div className="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin" />
                            <span>Processing...</span>
                        </>
                    ) : (
                        <>
                            <Plus className="w-4 h-4" />
                            <span>Deploy Job</span>
                        </>
                    )}
                </Button>
              </div>
            </div>
        </header>

        {/* Dashboard Content */}
        <div className="flex-1 overflow-y-auto p-8 scrollbar-hide z-10">
          <div className="max-w-[1600px] mx-auto flex flex-col gap-6">
            
            {/* Row 1: Real-time Telemetry (hidden once thumbnail is available) */}
            {!thumbnailPreview && <RealtimeMonitor />}
            
            {/* Phase Indicator (Only when job is active/recent) */}
            {activeJob && activeJob.status !== 'queued' && (
                <PhaseIndicator phase={activeJob.phase} />
            )}

            {/* Row 2: Interaction Zone */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[380px]">
                {/* Upload Zone */}
                <VideoUpload
                  onSelect={setSelectedVideoPath}
                  onPreviewChange={setThumbnailPreview}
                  isProcessing={isProcessing}
                  progress={activeJob?.progress ?? 0}
                  phase={activeJob?.phase}
                  className="lg:col-span-2"
                />
                
                {/* Middle: Chunk Map */}
                <div className="lg:col-span-1">
                    <ChunkVisualizer activeJob={activeJob} />
                </div>

                {/* Right: Results or Placeholder */}
                <div className="lg:col-span-1 h-full">
                    {activeJob && activeJob.status === 'completed' ? (
                        <SpeedupComparison job={activeJob} />
                    ) : (
                        <div className="h-full bg-[#111111] border border-[#222] rounded-2xl p-6 flex flex-col items-center justify-center text-zinc-600">
                             <Sparkles className="w-12 h-12 mb-4 opacity-20" />
                             <p className="text-sm font-bold uppercase tracking-wider">Awaiting Results</p>
                             <p className="text-xs text-zinc-500 mt-2 text-center">Deploy a job to see parallel speedup analysis</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Row 3: Job History */}
            {activeJob && activeJob.status === 'completed' && activeJob.comparison_report && (
              <VideoComparison job={activeJob} />
            )}

            <div className="flex flex-col gap-4">
                <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-wider">Operation History</h3>
                <JobList />
            </div>

          </div>
        </div>
      </main>
      <Toaster position="bottom-right" theme="dark" closeButton />
    </div>
  );
}

export default App;
