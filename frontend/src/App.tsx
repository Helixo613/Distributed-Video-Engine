import { useEffect, useState } from 'react';
import { Toaster, toast } from 'sonner';
import { ArchitectureFlow } from './components/research/architecture-flow';
import { BenchmarkComparison } from './components/research/benchmark-comparison';
import { DemoControls } from './components/research/demo-controls';
import { EvidenceDashboard } from './components/research/evidence-dashboard';
import { ResearchShell } from './components/research/research-shell';
import { SelectorDecisionPanel } from './components/research/selector-decision-panel';
import { StoryMode } from './components/research/story-mode';
import { demoScenarios } from './research-demo-data';
import type { ResearchSection } from './research-demo-data';
import { apiUrl } from './lib/api';

interface LiveJob {
  id: string;
  status: string;
  phase?: string;
  progress: number;
  duration?: string | null;
  serial_actual_time?: string | null;
  comparison_report?: {
    actual_speedup?: number;
    psnr_avg?: number | null;
    ssim_all?: number | null;
    summary?: string;
  } | null;
  performance?: {
    throughput?: number | null;
    efficiency?: number | null;
  } | null;
  error?: string | null;
}

function App() {
  const [activeSection, setActiveSection] = useState<ResearchSection>('story');
  const [backendAvailable, setBackendAvailable] = useState(false);
  const [selectedScenarioId, setSelectedScenarioId] = useState(demoScenarios[0].id);
  const [workerBudget, setWorkerBudget] = useState(4);
  const [uploadedInputPath, setUploadedInputPath] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [liveJob, setLiveJob] = useState<LiveJob | null>(null);
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRunningLive, setIsRunningLive] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(apiUrl('/health'));
        setBackendAvailable(res.ok);
      } catch {
        setBackendAvailable(false);
      }
    };

    checkHealth();
  }, []);

  useEffect(() => {
    if (!liveJobId) return;

    let cancelled = false;
    const pollJob = async () => {
      try {
        const res = await fetch(apiUrl(`/jobs/${liveJobId}`));
        if (!res.ok) throw new Error('Failed to read live job status');
        const data = (await res.json()) as LiveJob;
        if (cancelled) return;

        setLiveJob(data);
        setLiveStatus(`Live job ${data.id}: ${data.status}${data.phase ? ` (${data.phase})` : ''} - ${data.progress}%`);

        if (data.status === 'completed') {
          setLiveStatus(`Live job ${data.id} completed. Speedup: ${data.comparison_report?.actual_speedup?.toFixed(2) ?? 'n/a'}x.`);
          setLiveJobId(null);
        } else if (data.status === 'failed') {
          setLiveStatus(`Live job ${data.id} failed: ${data.error ?? 'unknown error'}`);
          setLiveJobId(null);
        }
      } catch (error) {
        if (!cancelled) {
          setLiveStatus(error instanceof Error ? error.message : 'Failed to poll live job');
        }
      }
    };

    pollJob();
    const interval = window.setInterval(pollJob, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [liveJobId]);

  const selectedScenario = demoScenarios.find((scenario) => scenario.id === selectedScenarioId) ?? demoScenarios[0];
  const liveInputPath = uploadedInputPath ?? selectedScenario.samplePath;

  const handleScenarioChange = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setUploadedInputPath(null);
    setUploadedFileName(null);
    setUploadStatus(null);
    setLiveStatus(null);
    setLiveJob(null);
    setLiveJobId(null);
  };

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setUploadStatus(`Uploading ${file.name}...`);
    setLiveStatus(null);

    try {
      const form = new FormData();
      form.append('file', file);

      const res = await fetch(apiUrl('/upload'), {
        method: 'POST',
        body: form,
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Upload failed');
      }

      const data = (await res.json()) as { filename: string; path: string; size_mb: number };
      setUploadedInputPath(data.path);
      setUploadedFileName(data.filename);
      setUploadStatus(`Uploaded ${data.filename} (${data.size_mb} MB). Ready for live run.`);
      toast.success('Video uploaded for live demo');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed';
      setUploadStatus(message);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunLive = async () => {
    setIsRunningLive(true);
    setLiveStatus(`Starting live run for ${liveInputPath}...`);

    try {
      const res = await fetch(apiUrl('/jobs'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_path: liveInputPath,
          workers: Math.min(selectedScenario.selector.workers, workerBudget),
          filter_chain: 'unsharp=5:5:1.5:5:5:0.5',
          smart: true,
          strict_benchmark: true,
          engine_version: 'v1',
          scheduler_enabled: true,
          partition_policy: selectedScenario.selector.policy,
          chunk_count: selectedScenario.selector.chunks,
        }),
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Failed to start live job');
      }

      const data = (await res.json()) as { id: string };
      setLiveJobId(data.id);
      setLiveJob({ id: data.id, status: 'queued', phase: 'queued', progress: 0 });
      setLiveStatus(`Live job ${data.id} started. Polling status...`);
      toast.success(`Live job ${data.id} started`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start live job';
      setLiveStatus(message);
      toast.error(message);
    } finally {
      setIsRunningLive(false);
    }
  };

  const sectionContent =
    activeSection === 'story' ? (
      <StoryMode />
    ) : activeSection === 'demo' ? (
      <div className="grid gap-5">
        <DemoControls
          selectedScenarioId={selectedScenarioId}
          onScenarioChange={handleScenarioChange}
          workerBudget={workerBudget}
          onWorkerBudgetChange={setWorkerBudget}
          liveAvailable={backendAvailable}
          liveInputPath={liveInputPath}
          uploadedFileName={uploadedFileName}
          uploadStatus={uploadStatus}
          liveStatus={liveStatus}
          liveJob={liveJob}
          isUploading={isUploading}
          isRunningLive={isRunningLive}
          onUpload={handleUpload}
          onRunLive={handleRunLive}
        />
        <BenchmarkComparison scenario={selectedScenario} />
        <SelectorDecisionPanel scenario={selectedScenario} workerBudget={workerBudget} />
      </div>
    ) : activeSection === 'evidence' ? (
      <EvidenceDashboard />
    ) : (
      <ArchitectureFlow />
    );

  return (
    <ResearchShell activeSection={activeSection} onSectionChange={setActiveSection} backendAvailable={backendAvailable}>
      {sectionContent}
      <Toaster position="bottom-right" theme="dark" closeButton />
    </ResearchShell>
  );
}

export default App;
