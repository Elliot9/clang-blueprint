import { h } from 'preact';
import type { BlueprintIndex, ClassEntry, PageRef } from '../types';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { RiskBadge } from '../components/RiskBadge';

interface Props {
  cls: ClassEntry;
  index: BlueprintIndex;
  onNavigate: (page: PageRef) => void;
}

function getModule(cls: ClassEntry, index: BlueprintIndex) {
  return index.modules.find(m => m.classNames.includes(cls.className));
}

function buildClassDiagram(cls: ClassEntry, index: BlueprintIndex): string {
  const lines = ['classDiagram'];
  // direct deps
  for (const dep of cls.dependencies) {
    const arrow = dep.type === 'inheritance' ? '<|--'
      : dep.type === 'composition' ? '*--'
      : dep.type === 'aggregation' ? 'o--'
      : '-->';
    lines.push(`  ${dep.target} ${arrow} ${cls.className} : ${dep.type}`);
  }
  // base classes not already in deps
  for (const base of cls.baseClasses) {
    if (!cls.dependencies.some(d => d.target === base && d.type === 'inheritance')) {
      lines.push(`  ${base} <|-- ${cls.className}`);
    }
  }
  // reverse deps (who depends on this)
  const reverseDeps = index.classes.filter(c =>
    c.className !== cls.className &&
    c.dependencies.some(d => d.target === cls.className)
  ).slice(0, 8);
  for (const rev of reverseDeps) {
    const dep = rev.dependencies.find(d => d.target === cls.className)!;
    const arrow = dep.type === 'inheritance' ? '<|--'
      : dep.type === 'composition' ? '*--'
      : dep.type === 'aggregation' ? 'o--'
      : '-->';
    lines.push(`  ${cls.className} ${arrow} ${rev.className} : used by`);
  }
  if (lines.length === 1) lines.push(`  class ${cls.className}`);
  return lines.join('\n');
}

declare const acquireVsCodeApi: () => { postMessage: (m: unknown) => void };

export function ClassPage({ cls, index, onNavigate }: Props) {
  const mod = getModule(cls, index);
  const reverseDeps = index.classes.filter(c =>
    c.className !== cls.className &&
    c.dependencies.some(d => d.target === cls.className)
  );

  function jumpToSource() {
    try {
      const vscode = acquireVsCodeApi();
      vscode.postMessage({ type: 'jumpToSource', file: cls.fileLocation, line: cls.lineNumber });
    } catch { /* running outside VS Code */ }
  }

  return (
    <main class="page">
      <header class="page-header">
        <div class="page-breadcrumb">
          <button class="link-btn" onClick={() => onNavigate({ kind: 'system' })}>Overview</button>
          {mod && (
            <>
              {' / '}
              <button class="link-btn" onClick={() => onNavigate({ kind: 'module', name: mod.name })}>
                {mod.name}
              </button>
            </>
          )}
          {' / '}
        </div>
        <h1 class="page-title">◻ {cls.className}</h1>
        {cls.namespace && <div class="page-subtitle">namespace: {cls.namespace}</div>}
      </header>

      {/* Intent + metadata strip */}
      <section class="meta-strip">
        {cls.intent && <p class="class-intent">"{cls.intent}"</p>}
        <div class="meta-tags">
          {cls.designPattern && <span class="pattern-tag">⬡ {cls.designPattern}</span>}
          <RiskBadge risk={cls.changeRisk} />
          <button class="source-link" onClick={jumpToSource}>
            ↗ {cls.fileLocation}:{cls.lineNumber}
          </button>
        </div>
        {cls.tradeoffs && cls.tradeoffs.length > 0 && (
          <div class="tradeoffs-box">
            <span class="tradeoffs-label">Trade-offs</span>
            <ul>{cls.tradeoffs.map(t => <li>{t}</li>)}</ul>
          </div>
        )}
      </section>

      {/* Dependency diagram */}
      <section class="page-section">
        <h2>Dependency Diagram</h2>
        <MermaidDiagram id={`class-${cls.className}`} definition={buildClassDiagram(cls, index)} />
      </section>

      {/* Interfaces */}
      {cls.interfaces.length > 0 && (
        <section class="page-section">
          <h2>Public Interface</h2>
          <ul class="interface-list">
            {cls.interfaces.map((sig, i) => (
              <li key={i} class="interface-item"><code>{sig}</code></li>
            ))}
          </ul>
        </section>
      )}

      {/* Base classes */}
      {cls.baseClasses.length > 0 && (
        <section class="page-section">
          <h2>Inherits From</h2>
          <div class="chip-row">
            {cls.baseClasses.map(b => (
              <button key={b} class="chip" onClick={() => onNavigate({ kind: 'class', name: b })}>
                {b}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Dependencies */}
      {cls.dependencies.length > 0 && (
        <section class="page-section">
          <h2>Dependencies ({cls.dependencies.length})</h2>
          <div class="dep-grid">
            {cls.dependencies.map(dep => (
              <div key={dep.target + dep.type} class={`dep-card dep-card--${dep.type}`}>
                <button class="link-btn" onClick={() => onNavigate({ kind: 'class', name: dep.target })}>
                  {dep.target}
                </button>
                <span class="dep-type-tag">{dep.type}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Used by */}
      {reverseDeps.length > 0 && (
        <section class="page-section">
          <h2>Used By ({reverseDeps.length})</h2>
          <div class="chip-row">
            {reverseDeps.map(r => (
              <button key={r.className} class="chip" onClick={() => onNavigate({ kind: 'class', name: r.className })}>
                {r.className}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Attributes */}
      {cls.attributes && cls.attributes.length > 0 && (
        <section class="page-section">
          <h2>Fields</h2>
          <ul class="interface-list">
            {cls.attributes.map((a, i) => <li key={i} class="interface-item"><code>{a}</code></li>)}
          </ul>
        </section>
      )}
    </main>
  );
}
