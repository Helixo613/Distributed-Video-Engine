import { useEffect, useState } from 'react';
import type { ComponentType } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Cpu, Zap, Activity, HardDrive } from 'lucide-react';
import { cn } from '../../lib/utils';
import { apiUrl } from '../../lib/api';

interface ClusterStats {
  cpu_percent: number;
  memory_percent: number;
  active_jobs: number;
  avg_throughput_fps: number;
}

interface HistoryPoint {
  time: string;
  cpu: number;
  mem: number;
  fps: number;
}

interface StatCardProps {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
  color: string;
  bg: string;
  trend?: number;
}

export function RealtimeMonitor() {
  const [stats, setStats] = useState<ClusterStats | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(apiUrl('/stats'));
        if (res.ok) {
          const data = await res.json();
          setStats(data);
          setHistory(prev => {
            const now = new Date();
            const timeStr = `${now.getHours()}:${now.getMinutes()}:${now.getSeconds()}`;
            const newPoint = {
              time: timeStr,
              cpu: data.cpu_percent,
              mem: data.memory_percent,
              fps: data.avg_throughput_fps
            };
            return [...prev.slice(-20), newPoint]; // Keep last 20 points
          });
        }
      } catch {
        // Silent fail
      }
    };

    const interval = setInterval(fetchStats, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div className="h-32 bg-[#111111] animate-pulse rounded-2xl" />;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <StatCard 
        label="CPU Utilization" 
        value={`${stats.cpu_percent.toFixed(1)}%`} 
        icon={Cpu} 
        color="text-blue-400" 
        bg="bg-blue-500/10"
        trend={history.length > 1 ? history[history.length - 1].cpu - history[history.length - 2].cpu : 0}
      />
      <StatCard 
        label="Memory Usage" 
        value={`${stats.memory_percent.toFixed(1)}%`} 
        icon={HardDrive} 
        color="text-purple-400" 
        bg="bg-purple-500/10"
      />
      <StatCard 
        label="Throughput" 
        value={`${stats.avg_throughput_fps} FPS`} 
        icon={Zap} 
        color="text-yellow-400" 
        bg="bg-yellow-500/10"
      />
      <StatCard 
        label="Active Jobs" 
        value={stats.active_jobs.toString()} 
        icon={Activity} 
        color="text-emerald-400" 
        bg="bg-emerald-500/10"
      />
      
      <div className="col-span-1 md:col-span-4 bg-[#111111] border border-[#222222] rounded-2xl p-4 h-64">
        <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-4">Real-time Cluster Load</h3>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history}>
            <defs>
              <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#222222" vertical={false} />
            <XAxis dataKey="time" hide />
            <YAxis stroke="#444" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px' }}
              itemStyle={{ fontSize: '12px' }}
            />
            <Area type="monotone" dataKey="cpu" stroke="#60a5fa" fillOpacity={1} fill="url(#colorCpu)" strokeWidth={2} />
            <Area type="monotone" dataKey="mem" stroke="#c084fc" fill="none" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color, bg, trend }: StatCardProps) {
  return (
    <div className="bg-[#111111] border border-[#222222] rounded-2xl p-4 flex items-center justify-between">
      <div>
        <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">{label}</p>
        <div className="flex items-baseline gap-2">
          <p className="text-xl font-bold mt-1 tracking-tight">{value}</p>
          {trend !== undefined && trend !== 0 && (
            <span className={cn("text-[10px] font-medium", trend > 0 ? "text-red-400" : "text-emerald-400")}>
              {trend > 0 ? "↑" : "↓"} {Math.abs(trend).toFixed(1)}%
            </span>
          )}
        </div>
      </div>
      <div className={cn("p-2.5 rounded-xl", bg)}>
        <Icon className={cn("w-5 h-5", color)} />
      </div>
    </div>
  )
}
