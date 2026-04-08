import { h } from 'preact';
import { useState } from 'preact/hooks';
import type { BlueprintIndex, PageRef } from '../types';

interface Props {
  index: BlueprintIndex;
  current: PageRef;
  onNavigate: (page: PageRef) => void;
}

export function Sidebar({ index, current, onNavigate }: Props) {
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');

  function toggleModule(name: string) {
    setExpandedModules(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  const q = search.toLowerCase();
  const filteredModules = q
    ? index.modules.filter(m =>
        m.name.toLowerCase().includes(q) ||
        m.classNames.some(c => c.toLowerCase().includes(q))
      )
    : index.modules;

  const isActive = (page: PageRef) => {
    if (page.kind !== current.kind) return false;
    if (page.kind === 'module' && current.kind === 'module') return page.name === current.name;
    if (page.kind === 'class' && current.kind === 'class') return page.name === current.name;
    return true;
  };

  return (
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-logo">◈</span>
        <span class="sidebar-title">{index.projectName || 'Blueprint'}</span>
      </div>

      <div class="sidebar-search">
        <input
          type="text"
          placeholder="Search…"
          value={search}
          onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
        />
      </div>

      <nav class="sidebar-nav">
        <button
          class={`nav-item nav-overview ${isActive({ kind: 'system' }) ? 'active' : ''}`}
          onClick={() => onNavigate({ kind: 'system' })}
        >
          <span class="nav-icon">⬡</span> Overview
        </button>

        <div class="nav-section-label">Modules</div>
        {filteredModules.map(mod => {
          const expanded = expandedModules.has(mod.name) || q.length > 0;
          const modActive = isActive({ kind: 'module', name: mod.name });
          const matchingClasses = q
            ? mod.classNames.filter(c => c.toLowerCase().includes(q))
            : mod.classNames;

          return (
            <div key={mod.name} class="nav-module">
              <button
                class={`nav-item nav-module-header ${modActive ? 'active' : ''}`}
                onClick={() => {
                  toggleModule(mod.name);
                  onNavigate({ kind: 'module', name: mod.name });
                }}
              >
                <span class="nav-chevron">{expanded ? '▾' : '▸'}</span>
                <span class="nav-icon">▦</span>
                <span class="nav-label">{mod.name}</span>
                <span class="nav-badge">{mod.classNames.length}</span>
              </button>

              {expanded && (
                <div class="nav-classes">
                  {matchingClasses.map(cls => (
                    <button
                      key={cls}
                      class={`nav-item nav-class ${isActive({ kind: 'class', name: cls }) ? 'active' : ''}`}
                      onClick={() => onNavigate({ kind: 'class', name: cls })}
                    >
                      <span class="nav-icon">◻</span>
                      <span class="nav-label">{cls}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {/* Unmodule-assigned classes */}
        {(() => {
          const assigned = new Set(index.modules.flatMap(m => m.classNames));
          const loose = index.classes.filter(c => !assigned.has(c.className));
          if (!loose.length) return null;
          const filtered = q ? loose.filter(c => c.className.toLowerCase().includes(q)) : loose;
          if (!filtered.length) return null;
          return (
            <div class="nav-module">
              <div class="nav-section-label" style={{ marginTop: 8 }}>Other</div>
              {filtered.map(c => (
                <button
                  key={c.className}
                  class={`nav-item nav-class ${isActive({ kind: 'class', name: c.className }) ? 'active' : ''}`}
                  onClick={() => onNavigate({ kind: 'class', name: c.className })}
                >
                  <span class="nav-icon">◻</span>
                  <span class="nav-label">{c.className}</span>
                </button>
              ))}
            </div>
          );
        })()}
      </nav>
    </aside>
  );
}
