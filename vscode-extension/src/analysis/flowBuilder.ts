/**
 * analysis/flowBuilder.ts — M25-01 / M25-02: Cross-class call chain assembly.
 *
 * Builds Flow objects by following callSequence data across class boundaries.
 * Used by Trace Mode flow query and Module Overview flow overlay.
 */

import type { ClassEntry, ModuleEntry } from '../shared/types';

export interface FlowStep {
  className: string;
  method: string;
  module: string;
  action: 'call' | 'read' | 'write';
}

export interface Flow {
  name: string;
  steps: FlowStep[];
  crossedModules: string[];
}

/**
 * Build a flow starting from a specific class + method by following callSequence.
 */
export function buildFlow(
  startClass: string,
  startMethod: string,
  entries: ClassEntry[],
  classToModule: Record<string, string>,
  maxDepth = 10,
): Flow | null {
  const entryMap = new Map(entries.map(e => [e.className, e]));
  const steps: FlowStep[] = [];
  const visited = new Set<string>();

  function walk(className: string, methodName: string, depth: number): void {
    if (depth > maxDepth) { return; }
    const key = `${className}::${methodName}`;
    if (visited.has(key)) { return; }
    visited.add(key);

    const entry = entryMap.get(className);
    if (!entry) { return; }

    steps.push({
      className,
      method: methodName,
      module: classToModule[className] ?? '_ungrouped',
      action: 'call',
    });

    // Find callSequence for this method
    const allMethods = [
      ...(entry.interfaceMeta ?? []),
      ...(entry.privateMethods ?? []),
    ];
    const meta = allMethods.find(m => m.signature?.includes(methodName + '('));
    if (!meta?.callSequence) { return; }

    for (const step of meta.callSequence) {
      if (step.targetClass === '_self_') {
        steps.push({
          className,
          method: step.member,
          module: classToModule[className] ?? '_ungrouped',
          action: step.isWrite ? 'write' : step.kind === 'call' ? 'call' : 'read',
        });
      } else if (step.kind === 'call') {
        walk(step.targetClass, step.member, depth + 1);
      } else {
        steps.push({
          className: step.targetClass,
          method: step.member,
          module: classToModule[step.targetClass] ?? '_ungrouped',
          action: step.isWrite ? 'write' : 'read',
        });
      }
    }
  }

  walk(startClass, startMethod, 0);

  if (steps.length < 2) { return null; }

  const modules = [...new Set(steps.map(s => s.module))];
  const lastName = steps[steps.length - 1];
  return {
    name: `${startClass}::${startMethod} → ${lastName.className}::${lastName.method}`,
    steps,
    crossedModules: modules,
  };
}

/**
 * Auto-discover key flows by starting from entry point public methods.
 * Returns top flows sorted by length and cross-module count.
 */
export function discoverKeyFlows(
  entries: ClassEntry[],
  entryPoints: Array<{ className: string; kind: string }>,
  modules: ModuleEntry[],
  limit = 10,
): Flow[] {
  const classToModule: Record<string, string> = {};
  for (const m of modules) {
    for (const cn of m.classNames) { classToModule[cn] = m.name; }
  }

  const entryMap = new Map(entries.map(e => [e.className, e]));
  const flows: Flow[] = [];

  // Start from entry points (main and hub kinds first)
  const orderedEps = [...entryPoints].sort((a, b) => {
    const order: Record<string, number> = { main: 0, hub: 1, server: 2, root: 3 };
    return (order[a.kind] ?? 4) - (order[b.kind] ?? 4);
  });

  for (const ep of orderedEps.slice(0, 20)) {
    const entry = entryMap.get(ep.className);
    if (!entry) { continue; }

    // Try each public method
    for (const sig of entry.interfaces.slice(0, 5)) {
      const match = sig.match(/\b([a-zA-Z_]\w*)\s*\(/);
      if (!match) { continue; }
      const methodName = match[1];
      const flow = buildFlow(ep.className, methodName, entries, classToModule);
      if (flow && flow.steps.length >= 3) {
        flows.push(flow);
      }
    }
  }

  // Sort by (crossedModules desc, steps desc), deduplicate similar flows
  flows.sort((a, b) => {
    if (b.crossedModules.length !== a.crossedModules.length) {
      return b.crossedModules.length - a.crossedModules.length;
    }
    return b.steps.length - a.steps.length;
  });

  // Deduplicate flows that share >80% of the same steps
  const unique: Flow[] = [];
  for (const flow of flows) {
    const stepKeys = new Set(flow.steps.map(s => `${s.className}::${s.method}`));
    const isDuplicate = unique.some(u => {
      const uKeys = new Set(u.steps.map(s => `${s.className}::${s.method}`));
      const overlap = [...stepKeys].filter(k => uKeys.has(k)).length;
      return overlap / Math.max(stepKeys.size, uKeys.size) > 0.8;
    });
    if (!isDuplicate) { unique.push(flow); }
    if (unique.length >= limit) { break; }
  }

  return unique;
}
