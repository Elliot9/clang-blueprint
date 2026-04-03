/**
 * analysis/exploreAdvisor.ts — M24-01: Exploration Suggestion Engine.
 *
 * Pure-function module. Given currently visible classes, history, and module
 * context, suggests the next 1-3 classes worth exploring.
 *
 * Strategies:
 *   hub        — high in-degree class not yet expanded
 *   boundary   — class connecting current module to another
 *   unexplored — strong dependency target not yet on canvas
 *   flow-next  — next step in a call chain the user was viewing
 */

import type { ClassEntry, ModuleEntry } from '../shared/types';

export interface ExplorationSuggestion {
  targetClass: string;
  reason: string;
  priority: 'high' | 'medium';
  kind: 'hub' | 'boundary' | 'unexplored' | 'flow-next';
}

export interface AdvisorInput {
  visibleClasses: ClassEntry[];
  allEntries: ClassEntry[];
  expandedClasses: Set<string>;
  modules: ModuleEntry[];
  reverseDeps: Record<string, string[]>;
}

/**
 * Produce up to `limit` exploration suggestions.
 */
export function suggestNextExploration(
  input: AdvisorInput,
  limit = 3,
): ExplorationSuggestion[] {
  const { visibleClasses, allEntries, expandedClasses, modules, reverseDeps } = input;
  const visibleSet = new Set(visibleClasses.map(c => c.className));
  const allMap = new Map(allEntries.map(e => [e.className, e]));
  const results: ExplorationSuggestion[] = [];
  const seen = new Set<string>();

  // Determine which module the majority of visible classes belong to
  const modLookup: Record<string, string> = {};
  for (const m of modules) {
    for (const cn of m.classNames) { modLookup[cn] = m.name; }
  }
  const visibleModCounts: Record<string, number> = {};
  for (const c of visibleClasses) {
    const m = modLookup[c.className] ?? '_ungrouped';
    visibleModCounts[m] = (visibleModCounts[m] ?? 0) + 1;
  }
  const primaryModule = Object.entries(visibleModCounts)
    .sort((a, b) => b[1] - a[1])[0]?.[0];

  // --- Strategy 1: Hub (high in-degree, visible but not expanded) ---
  const hubCandidates: Array<{ cn: string; deg: number }> = [];
  for (const c of visibleClasses) {
    if (expandedClasses.has(c.className)) { continue; }
    const deg = (reverseDeps[c.className] ?? []).length;
    if (deg >= 2) { hubCandidates.push({ cn: c.className, deg }); }
  }
  hubCandidates.sort((a, b) => b.deg - a.deg);
  for (const { cn, deg } of hubCandidates.slice(0, 2)) {
    if (seen.has(cn)) { continue; }
    results.push({
      targetClass: cn,
      reason: `${cn} is used by ${deg} classes — central hub`,
      priority: 'high',
      kind: 'hub',
    });
    seen.add(cn);
  }

  // --- Strategy 2: Boundary (visible class with deps in another module) ---
  for (const c of visibleClasses) {
    if (seen.has(c.className)) { continue; }
    const cMod = modLookup[c.className];
    for (const dep of c.dependencies) {
      const depMod = modLookup[dep.target];
      if (depMod && depMod !== cMod && !visibleSet.has(dep.target) && allMap.has(dep.target)) {
        results.push({
          targetClass: dep.target,
          reason: `${dep.target} (module ${depMod}) — boundary from ${c.className}`,
          priority: 'medium',
          kind: 'boundary',
        });
        seen.add(dep.target);
        break;
      }
    }
    if (results.length >= limit) { break; }
  }

  // --- Strategy 3: Unexplored (strong dep target not on canvas) ---
  const depTargetCount: Record<string, number> = {};
  for (const c of visibleClasses) {
    for (const d of c.dependencies) {
      if (!visibleSet.has(d.target) && allMap.has(d.target)) {
        depTargetCount[d.target] = (depTargetCount[d.target] ?? 0) + 1;
      }
    }
  }
  const unexplored = Object.entries(depTargetCount)
    .filter(([cn]) => !seen.has(cn))
    .sort((a, b) => b[1] - a[1]);
  for (const [cn, count] of unexplored.slice(0, 2)) {
    results.push({
      targetClass: cn,
      reason: `${cn} — referenced by ${count} visible classes but not shown`,
      priority: 'medium',
      kind: 'unexplored',
    });
    seen.add(cn);
  }

  return results.slice(0, limit);
}
