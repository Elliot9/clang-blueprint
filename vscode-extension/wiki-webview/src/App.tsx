import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import type { BlueprintIndex, BlueprintChanges, HostMessage, PageRef } from './types';
import { Sidebar } from './components/Sidebar';
import { SystemPage } from './pages/SystemPage';
import { ModulePage } from './pages/ModulePage';
import { ClassPage } from './pages/ClassPage';
import { ChangesPage } from './pages/ChangesPage';

declare function acquireVsCodeApi(): { postMessage: (m: unknown) => void };

export function App() {
  const [index, setIndex] = useState<BlueprintIndex | null>(null);
  const [changes, setChanges] = useState<BlueprintChanges | undefined>(undefined);
  const [page, setPage] = useState<PageRef>({ kind: 'system' });

  useEffect(() => {
    // Notify extension host that we're ready
    try {
      acquireVsCodeApi().postMessage({ type: 'ready' });
    } catch { /* outside VS Code (dev mode) */ }

    // Listen for messages from extension host
    window.addEventListener('message', (event) => {
      const msg = event.data as HostMessage;
      if (msg.type === 'load') {
        setIndex(msg.index);
      } else if (msg.type === 'loadChanges') {
        setChanges(msg.changes);
      } else if (msg.type === 'navigate') {
        setPage(msg.page);
      }
    });
  }, []);

  if (!index) {
    return (
      <div class="loading">
        <div class="loading-spinner">◈</div>
        <div>Loading Blueprint index…</div>
      </div>
    );
  }

  function renderPage() {
    if (!index) return null;
    switch (page.kind) {
      case 'system':
        return <SystemPage index={index} onNavigate={setPage} />;
      case 'module': {
        const mod = index.modules.find(m => m.name === page.name);
        if (!mod) return <div class="error-page">Module not found: {page.name}</div>;
        return <ModulePage module={mod} index={index} onNavigate={setPage} />;
      }
      case 'class': {
        const cls = index.classes.find(c => c.className === page.name);
        if (!cls) return <div class="error-page">Class not found: {page.name}</div>;
        return <ClassPage cls={cls} index={index} onNavigate={setPage} />;
      }
      case 'changes': {
        const ch = changes ?? { version: 1, records: [] };
        return <ChangesPage changes={ch} onNavigate={setPage} />;
      }
    }
  }

  return (
    <div class="app-layout">
      <Sidebar index={index} changes={changes} current={page} onNavigate={setPage} />
      <div class="content-area">
        {renderPage()}
      </div>
    </div>
  );
}
