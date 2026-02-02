import { Activity, Cpu, History, Settings, HelpCircle, Github } from "lucide-react";
import { useState } from "react";

type Tab = 'monitor' | 'history' | 'settings';

interface SidebarProps {
  activeTab?: Tab;
  onTabChange?: (tab: Tab) => void;
}

export function Sidebar({ activeTab = 'monitor', onTabChange }: SidebarProps) {
  const [currentTab, setCurrentTab] = useState<Tab>(activeTab);

  const handleTabChange = (tab: Tab) => {
    setCurrentTab(tab);
    onTabChange?.(tab);
  };

  const navItems = [
    { id: 'monitor' as Tab, icon: Activity, label: 'Monitor', active: true },
    { id: 'history' as Tab, icon: History, label: 'History', active: true },
    { id: 'settings' as Tab, icon: Settings, label: 'Settings', active: false },
  ];

  return (
    <aside className="w-16 md:w-64 bg-[#0a0a0a] border-r border-[#1a1a1a] flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div className="hidden md:block">
            <h1 className="text-sm font-bold">HPC Engine</h1>
            <p className="text-[10px] text-zinc-500">v2.0 • Distributed</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => item.active && handleTabChange(item.id)}
            disabled={!item.active}
            className={`
              w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all
              ${currentTab === item.id
                ? 'bg-indigo-500/20 text-indigo-400'
                : item.active
                  ? 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white'
                  : 'text-zinc-600 cursor-not-allowed'
              }
            `}
          >
            <item.icon className="w-5 h-5" />
            <span className="hidden md:block text-sm font-medium">{item.label}</span>
            {!item.active && (
              <span className="hidden md:block ml-auto text-[8px] bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-500">
                SOON
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-[#1a1a1a] space-y-1">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-zinc-500 hover:bg-zinc-800/50 hover:text-white transition-all"
        >
          <Github className="w-5 h-5" />
          <span className="hidden md:block text-sm font-medium">GitHub</span>
        </a>
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-zinc-500 hover:bg-zinc-800/50 hover:text-white transition-all">
          <HelpCircle className="w-5 h-5" />
          <span className="hidden md:block text-sm font-medium">Help</span>
        </button>
      </div>
    </aside>
  );
}
