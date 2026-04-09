import { h } from 'preact';
import { useState } from 'preact/hooks';
import type { BlueprintChanges, ChangeRecord, ClassDiff, PageRef } from '../types';

interface Props {
  changes: BlueprintChanges;
  onNavigate: (page: PageRef) => void;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function ClassDiffDetail({ diff, onNavigate }: { diff: ClassDiff; onNavigate: (p: PageRef) => void }) {
  return (
    <div class="change-diff-detail">
      {diff.interfaceChanges && (
        <div class="diff-section">
          <span class="diff-label">Interface</span>
          {diff.interfaceChanges.added.map(s => (
            <span key={s} class="diff-chip diff-chip--added">+ {s}</span>
          ))}
          {diff.interfaceChanges.removed.map(s => (
            <span key={s} class="diff-chip diff-chip--removed">− {s}</span>
          ))}
        </div>
      )}
      {diff.depChanges && diff.depChanges.length > 0 && (
        <div class="diff-section">
          <span class="diff-label">Dependencies</span>
          {diff.depChanges.map((d, i) => (
            <span key={i} class={`diff-chip diff-chip--${d.change === 'added' ? 'added' : d.change === 'removed' ? 'removed' : 'changed'}`}>
              {d.change === 'added' && `+ ${d.target} (${d.type})`}
              {d.change === 'removed' && `− ${d.target} (${d.type})`}
              {d.change === 'type_changed' && `~ ${d.target}: ${d.from} → ${d.to}`}
            </span>
          ))}
        </div>
      )}
      {diff.riskChange && (
        <div class="diff-section">
          <span class="diff-label">Risk</span>
          <span class="diff-chip diff-chip--changed">
            {diff.riskChange.from} → {diff.riskChange.to}
          </span>
        </div>
      )}
      {diff.fileLocationChange && (
        <div class="diff-section">
          <span class="diff-label">Moved</span>
          <span class="diff-chip diff-chip--changed" style={{ fontFamily: 'var(--font-mono)' }}>
            {diff.fileLocationChange.from} → {diff.fileLocationChange.to}
          </span>
        </div>
      )}
    </div>
  );
}

function ChangeRecordCard({ record, onNavigate }: { record: ChangeRecord; onNavigate: (p: PageRef) => void }) {
  const [expanded, setExpanded] = useState(false);
  const totalChanges = record.added.length + record.removed.length + record.modified.length;

  return (
    <div class="change-card">
      {/* Header row */}
      <div class="change-card-header" onClick={() => setExpanded(e => !e)}>
        <span class="change-chevron">{expanded ? '▾' : '▸'}</span>
        <div class="change-card-meta">
          <span class="change-commit" title={record.commit}>{record.commit.slice(0, 8)}</span>
          <span class="change-message">{record.message || '(no message)'}</span>
        </div>
        <div class="change-card-badges">
          {record.added.length > 0 && (
            <span class="diff-badge diff-badge--added">+{record.added.length}</span>
          )}
          {record.removed.length > 0 && (
            <span class="diff-badge diff-badge--removed">−{record.removed.length}</span>
          )}
          {record.modified.length > 0 && (
            <span class="diff-badge diff-badge--changed">~{record.modified.length}</span>
          )}
        </div>
        <div class="change-card-author">
          <span class="change-author">{record.author}</span>
          <span class="change-date">{formatDate(record.date)}</span>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div class="change-card-body">

          {/* Added classes */}
          {record.added.length > 0 && (
            <div class="change-section">
              <div class="change-section-title change-section-title--added">
                Added ({record.added.length})
              </div>
              <div class="change-items">
                {record.added.map(c => (
                  <div key={c.className} class="change-item">
                    <button class="link-btn" onClick={() => onNavigate({ kind: 'class', name: c.className })}>
                      {c.className}
                    </button>
                    {c.fileLocation && (
                      <span class="change-item-meta" style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.fileLocation}
                      </span>
                    )}
                    {c.designPattern && <span class="pattern-tag">{c.designPattern}</span>}
                    {c.changeRisk && (
                      <span class={`risk-badge risk-badge--${c.changeRisk}`}>{c.changeRisk}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Removed classes */}
          {record.removed.length > 0 && (
            <div class="change-section">
              <div class="change-section-title change-section-title--removed">
                Removed ({record.removed.length})
              </div>
              <div class="change-items">
                {record.removed.map(c => (
                  <div key={c.className} class="change-item change-item--removed">
                    <span class="change-item-name">{c.className}</span>
                    {c.fileLocation && (
                      <span class="change-item-meta" style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.fileLocation}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Modified classes */}
          {record.modified.length > 0 && (
            <div class="change-section">
              <div class="change-section-title change-section-title--changed">
                Modified ({record.modified.length})
              </div>
              <div class="change-items">
                {record.modified.map(diff => (
                  <div key={diff.className} class="change-item change-item--modified">
                    <button class="link-btn" onClick={() => onNavigate({ kind: 'class', name: diff.className })}>
                      {diff.className}
                    </button>
                    <ClassDiffDetail diff={diff} onNavigate={onNavigate} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Module changes */}
          {(record.modulesAdded.length > 0 || record.modulesRemoved.length > 0 || record.modulesModified.length > 0) && (
            <div class="change-section">
              <div class="change-section-title">Modules</div>
              <div class="change-items">
                {record.modulesAdded.map(n => (
                  <div key={n} class="change-item">
                    <span class="diff-badge diff-badge--added">+</span>
                    <button class="link-btn" onClick={() => onNavigate({ kind: 'module', name: n })}>{n}</button>
                  </div>
                ))}
                {record.modulesRemoved.map(n => (
                  <div key={n} class="change-item change-item--removed">
                    <span class="diff-badge diff-badge--removed">−</span>
                    <span>{n}</span>
                  </div>
                ))}
                {record.modulesModified.map(m => (
                  <div key={m.name} class="change-item">
                    <span class="diff-badge diff-badge--changed">~</span>
                    <button class="link-btn" onClick={() => onNavigate({ kind: 'module', name: m.name })}>{m.name}</button>
                    {m.classesAdded.length > 0 && (
                      <span class="change-item-meta">+{m.classesAdded.join(', ')}</span>
                    )}
                    {m.classesRemoved.length > 0 && (
                      <span class="change-item-meta" style={{ color: 'var(--risk-high)' }}>
                        −{m.classesRemoved.join(', ')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Impact analysis */}
          {(record.impact.direct.length > 0 || record.impact.indirect.length > 0) && (
            <div class="change-section">
              <div class="change-section-title">Impact Analysis</div>
              {record.impact.direct.length > 0 && (
                <div class="change-impact-row">
                  <span class="impact-label">Direct</span>
                  <div class="chip-row">
                    {record.impact.direct.map(n => (
                      <button key={n} class="chip" onClick={() => onNavigate({ kind: 'class', name: n })}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {record.impact.indirect.length > 0 && (
                <div class="change-impact-row">
                  <span class="impact-label impact-label--indirect">Indirect</span>
                  <div class="chip-row">
                    {record.impact.indirect.map(n => (
                      <button key={n} class="chip" onClick={() => onNavigate({ kind: 'class', name: n })}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ChangesPage({ changes, onNavigate }: Props) {
  const records = [...changes.records].reverse(); // newest first
  const totalAdded    = records.reduce((n, r) => n + r.added.length, 0);
  const totalRemoved  = records.reduce((n, r) => n + r.removed.length, 0);
  const totalModified = records.reduce((n, r) => n + r.modified.length, 0);

  return (
    <main class="page">
      <header class="page-header">
        <h1 class="page-title">Change Report</h1>
        <div class="page-subtitle">
          Architectural diff history — {records.length} {records.length === 1 ? 'commit' : 'commits'} recorded
        </div>
      </header>

      <section class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{records.length}</div>
          <div class="stat-label">Commits</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style={{ color: '#4ec9b0' }}>{totalAdded}</div>
          <div class="stat-label">Classes added</div>
        </div>
        <div class="stat-card stat-card--risk">
          <div class="stat-value">{totalRemoved}</div>
          <div class="stat-label">Classes removed</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{totalModified}</div>
          <div class="stat-label">Classes modified</div>
        </div>
      </section>

      {records.length === 0 ? (
        <div class="page-section">
          <p style={{ color: 'var(--fg-muted)', fontSize: '13px' }}>
            No change records yet. Run <code>blueprint diff</code> after committing to generate history.
          </p>
        </div>
      ) : (
        <section class="page-section">
          <h2>History</h2>
          <div class="change-list">
            {records.map(r => (
              <ChangeRecordCard key={r.commit + r.date} record={r} onNavigate={onNavigate} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
