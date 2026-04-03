/**
 * analysis/explorationPath.ts — M24-05: Suggested Exploration Path.
 *
 * Given entry points and module edges, auto-generates a recommended path
 * through 3-5 modules following the heaviest dependency edges.
 */

import type { ModuleEntry, ModuleEdge, EntryPoint } from '../shared/types';

export interface ExplorationStep {
  moduleName: string;
  className: string;
  reason: string;
}

export interface ExplorationPath {
  steps: ExplorationStep[];
}

/**
 * Generate a suggested exploration path starting from the best entry point
 * and walking along the heaviest module edges.
 */
export function generateExplorationPath(
  modules: ModuleEntry[],
  moduleEdges: ModuleEdge[],
  entryPoints: EntryPoint[],
  maxSteps = 5,
): ExplorationPath | null {
  if (modules.length === 0) { return null; }

  const moduleMap = new Map(modules.map(m => [m.name, m]));

  // Build adjacency: source → [{target, weight}] sorted by weight desc
  const adj: Record<string, Array<{ target: string; weight: number }>> = {};
  for (const e of moduleEdges) {
    if (!adj[e.source]) { adj[e.source] = []; }
    adj[e.source].push({ target: e.target, weight: e.weight });
  }
  for (const key of Object.keys(adj)) {
    adj[key].sort((a, b) => b.weight - a.weight);
  }

  // Pick starting module: prefer module containing a 'main' or 'hub' entry point
  let startModule: string | undefined;
  let startClass: string | undefined;
  let startReason = 'entry point';

  const epOrder: EntryPoint['kind'][] = ['main', 'hub', 'server', 'root'];
  for (const kind of epOrder) {
    const ep = entryPoints.find(e => e.kind === kind);
    if (ep) {
      // Find which module contains this entry point
      for (const m of modules) {
        if (m.classNames.includes(ep.className)) {
          startModule = m.name;
          startClass = ep.className;
          startReason = `${ep.kind} entry point`;
          break;
        }
      }
      if (startModule) { break; }
    }
  }

  // Fallback: largest module
  if (!startModule) {
    const largest = [...modules].sort((a, b) => b.classNames.length - a.classNames.length)[0];
    startModule = largest.name;
    startClass = largest.classNames[0] ?? largest.name;
    startReason = 'largest module';
  }

  // Walk along heaviest edges
  const steps: ExplorationStep[] = [];
  const visited = new Set<string>();

  let current = startModule;
  steps.push({
    moduleName: current,
    className: startClass!,
    reason: startReason,
  });
  visited.add(current);

  while (steps.length < maxSteps) {
    const neighbors = adj[current] ?? [];
    const next = neighbors.find(n => !visited.has(n.target) && moduleMap.has(n.target));
    if (!next) { break; }

    visited.add(next.target);
    const mod = moduleMap.get(next.target)!;

    // Pick representative class: prefer entry point in this module, else first class
    let repClass = mod.classNames[0] ?? mod.name;
    const epInMod = entryPoints.find(ep => mod.classNames.includes(ep.className));
    if (epInMod) { repClass = epInMod.className; }

    steps.push({
      moduleName: next.target,
      className: repClass,
      reason: `${next.weight} connections from ${current}`,
    });
    current = next.target;
  }

  if (steps.length < 2) { return null; }
  return { steps };
}
