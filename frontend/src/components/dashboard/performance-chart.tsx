import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

const data = [
  { time: '00:00', load: 45, fps: 22 },
  { time: '04:00', load: 52, fps: 24 },
  { time: '08:00', load: 88, fps: 28 },
  { time: '12:00', load: 74, fps: 25 },
  { time: '16:00', load: 92, fps: 30 },
  { time: '20:00', load: 65, fps: 24 },
  { time: '23:59', load: 48, fps: 21 },
];

export function PerformanceChart() {
  return (
    <div className="bg-[#111111] border border-[#222222] rounded-2xl p-6 h-[400px]">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h3 className="text-lg font-bold">Cluster Performance</h3>
          <p className="text-xs text-zinc-500 font-medium">System throughput and resource utilization over 24h</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-white" />
            <span className="text-xs text-zinc-400 font-medium">Load %</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-indigo-500" />
            <span className="text-xs text-zinc-400 font-medium">FPS</span>
          </div>
        </div>
      </div>
      
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorLoad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffffff" stopOpacity={0.1}/>
                <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorFps" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.1}/>
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#222222" vertical={false} />
            <XAxis 
              dataKey="time" 
              stroke="#555555" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false} 
              dy={10}
            />
            <YAxis 
              stroke="#555555" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false} 
              dx={-10}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#151515', border: '1px solid #333', borderRadius: '12px' }}
              itemStyle={{ fontSize: '12px' }}
            />
            <Area type="monotone" dataKey="load" stroke="#ffffff" strokeWidth={2} fillOpacity={1} fill="url(#colorLoad)" />
            <Area type="monotone" dataKey="fps" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorFps)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}