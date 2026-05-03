import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { budgetTradeoffs, keyResults, runtimeComparison } from '../../research-demo-data';

export function EvidenceDashboard() {
  return (
    <section className="grid gap-5">
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Reviewer Evidence</div>
        <h2 className="mt-1 text-2xl font-semibold text-white">Paper-aligned results</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">
          These metrics connect the classroom demo to the project evaluation: runtime wins, selector quality,
          prediction calibration, and resource-budget behavior.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {keyResults.map((result) => (
          <article key={result.label} className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
            <result.icon className="h-5 w-5 text-cyan-300" />
            <div className="mt-4 text-3xl font-semibold text-white">{result.value}</div>
            <div className="mt-1 text-sm font-semibold text-zinc-200">{result.label}</div>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{result.detail}</p>
          </article>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
          <h3 className="text-sm font-semibold text-white">Runtime comparison</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={runtimeComparison}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="case" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }} />
                <Bar dataKey="serial" fill="#71717a" radius={[4, 4, 0, 0]} />
                <Bar dataKey="static" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="adaptive" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5">
          <h3 className="text-sm font-semibold text-white">Worker budget tradeoffs</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={budgetTradeoffs}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="budget" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }} />
                <Line type="monotone" dataKey="speedup" stroke="#22c55e" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="efficiency" stroke="#38bdf8" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </section>
  );
}
