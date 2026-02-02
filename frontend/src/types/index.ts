export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type JobPhase = 'queued' | 'analyzing' | 'benchmarking' | 'parallel' | 'merging' | 'completed';
export type EngineVersion = 'v1' | 'v2';

export interface ComparisonReport {
  sample_seconds: number;
  input_size_mb: number;
  output_size_mb: number;
  size_change_pct: number;
  psnr_avg?: number | null;
  ssim_all?: number | null;
  summary: string;
  generated_at: number;
}

export interface RenderingJob {
  id: string;
  status: JobStatus;
  phase?: JobPhase;
  progress: number;
  input: string;
  output?: string;
  error?: string;
  workers: number;
  filter_chain?: string;
  duration?: string;
  projected_serial_time?: string;
  smart_config?: Record<string, unknown>;
  comparison_report?: ComparisonReport | null;
  created_at?: number;
  engine_version?: EngineVersion;
}

export interface ClusterStats {
  cpu_percent: number;
  cpu_count: number;
  memory_percent: number;
  active_jobs: number;
  queued_jobs: number;
  completed_jobs: number;
  avg_throughput_fps: number;
  success_rate: number;
}
