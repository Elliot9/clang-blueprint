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

// Message from extension host → wiki webview
export type HostMessage =
  | { type: 'load'; index: BlueprintIndex }
  | { type: 'navigate'; page: PageRef };

// Message from wiki webview → extension host
export type WikiMessage =
  | { type: 'ready' }
  | { type: 'jumpToSource'; file: string; line: number };

export type PageRef =
  | { kind: 'system' }
  | { kind: 'module'; name: string }
  | { kind: 'class'; name: string };
