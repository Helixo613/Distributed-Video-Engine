import { useEffect, useState } from "react";
import { MoreVertical, Video, ChevronRight, AlertCircle, CheckCircle2 } from "lucide-react";
import { Progress } from "../ui/progress";
import { Badge } from "./badge";
import type { RenderingJob } from "../../types";
import { apiUrl } from "../../lib/api";

export function JobList() {
  const [jobs, setJobs] = useState<RenderingJob[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      const res = await fetch(apiUrl('/jobs'));
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (e) {
      console.error("Failed to fetch jobs", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 1000); // Poll every second
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-[#111111] border border-[#222222] rounded-2xl overflow-hidden min-h-[400px]">
      <div className="p-6 border-b border-[#222222] flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-white">Active Operations</h3>
          <p className="text-xs text-zinc-500 font-medium">Monitoring {jobs.length} total tasks</p>
        </div>
        <button className="text-xs font-bold text-zinc-400 hover:text-white transition-colors flex items-center gap-1">
          View All History <ChevronRight className="w-3 h-3" />
        </button>
      </div>

      <div className="divide-y divide-[#222222]">
        {jobs.length === 0 && !loading && (
          <div className="p-8 text-center text-zinc-500 text-sm">No active jobs found. Deploy a new job to start.</div>
        )}
        
        {jobs.map((job) => (
          <div key={job.id} className="p-4 hover:bg-white/[0.02] transition-colors group">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#1a1a1a] flex items-center justify-center border border-[#333333]">
                  {job.status === 'failed' ? (
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  ) : job.status === 'completed' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                  ) : (
                    <Video className="w-5 h-5 text-zinc-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold truncate max-w-[200px]">{job.input}</span>
                    <Badge variant={job.status}>{job.status}</Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">#{job.id}</span>
                    <div className="w-1 h-1 rounded-full bg-zinc-700" />
                    <span className="text-[10px] text-zinc-500 font-medium">{job.workers} Workers</span>
                                    {job.engine_version && (
                                      <>
                                        <div className="w-1 h-1 rounded-full bg-zinc-700" />
                                        <span className={`text-[10px] font-bold ${job.engine_version === 'v2' ? 'text-purple-400' : 'text-orange-400'}`}>
                                          {job.engine_version.toUpperCase()}
                                        </span>
                                      </>
                                    )}
                  </div>
                </div>
              </div>
              <button className="p-2 hover:bg-white/5 rounded-lg opacity-0 group-hover:opacity-100 transition-all">
                <MoreVertical className="w-4 h-4 text-zinc-500" />
              </button>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex justify-between text-[10px] font-bold mb-1.5 uppercase tracking-wide">
                  <span className="text-zinc-500">Processing Progress</span>
                  <span className="text-zinc-300">{job.progress}%</span>
                </div>
                <Progress value={job.progress} className="h-1.5" />
              </div>
              <div className="flex items-center gap-4 pl-4 border-l border-[#222222]">
                <div className="flex flex-col min-w-[60px]">
                   <span className="text-[10px] text-zinc-500 font-bold uppercase">Duration</span>
                   <span className="text-xs font-semibold tabular-nums">{job.duration || "--"}</span>
                </div>
                {job.output && (
                   <div className="flex flex-col">
                      <a href={apiUrl(job.output)} target="_blank" rel="noreferrer" className="text-[10px] text-blue-400 font-bold uppercase hover:underline cursor-pointer">
                        Download
                      </a>
                   </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
