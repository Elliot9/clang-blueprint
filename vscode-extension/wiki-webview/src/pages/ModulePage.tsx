import { h } from 'preact';
import type { BlueprintIndex, ModuleEntry, PageRef } from '../types';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { RiskBadge } from '../components/RiskBadge';

interface Props {
  module: ModuleEntry;
  index: BlueprintIndex;
  onNavigate: (page: PageRef) => void;
}

function buildModuleClassDiagram(mod: ModuleEntry, index: BlueprintIndex): string {
  const classSet = new Set(mod.classNames);
  const classes = index.classes.filter(c => classSet.has(c.className));
  const lines = ['classDiagram'];
  for (const cls of classes) {
    for (const dep of cls.dependencies) {
      if (!classSet.has(dep.target)) continue;
      const arrow = dep.type === 'inheritance' ? '<|--'
        : dep.type === 'composition' ? '*--'
        : dep.type === 'aggregation' ? 'o--'
        : '-->';
      lines.push(`  ${dep.target} ${arrow} ${cls.className}`);
    }
  }
  if (lines.length === 1) lines.push('  note "No internal dependencies"');
  return lines.join('\n');
}

export function ModulePage({ module: mod, index, onNavigate }: Props) {
  const classes = index.classes.filter(c => mod.classNames.includes(c.className));
  const riskCounts = { high: 0, medium: 0, low: 0 };
  for (const c of classes) if (c.changeRisk) riskCounts[c.changeRisk]++;

  return (
    <main class="page">
      <header class="page-header">
        <div class="page-breadcrumb">
          <button class="link-btn" onClick={() => onNavigate({ kind: 'system' })}>Overview</button>
          {' / '}
        </div>
        <h1 class="page-title">▦ {mod.name}</h1>
        {mod.namespace && <div class="page-subtitle">namespace: {mod.namespace}</div>}
      </header>

      <section class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{mod.classNames.length}</div>
          <div class="stat-label">Classes</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{mod.internalEdgeCount}</div>
          <div class="stat-label">Internal deps</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{mod.externalDeps.length}</div>
          <div class="stat-label">External deps</div>
        </div>
        {riskCounts.high > 0 && (
          <div class="stat-card stat-card--risk">
            <div class="stat-value">{riskCounts.high}</div>
            <div class="stat-label">High-risk</div>
          </div>
        )}
      </section>

      {mod.externalDeps.length > 0 && (
        <section class="page-section">
          <h2>External Dependencies</h2>
          <ul class="dep-list">
            {mod.externalDeps.sort((a, b) => b.weight - a.weight).map(d => (
              <li key={d.target} class="dep-item">
                <button class="link-btn" onClick={() => onNavigate({ kind: 'module', name: d.target })}>
                  {d.target}
                </button>
                <span class="dep-weight">{d.weight} references</span>
                <span class="dep-types">{d.depTypes.join(', ')}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section class="page-section">
        <h2>Class Diagram</h2>
        <MermaidDiagram id={`module-${mod.name}`} definition={buildModuleClassDiagram(mod, index)} />
      </section>

      <section class="page-section">
        <h2>Classes</h2>
        <div class="class-table">
          {classes.map(cls => (
            <div key={cls.className} class="class-row" onClick={() => onNavigate({ kind: 'class', name: cls.className })}>
              <div class="class-row-name">◻ {cls.className}</div>
              <div class="class-row-intent">{cls.intent || cls.responsibility}</div>
              <div class="class-row-meta">
                {cls.designPattern && <span class="pattern-tag">{cls.designPattern}</span>}
                <RiskBadge risk={cls.changeRisk} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
