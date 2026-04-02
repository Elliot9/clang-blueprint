/**
 * ai/LocalAnalysisProvider.ts — P15-01.
 *
 * Implements IAnalysisProvider using heuristics + TF-IDF-style keyword matching.
 * No API key required. All methods are synchronously derived from ClassEntry data.
 */

import type {
  IAnalysisProvider,
  ClassEntry,
  CallStep,
  ChatMessage,
  AnalysisSummary,
  RelevanceMatch,
} from '../shared/types';

// ---------------------------------------------------------------------------
// Method name heuristics
// ---------------------------------------------------------------------------

/** Patterns that reveal a class's primary role, checked in order. */
const ROLE_PATTERNS: Array<{ prefixes: string[]; role: string }> = [
  { prefixes: ['parse', 'decode', 'deserialize', 'tokenize', 'lex'],  role: 'Parser / Decoder' },
  { prefixes: ['encode', 'serialize', 'format', 'render'],             role: 'Serializer / Formatter' },
  { prefixes: ['connect', 'listen', 'accept', 'send', 'recv', 'read', 'write', 'fetch'],
                                                                        role: 'I/O Handler' },
  { prefixes: ['handle', 'on', 'dispatch', 'notify', 'emit', 'trigger'], role: 'Event Handler' },
  { prefixes: ['create', 'build', 'make', 'spawn', 'allocate'],        role: 'Factory / Builder' },
  { prefixes: ['destroy', 'close', 'shutdown', 'cleanup', 'free', 'release'], role: 'Lifecycle Manager' },
  { prefixes: ['schedule', 'run', 'execute', 'submit', 'enqueue'],     role: 'Executor / Scheduler' },
  { prefixes: ['get', 'set', 'fetch', 'load', 'store', 'update'],      role: 'Data Accessor' },
  { prefixes: ['validate', 'check', 'verify', 'assert'],               role: 'Validator' },
  { prefixes: ['log', 'trace', 'record', 'report', 'audit'],           role: 'Logger / Monitor' },
];

function _methodRole(methods: string[]): string | undefined {
  const names = methods.map(m => {
    // Strip return type / params from signature, keep method name only
    const match = m.match(/\b([a-z_]\w*)\s*\(/i);
    return match?.[1]?.toLowerCase() ?? '';
  });

  for (const { prefixes, role } of ROLE_PATTERNS) {
    const hits = names.filter(n => prefixes.some(p => n.startsWith(p)));
    if (hits.length >= Math.min(2, Math.ceil(names.length * 0.25))) {
      return role;
    }
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Intent inference
// ---------------------------------------------------------------------------

function _inferIntent(entry: ClassEntry): string {
  const cls = entry.className;
  const responsibility = entry.responsibility;

  // If responsibility label is already meaningful (not generic), use it
  if (responsibility && responsibility !== 'Unknown' && responsibility !== '') {
    const privSigs = (entry.privateMethods ?? []).map(m => m.signature);
    const role = _methodRole([...entry.interfaces, ...privSigs]);
    const deps = entry.dependencies.filter(d => d.type === 'composition').map(d => d.target);
    if (deps.length > 0) {
      return `${responsibility} — manages ${deps.slice(0, 3).join(', ')}`;
    }
    return responsibility;
  }

  // Fall back to method-name heuristic
  const privSigs = (entry.privateMethods ?? []).map(m => m.signature);
  const allMethods = [...entry.interfaces, ...privSigs];
  const role = _methodRole(allMethods);
  if (role) {
    return `${cls} — ${role}`;
  }

  // Last resort: structural inference
  const compositions = entry.dependencies.filter(d => d.type === 'composition');
  if (compositions.length >= 3) {
    return `${cls} — coordinates ${compositions.length} subsystems`;
  }
  if (entry.baseClasses.length > 0) {
    return `${cls} — extends ${entry.baseClasses[0]}`;
  }

  return cls;
}

// ---------------------------------------------------------------------------
// Responsibilities extraction
// ---------------------------------------------------------------------------

function _inferResponsibilities(entry: ClassEntry): string[] {
  const resp: string[] = [];

  // Public methods (up to 6) — each is a responsibility
  const publicMethods = entry.interfaces.slice(0, 6);
  for (const m of publicMethods) {
    // Clean up signature to just the name + short desc
    const match = m.match(/(\w+)\s*\(([^)]{0,60})/);
    if (match) {
      resp.push(`${match[1]}(${match[2].length < 50 ? match[2] : match[2].slice(0, 50) + '…'})`);
    }
  }
  if (entry.interfaces.length > 6) {
    resp.push(`… and ${entry.interfaces.length - 6} more methods`);
  }

  return resp;
}

// ---------------------------------------------------------------------------
// TF-IDF-style relevance scoring
// ---------------------------------------------------------------------------

/** Expand CamelCase → tokens ("DiskManager" → ["Disk", "Manager", "diskmanager"]) */
function _tokenize(text: string): string[] {
  const words = text
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .split(/[\s_:,.()\[\]<>]+/)
    .filter(w => w.length > 1)
    .map(w => w.toLowerCase());
  return [...new Set(words)];
}

function _entryTokens(entry: ClassEntry): string[] {
  return [
    ...(_tokenize(entry.className)),
    ...(_tokenize(entry.namespace ?? '')),
    ...(_tokenize(entry.responsibility ?? '')),
    ...(entry.interfaces.flatMap(i => _tokenize(i))),
    ...(entry.dependencies.map(d => d.target.toLowerCase())),
  ];
}

// ---------------------------------------------------------------------------
// IAnalysisProvider implementation
// ---------------------------------------------------------------------------

export class LocalAnalysisProvider implements IAnalysisProvider {
  readonly providerId = 'local' as const;

  async isAvailable(): Promise<boolean> {
    return true;
  }

  async summarize(entry: ClassEntry, context?: ClassEntry[]): Promise<AnalysisSummary> {
    const intent = _inferIntent(entry);
    const responsibilities = _inferResponsibilities(entry);

    // usedBy: who in context depends on this class
    const usedBy = (context ?? [])
      .filter(e => e.className !== entry.className &&
        e.dependencies.some(d => d.target === entry.className))
      .map(e => e.className)
      .slice(0, 5);

    const dependsOn = entry.dependencies
      .map(d => d.target)
      .slice(0, 5);

    return { intent, responsibilities, usedBy, dependsOn };
  }

  async findRelevant(query: string, all: ClassEntry[]): Promise<RelevanceMatch[]> {
    const queryTokens = _tokenize(query);
    if (queryTokens.length === 0) { return []; }

    return all
      .map(entry => {
        const entryTokens = _entryTokens(entry);
        const matched = queryTokens.filter(qt => entryTokens.some(et => et.includes(qt) || qt.includes(et)));
        const score = matched.length / queryTokens.length;
        return { entry, score, matchedTerms: matched };
      })
      .filter(r => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 20);
  }

  async explainChain(steps: CallStep[], _context: ClassEntry[]): Promise<string> {
    if (steps.length === 0) { return 'No call chain recorded for this method.'; }
    const parts = steps.map(s => {
      if (s.targetClass === '_self_') {
        return s.isWrite
          ? `writes field \`${s.member}\``
          : `reads field \`${s.member}\``;
      }
      return s.kind === 'call'
        ? `calls \`${s.targetClass}::${s.member}\``
        : (s.isWrite
          ? `writes \`${s.targetClass}::${s.member}\``
          : `reads \`${s.targetClass}::${s.member}\``);
    });
    return parts.join(' → ');
  }

  async locateAnchor(errorLog: string, all: ClassEntry[]): Promise<ClassEntry[]> {
    // Extract identifier-like tokens from the error log (min 4 chars)
    const words = [...new Set(
      errorLog.split(/[^a-zA-Z0-9_:]+/).filter(w => w.length >= 4),
    )];

    return all
      .filter(e => words.some(w =>
        e.className.includes(w) ||
        w.includes(e.className) ||
        (e.namespace && e.namespace.includes(w)),
      ))
      .slice(0, 10);
  }

  async chat(
    _messages: ChatMessage[],
    _context: ClassEntry[],
    onChunk: (chunk: string) => void,
  ): Promise<void> {
    onChunk(
      'Local analysis mode is active. To enable AI-powered chat, ' +
      'set `clangBlueprint.analysisProvider` to `"claude"` or `"gemini"` ' +
      'and add the corresponding API key in settings.',
    );
  }
}
