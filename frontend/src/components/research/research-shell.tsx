import { BarChart3, BookOpen, Cpu, Network } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ResearchSection } from '../../research-demo-data';
import { ResearchHero } from './research-hero';

interface ResearchShellProps {
  activeSection: ResearchSection;
  onSectionChange: (section: ResearchSection) => void;
  backendAvailable: boolean;
  children: ReactNode;
}

const navItems: Array<{ id: ResearchSection; label: string; icon: LucideIcon }> = [
  { id: 'story', label: 'Story', icon: BookOpen },
  { id: 'demo', label: 'Live Demo', icon: Cpu },
  { id: 'evidence', label: 'Evidence', icon: BarChart3 },
  { id: 'architecture', label: 'Architecture', icon: Network },
];

export function ResearchShell({ activeSection, onSectionChange, backendAvailable, children }: ResearchShellProps) {
  return (
    <div className="min-h-screen bg-[#08090b] text-white">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-[#08090b]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <div className="text-sm font-semibold text-white">Distributed Video Engine</div>
            <div className="text-xs text-zinc-500">Research demonstration console</div>
          </div>
          <nav className="flex gap-2 overflow-x-auto">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSectionChange(item.id)}
                className={
                  activeSection === item.id
                    ? 'inline-flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm font-semibold text-zinc-950'
                    : 'inline-flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm font-semibold text-zinc-300 hover:border-zinc-600'
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1500px] flex-col gap-6 px-4 py-6 md:px-8">
        <ResearchHero onNavigate={onSectionChange} backendAvailable={backendAvailable} />
        {children}
      </main>
    </div>
  );
}
