import { useEffect, useState } from "react";
import { Cpu, Zap, Clock, CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClusterStats } from "../../types";
import { apiUrl } from "../../lib/api";

export function StatsCards() {
  const [stats, setStats] = useState<ClusterStats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(apiUrl('/stats'));
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (e) {
        console.error("Failed to fetch stats", e);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 2000); // Poll every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const statCards = [
    {
      label: "Cluster Load",
      value: stats ? `${stats.cpu_percent.toFixed(1)}%` : "--",
      icon: Cpu,
      color: "text-blue-400",
      sub: stats ? `${stats.cpu_count} Cores Active` : "Loading..."
    },
    {
      label: "Avg. Throughput",
      value: stats ? `${stats.avg_throughput_fps} fps` : "--",
      icon: Zap,
      color: "text-emerald-400",
      sub: stats ? `Memory: ${stats.memory_percent.toFixed(0)}%` : "Loading..."
    },
    {
      label: "Active Jobs",
      value: stats ? `${stats.active_jobs}` : "--",
      icon: Clock,
      color: "text-orange-400",
      sub: stats ? `${stats.queued_jobs} queued` : "Loading..."
    },
    {
      label: "Completed",
      value: stats ? `${stats.completed_jobs}` : "--",
      icon: CheckCircle2,
      color: "text-indigo-400",
      sub: stats ? `${stats.success_rate}% Success Rate` : "Loading..."
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {statCards.map((stat) => (
        <div key={stat.label} className="stats-card group">
          <div className="flex items-start justify-between mb-4">
            <div className={cn("p-2 rounded-xl bg-opacity-10", stat.color.replace('text-', 'bg-'))}>
              <stat.icon className={cn("w-5 h-5", stat.color)} />
            </div>
            <span className={cn(
              "text-[10px] font-bold px-1.5 py-0.5 rounded border",
              stats
                ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/20"
                : "text-zinc-500 bg-zinc-500/10 border-zinc-500/20"
            )}>
              {stats ? "LIVE" : "OFFLINE"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-zinc-500 text-xs font-medium uppercase tracking-wider">{stat.label}</span>
            <span className="text-2xl font-bold tracking-tight my-1">{stat.value}</span>
            <span className="text-zinc-500 text-[10px] font-medium">{stat.sub}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
