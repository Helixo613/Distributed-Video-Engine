import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { ArchitectureFlow } from './components/research/architecture-flow';
import { DemoControls } from './components/research/demo-controls';
import { EvidenceDashboard } from './components/research/evidence-dashboard';
import { ResearchShell } from './components/research/research-shell';
import { SelectorDecisionPanel } from './components/research/selector-decision-panel';
import { StoryMode } from './components/research/story-mode';
import { demoScenarios } from './research-demo-data';
import type { ResearchSection } from './research-demo-data';
import { apiUrl } from './lib/api';

function App() {
  const [activeSection, setActiveSection] = useState<ResearchSection>('story');
  const [backendAvailable, setBackendAvailable] = useState(false);
  const [selectedScenarioId, setSelectedScenarioId] = useState(demoScenarios[0].id);
  const [workerBudget, setWorkerBudget] = useState(4);

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

  const selectedScenario = demoScenarios.find((scenario) => scenario.id === selectedScenarioId) ?? demoScenarios[0];

  const sectionContent =
    activeSection === 'story' ? (
      <StoryMode />
    ) : activeSection === 'demo' ? (
      <div className="grid gap-5">
        <DemoControls
          selectedScenarioId={selectedScenarioId}
          onScenarioChange={setSelectedScenarioId}
          workerBudget={workerBudget}
          onWorkerBudgetChange={setWorkerBudget}
          liveAvailable={backendAvailable}
        />
        <SelectorDecisionPanel scenario={selectedScenario} workerBudget={workerBudget} />
      </div>
    ) : activeSection === 'evidence' ? (
      <EvidenceDashboard />
    ) : (
      <ArchitectureFlow />
    );

  return (
    <ResearchShell activeSection={activeSection} onSectionChange={setActiveSection} backendAvailable={backendAvailable}>
      {sectionContent}
      <Toaster position="bottom-right" theme="dark" closeButton />
    </ResearchShell>
  );
}

export default App;
