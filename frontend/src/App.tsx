import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { ResearchShell } from './components/research/research-shell';
import { StoryMode } from './components/research/story-mode';
import type { ResearchSection } from './research-demo-data';
import { apiUrl } from './lib/api';

function App() {
  const [activeSection, setActiveSection] = useState<ResearchSection>('story');
  const [backendAvailable, setBackendAvailable] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(apiUrl('/health'));
        setBackendAvailable(res.ok);
      } catch {
        setBackendAvailable(false);
      }
    };

    checkHealth();
  }, []);

  const sectionContent =
    activeSection === 'story' ? (
      <StoryMode />
    ) : (
      <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <h2 className="text-xl font-semibold capitalize text-white">{activeSection}</h2>
        <p className="mt-2 text-sm text-zinc-400">This section will be implemented in the next tasks.</p>
      </section>
    );

  return (
    <ResearchShell activeSection={activeSection} onSectionChange={setActiveSection} backendAvailable={backendAvailable}>
      {sectionContent}
      <Toaster position="bottom-right" theme="dark" closeButton />
    </ResearchShell>
  );
}

export default App;
