import { Bell, Search, Command } from "lucide-react";

export function TopBar() {
  return (
    <header className="h-16 border-b border-[#222222] bg-[#0a0a0a]/80 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-10">
      <div className="flex items-center gap-4 flex-1">
        <div className="relative w-96 group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 transition-colors group-focus-within:text-white" />
          <input 
            type="text" 
            placeholder="Search jobs, nodes, or commands..."
            className="w-full bg-[#151515] border border-[#222222] rounded-xl py-2 pl-10 pr-4 text-sm outline-none focus:border-[#444444] transition-all"
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 bg-[#222222] rounded border border-[#333333] flex items-center gap-1">
             <Command className="w-2.5 h-2.5 text-zinc-400" />
             <span className="text-[10px] text-zinc-400 font-bold">K</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="relative w-10 h-10 flex items-center justify-center hover:bg-white/5 rounded-xl transition-all">
          <Bell className="w-5 h-5 text-zinc-400" />
          <div className="absolute top-2.5 right-2.5 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0a0a0a]" />
        </button>
        <div className="h-6 w-px bg-[#222222]" />
        <div className="flex items-center gap-3 pl-2">
          <div className="flex flex-col items-end">
            <span className="text-sm font-semibold">Arnav Bansal</span>
            <span className="text-[10px] text-zinc-500 font-medium">System Admin</span>
          </div>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 border border-white/10 shadow-lg shadow-indigo-500/10" />
        </div>
      </div>
    </header>
  );
}
