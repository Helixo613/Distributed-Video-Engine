import { useEffect, useRef, useState } from 'react';
import type { SyntheticEvent } from 'react';
import { Scale, FileVideo2, Sparkles, Play, Pause } from 'lucide-react';
import type { RenderingJob } from '../../types';
import { apiUrl } from '../../lib/api';

interface VideoComparisonProps {
  job: RenderingJob;
}

function toSourceRoute(inputPath: string): string {
  if (inputPath.startsWith('uploads/')) {
    return apiUrl(`/${inputPath}`);
  }

  const encoded = inputPath
    .split('/')
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join('/');
  return apiUrl(`/files/${encoded}`);
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export function VideoComparison({ job }: VideoComparisonProps) {
  const hasData = Boolean(job.output && job.comparison_report);
  const primarySourceUrl = toSourceRoute(job.input);
  const fallbackSourceUrl = apiUrl(`/files/${job.input.split('/').map((p) => encodeURIComponent(p)).join('/')}`);
  const outputUrl = job.output ? apiUrl(job.output) : '';
  const report = job.comparison_report;

  const originalRef = useRef<HTMLVideoElement>(null);
  const processedRef = useRef<HTMLVideoElement>(null);
  const wipeOriginalRef = useRef<HTMLVideoElement>(null);
  const wipeProcessedRef = useRef<HTMLVideoElement>(null);
  const syncingRef = useRef(false);

  const [sourceUrl, setSourceUrl] = useState(primarySourceUrl);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [wipePosition, setWipePosition] = useState(50);

  useEffect(() => {
    setSourceUrl(primarySourceUrl);
  }, [primarySourceUrl]);

  if (!hasData || !report) return null;

  const syncGroup = (leader: HTMLVideoElement, followers: Array<HTMLVideoElement | null>) => {
    if (syncingRef.current) return;
    syncingRef.current = true;

    followers.forEach((video) => {
      if (!video) return;
      if (Math.abs(video.currentTime - leader.currentTime) > 0.12) {
        video.currentTime = leader.currentTime;
      }
      video.playbackRate = leader.playbackRate;
    });

    const shouldPlay = !leader.paused;
    followers.forEach((video) => {
      if (!video) return;
      if (shouldPlay && video.paused) {
        void video.play().catch(() => undefined);
      }
      if (!shouldPlay && !video.paused) {
        video.pause();
      }
    });

    requestAnimationFrame(() => {
      syncingRef.current = false;
    });
  };

  const allVideos = () => [originalRef.current, processedRef.current, wipeOriginalRef.current, wipeProcessedRef.current].filter(Boolean) as HTMLVideoElement[];

  const handleVideoEvent = (leader: HTMLVideoElement) => {
    const followers = allVideos().filter((v) => v !== leader);
    syncGroup(leader, followers);
    setIsPlaying(!leader.paused);
    if (Number.isFinite(leader.currentTime)) setCurrentTime(leader.currentTime);
    if (Number.isFinite(leader.duration) && leader.duration > 0) setDuration(leader.duration);
  };

  const togglePlayback = () => {
    const leader = originalRef.current || processedRef.current;
    if (!leader) return;

    if (leader.paused) {
      void leader.play().catch(() => undefined);
    } else {
      leader.pause();
    }
    handleVideoEvent(leader);
  };

  const seekAll = (nextTime: number) => {
    allVideos().forEach((video) => {
      video.currentTime = nextTime;
    });
    setCurrentTime(nextTime);
  };

  const exportReport = () => {
    const payload = {
      job_id: job.id,
      input: job.input,
      output: job.output,
      comparison_report: report,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `comparison-report-${job.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const sharedVideoProps = {
    preload: 'metadata' as const,
    onPlay: (e: SyntheticEvent<HTMLVideoElement>) => handleVideoEvent(e.currentTarget),
    onPause: (e: SyntheticEvent<HTMLVideoElement>) => handleVideoEvent(e.currentTarget),
    onSeeking: (e: SyntheticEvent<HTMLVideoElement>) => handleVideoEvent(e.currentTarget),
    onRateChange: (e: SyntheticEvent<HTMLVideoElement>) => handleVideoEvent(e.currentTarget),
    onTimeUpdate: (e: SyntheticEvent<HTMLVideoElement>) => {
      const leader = e.currentTarget;
      setCurrentTime(leader.currentTime);
      if (Number.isFinite(leader.duration) && leader.duration > 0) {
        setDuration(leader.duration);
      }
    },
    onLoadedMetadata: (e: SyntheticEvent<HTMLVideoElement>) => {
      const leader = e.currentTarget;
      if (Number.isFinite(leader.duration) && leader.duration > 0) {
        setDuration(leader.duration);
      }
    },
  };

  return (
    <div className="bg-[#111111] border border-[#222] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
          <Scale className="w-4 h-4" />
          Before vs After Comparison
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">{report.sample_seconds}s analysis window</span>
          <button
            onClick={exportReport}
            className="text-[10px] px-2 py-1 rounded-md border border-[#333] bg-[#0a0a0a] hover:bg-[#161616] text-zinc-300 font-bold uppercase tracking-wider"
          >
            Export Report
          </button>
        </div>
      </div>

      <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3 mb-5">
        <div className="flex items-center gap-3 mb-3">
          <button
            onClick={togglePlayback}
            className="h-8 w-8 rounded-lg border border-[#333] bg-[#151515] hover:bg-[#1f1f1f] flex items-center justify-center"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <input
            type="range"
            min={0}
            max={duration || 0}
            value={Math.min(currentTime, duration || 0)}
            onChange={(e) => seekAll(parseFloat(e.target.value))}
            className="flex-1 accent-cyan-500"
          />
          <span className="text-xs text-zinc-400 font-mono min-w-[88px] text-right">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-black border border-[#222] rounded-xl p-3">
            <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-2">Original</p>
            <video
              ref={originalRef}
              src={sourceUrl}
              controls
              className="w-full rounded-lg bg-black aspect-video"
              onError={() => {
                if (sourceUrl !== fallbackSourceUrl) setSourceUrl(fallbackSourceUrl);
              }}
              {...sharedVideoProps}
            />
          </div>
          <div className="bg-black border border-[#222] rounded-xl p-3">
            <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-2">Processed</p>
            <video ref={processedRef} src={outputUrl} controls className="w-full rounded-lg bg-black aspect-video" {...sharedVideoProps} />
          </div>
        </div>
      </div>

      <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3 mb-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Frame Wipe Comparator</p>
          <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Split {wipePosition}%</span>
        </div>

        <div className="relative rounded-lg overflow-hidden border border-[#222] aspect-video bg-black mb-3">
          <video
            ref={wipeOriginalRef}
            src={sourceUrl}
            muted
            className="absolute inset-0 w-full h-full object-cover"
            onError={() => {
              if (sourceUrl !== fallbackSourceUrl) setSourceUrl(fallbackSourceUrl);
            }}
            {...sharedVideoProps}
          />
          <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - wipePosition}% 0 0)` }}>
            <video ref={wipeProcessedRef} src={outputUrl} muted className="w-full h-full object-cover" {...sharedVideoProps} />
          </div>
          <div className="absolute top-0 bottom-0 w-[2px] bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.75)]" style={{ left: `${wipePosition}%` }} />
        </div>

        <input
          type="range"
          min={0}
          max={100}
          value={wipePosition}
          onChange={(e) => setWipePosition(parseInt(e.target.value, 10))}
          className="w-full accent-cyan-500"
        />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <MetricCard label="PSNR Avg" value={report.psnr_avg != null ? `${report.psnr_avg.toFixed(2)} dB` : 'N/A'} />
        <MetricCard label="SSIM" value={report.ssim_all != null ? report.ssim_all.toFixed(4) : 'N/A'} />
        <MetricCard label="Input Size" value={`${report.input_size_mb.toFixed(2)} MB`} />
        <MetricCard label="Output Size" value={`${report.output_size_mb.toFixed(2)} MB`} />
      </div>

      <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-4 flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles className="w-4 h-4 text-indigo-400" />
        </div>
        <div>
          <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-1">Summary Report</p>
          <p className="text-sm text-zinc-200">{report.summary}</p>
          <p className="text-[11px] text-zinc-500 mt-2 flex items-center gap-1">
            <FileVideo2 className="w-3 h-3" />
            Size delta: {report.size_change_pct > 0 ? '+' : ''}
            {report.size_change_pct.toFixed(2)}%
          </p>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3">
      <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">{label}</p>
      <p className="text-sm text-white font-semibold mt-1">{value}</p>
    </div>
  );
}
