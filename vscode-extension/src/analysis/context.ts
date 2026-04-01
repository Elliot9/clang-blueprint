/**
 * analysis/context.ts — Context assembly for IAnalysisProvider calls.
 *
 * Pure functions only. No vscode imports, no async, no side effects.
 * Each Mode Controller calls the appropriate function before invoking a provider.
 *
 * Rule: these functions select a *subset* of ClassEntry[] to pass as `context`.
 * The provider uses this context to bound its analysis to what's relevant,
 * reducing token usage for ClaudeAnalysisProvider and noise for LocalAnalysisProvider.
 */

import type { ClassEntry } from '../shared/types';

// ---------------------------------------------------------------------------
// Explore Mode
// ---------------------------------------------------------------------------

/**
 * Return all classes belonging to `namespace`.
 * If namespace is empty string, return the entire list (global namespace / all).
 * Matching is prefix-based: "core" matches "core", "core::io", "core::net::Foo".
 */
export function buildExploreContext(namespace: string, all: ClassEntry[]): ClassEntry[] {
  if (!namespace) { return all; }
  return all.filter(e => {
    const ns = e.namespace ?? '';
    return ns === namespace || ns.startsWith(namespace + '::');
  });
}

// ---------------------------------------------------------------------------
// Trace Mode
// ---------------------------------------------------------------------------

/**
 * Return the N-hop neighbourhood of `focalClassName` via BFS over dependencies.
 * hops=1: focal + direct deps + direct dependents (via reverseDeps lookup)
 * hops=2: one level further, etc.
 *
 * `reverseDeps` is the precomputed map from blueprint_graph.json.
 * If not available, pass an empty object — the BFS still works forward.
 */
export function buildTraceContext(
  focalClassName: string,
  hops: number,
  all: ClassEntry[],
  reverseDeps: Record<string, string[]> = {},
): ClassEntry[] {
  const visited = new Set<string>([focalClassName]);
  let frontier = new Set<string>([focalClassName]);

  for (let h = 0; h < hops; h++) {
    const next = new Set<string>();

    for (const name of frontier) {
      const entry = all.find(e => e.className === name);

      // Forward deps
      if (entry) {
        for (const dep of entry.dependencies) {
          if (!visited.has(dep.target)) {
            visited.add(dep.target);
            next.add(dep.target);
          }
        }
        // Base classes
        for (const base of entry.baseClasses) {
          if (!visited.has(base)) {
            visited.add(base);
            next.add(base);
          }
        }
      }

      // Reverse deps (classes that depend on `name`)
      for (const dependent of (reverseDeps[name] ?? [])) {
        if (!visited.has(dependent)) {
          visited.add(dependent);
          next.add(dependent);
        }
      }
    }

    frontier = next;
    if (frontier.size === 0) { break; }
  }

  return all.filter(e => visited.has(e.className));
}

/**
 * Compute the direct and indirect impact set of changing `className`.
 * Returns { direct: string[], indirect: string[] }.
 * Requires `reverseDeps` from blueprint_graph.json for efficiency.
 */
export function computeImpact(
  className: string,
  reverseDeps: Record<string, string[]>,
): { direct: string[]; indirect: string[] } {
  const direct = [...(reverseDeps[className] ?? [])];
  const visited = new Set<string>([className, ...direct]);
  const indirect: string[] = [];

  let frontier = new Set<string>(direct);
  while (frontier.size > 0) {
    const next = new Set<string>();
    for (const name of frontier) {
      for (const dep of (reverseDeps[name] ?? [])) {
        if (!visited.has(dep)) {
          visited.add(dep);
          next.add(dep);
          indirect.push(dep);
        }
      }
    }
    frontier = next;
  }

  return { direct, indirect };
}

// ---------------------------------------------------------------------------
// Chat Mode
// ---------------------------------------------------------------------------

/**
 * Return the classes explicitly chosen by the user for the chat context,
 * plus a single hop of their direct dependencies to give the AI structural
 * awareness without overwhelming it with unrelated classes.
 */
export function buildChatContext(selectedClassNames: string[], all: ClassEntry[]): ClassEntry[] {
  const selected = new Set(selectedClassNames);

  // Include selected classes
  const result = all.filter(e => selected.has(e.className));

  // Include their direct deps (not already selected) for structural context
  const extraNames = new Set<string>();
  for (const entry of result) {
    for (const dep of entry.dependencies) {
      if (!selected.has(dep.target)) {
        extraNames.add(dep.target);
      }
    }
  }

  const extras = all.filter(e => extraNames.has(e.className));
  return [...result, ...extras];
}
