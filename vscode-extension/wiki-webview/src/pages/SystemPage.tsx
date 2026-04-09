import { h } from 'preact';
import type { BlueprintIndex, PageRef } from '../types';
import { MermaidDiagram } from '../components/MermaidDiagram';

interface Props {
  index: BlueprintIndex;
  onNavigate: (page: PageRef) => void;
}

function buildModuleGraph(index: BlueprintIndex): string {
  const lines = ['graph LR'];
  // nodes
  for (const mod of index.modules) {
    const label = `${mod.name}\\n${mod.classNames.length} classes`;
    lines.push(`  ${mod.name.replace(/\W/g, '_')}["${label}"]`);
  }
  // edges (top-N by weight)
  const sorted = [...index.moduleEdges].sort((a, b) => b.weight - a.weight).slice(0, 20);
  for (const e of sorted) {
    const s = e.source.replace(/\W/g, '_');
    const t = e.target.replace(/\W/g, '_');
    lines.push(`  ${s} -->|${e.weight}| ${t}`);
  }
  return lines.join('\n');
}

export function SystemPage({ index, onNavigate }: Props) {
  const totalClasses = index.classes.length;
  const totalDeps = index.classes.reduce((n, c) => n + c.dependencies.length, 0);
  const highRisk = index.classes.filter(c => c.changeRisk === 'high').length;

  return (
    <main class="page">
      <header class="page-header">
        <h1 class="page-title">{index.projectName || 'Project'}</h1>
        <div class="page-subtitle">System Overview</div>
        {index.projectSummary && (
          <p class="page-prose">{index.projectSummary}</p>
        )}
      </header>

      <section class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{index.modules.length}</div>
          <div class="stat-label">Modules</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{totalClasses}</div>
          <div class="stat-label">Classes</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{totalDeps}</div>
          <div class="stat-label">Dependencies</div>
        </div>
        <div class="stat-card stat-card--risk">
          <div class="stat-value">{highRisk}</div>
          <div class="stat-label">High-risk classes</div>
        </div>
      </section>

      {index.entryPoints.length > 0 && (
        <section class="page-section">
          <h2>Entry Points</h2>
          <ul class="entry-list">
            {index.entryPoints.map(ep => (
              <li key={ep.className} class="entry-item">
                <button class="link-btn" onClick={() => onNavigate({ kind: 'class', name: ep.className })}>
                  {ep.className}
                </button>
                <span class="entry-kind">{ep.kind}</span>
                <span class="entry-reason">{ep.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {index.moduleEdges.length > 0 && (
        <section class="page-section">
          <h2>Module Dependency Graph</h2>
          <MermaidDiagram id="system-module-graph" definition={buildModuleGraph(index)} />
        </section>
      )}

      <section class="page-section">
        <h2>Modules</h2>
        <div class="module-grid">
          {index.modules.map(mod => (
            <div key={mod.name} class="module-card" onClick={() => onNavigate({ kind: 'module', name: mod.name })}>
              <div class="module-card-name">▦ {mod.name}</div>
              <div class="module-card-meta">{mod.classNames.length} classes</div>
              {mod.namespace && <div class="module-card-ns">{mod.namespace}</div>}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
