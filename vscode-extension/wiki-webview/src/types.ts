/** Mirrors shared/types.ts — duplicated to avoid circular build dependency with the extension host. */

export interface Dependency {
  target: string;
  type: string;
  cardinality?: string;
}

export interface ClassEntry {
  className: string;
  responsibility: string;
  namespace: string;
  fileLocation: string;
  lineNumber: number;
  baseClasses: string[];
  templateParams: string[];
  dependencies: Dependency[];
  attributes?: string[];
  interfaces: string[];
  // semantic enrichment
  intent?: string;
  designPattern?: string;
  tradeoffs?: string[];
  changeRisk?: 'low' | 'medium' | 'high';
}

export interface ModuleEntry {
  name: string;
  namespace?: string;
  directory?: string;
  classNames: string[];
  summarySeed: string;
  internalEdgeCount: number;
  externalDeps: { target: string; weight: number; depTypes: string[] }[];
  summary?: string;
}

export interface ModuleEdge {
  source: string;
  target: string;
  weight: number;
}

export interface EntryPoint {
  className: string;
  kind: string;
  reason: string;
}

export interface BlueprintIndex {
  version: number;
  projectName?: string;
  projectSummary?: string;
  modules: ModuleEntry[];
  moduleEdges: ModuleEdge[];
  entryPoints: EntryPoint[];
  classes: ClassEntry[];
}

// ---------------------------------------------------------------------------
// Change Report (blueprint_changes.json — Direction B)
// ---------------------------------------------------------------------------

export interface ClassDiff {
  className: string;
  interfaceChanges?: { added: string[]; removed: string[] };
  depChanges?: Array<{
    target: string;
    change: 'added' | 'removed' | 'type_changed';
    type?: string;
    from?: string;
    to?: string;
  }>;
  riskChange?: { from: string; to: string };
  fileLocationChange?: { from: string; to: string };
}

export interface ChangeRecord {
  commit: string;
  author: string;
  email: string;
  date: string;
  message: string;
  indexFile: string;
  added: Array<{ className: string; fileLocation?: string; designPattern?: string; changeRisk?: string }>;
  removed: Array<{ className: string; fileLocation?: string }>;
  modified: ClassDiff[];
  modulesAdded: string[];
  modulesRemoved: string[];
  modulesModified: Array<{ name: string; classesAdded: string[]; classesRemoved: string[] }>;
  impact: { direct: string[]; indirect: string[] };
}

export interface BlueprintChanges {
  version: number;
  records: ChangeRecord[];
}

// ---------------------------------------------------------------------------
// Messaging
// ---------------------------------------------------------------------------

// Message from extension host → wiki webview
export type HostMessage =
  | { type: 'load'; index: BlueprintIndex }
  | { type: 'loadChanges'; changes: BlueprintChanges }
  | { type: 'navigate'; page: PageRef };

// Message from wiki webview → extension host
export type WikiMessage =
  | { type: 'ready' }
  | { type: 'jumpToSource'; file: string; line: number };

export type PageRef =
  | { kind: 'system' }
  | { kind: 'module'; name: string }
  | { kind: 'class'; name: string }
  | { kind: 'changes' };
