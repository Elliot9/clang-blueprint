/**
 * analysis/callerIndex.ts — M28-01/02
 *
 * Builds a reverse index from callSequence data so we can answer:
 * "Which methods call ClassName::methodName?"
 *
 * The scanner produces per-method callSequence (forward direction).
 * This module inverts that into a caller lookup (reverse direction).
 */

import type { ClassEntry, CallStep } from '../shared/types';

// ---------------------------------------------------------------------------
// Caller index (M28-01)
// ---------------------------------------------------------------------------

export interface CallerRef {
  /** Class that contains the calling method */
  callerClass: string;
  /** Signature of the calling method */
  callerMethod: string;
  /** Line number of the call site (if available) */
  lineNumber?: number;
  /** File location of the caller class */
  fileLocation?: string;
}

/**
 * Build a reverse index: for every (targetClass, member) pair found in any
 * callSequence, record who calls it.
 *
 * Key format: "ClassName::methodName" (short names, not full signatures).
 * _self_ references are resolved back to the owning class name.
 */
export function buildCallerIndex(entries: ClassEntry[]): Map<string, CallerRef[]> {
  const index = new Map<string, CallerRef[]>();

  for (const entry of entries) {
    const allMethods = [
      ...(entry.interfaceMeta ?? []),
      ...(entry.privateMethods ?? []),
    ];

    for (const method of allMethods) {
      if (!method.callSequence || method.callSequence.length === 0) { continue; }

      for (const step of method.callSequence) {
        if (step.targetClass === '_meta_') { continue; }
        if (step.kind === 'field') { continue; } // only track call references

        const targetClass = step.targetClass === '_self_'
          ? entry.className.split('::').pop() ?? entry.className
          : step.targetClass;

        const key = `${targetClass}::${step.member}`;

        let refs = index.get(key);
        if (!refs) {
          refs = [];
          index.set(key, refs);
        }

        refs.push({
          callerClass: entry.className,
          callerMethod: method.signature,
          lineNumber: step.lineNumber,
          fileLocation: entry.fileLocation,
        });
      }
    }
  }

  return index;
}

// ---------------------------------------------------------------------------
// Caller tree (M28-02)
// ---------------------------------------------------------------------------

export interface CallerTreeNode {
  /** Class that calls the target */
  className: string;
  /** Method signature of the caller */
  method: string;
  /** Line number of the call site */
  lineNumber?: number;
  /** File location of the caller */
  fileLocation?: string;
  /** Depth in the tree (0 = direct callers of root) */
  depth: number;
  /** Recursive callers of this caller */
  children: CallerTreeNode[];
  /** True once children have been resolved */
  childrenLoaded: boolean;
}

/**
 * Build a recursive caller tree: starting from targetClass::targetMethod,
 * find all callers, then find callers-of-callers, etc.
 *
 * @param targetClass   - The class containing the method we're looking up
 * @param targetMethod  - The method name (short name, not full signature)
 * @param entries       - All ClassEntry data
 * @param maxDepth      - Maximum recursion depth (default 6)
 * @returns A virtual root node whose children are the direct callers
 */
export function buildCallerTree(
  targetClass: string,
  targetMethod: string,
  entries: ClassEntry[],
  maxDepth: number = 6,
): CallerTreeNode {
  const callerIndex = buildCallerIndex(entries);
  const visited = new Set<string>();

  // Also try short name for lookup since callerIndex keys use short names
  const shortClass = targetClass.split('::').pop() ?? targetClass;

  function buildChildren(className: string, methodName: string, depth: number): CallerTreeNode[] {
    if (depth >= maxDepth) { return []; }

    // Try both qualified and short class name
    const key1 = `${className}::${methodName}`;
    const key2 = `${shortClass === className ? '' : ''}${className.split('::').pop() ?? className}::${methodName}`;

    const refs = callerIndex.get(key1) ?? callerIndex.get(key2) ?? [];

    const children: CallerTreeNode[] = [];
    for (const ref of refs) {
      // Extract short method name from signature for recursion
      const nameMatch = ref.callerMethod.match(/\b([a-zA-Z_~]\w*)\s*\(/);
      const callerMethodName = nameMatch ? nameMatch[1] : ref.callerMethod;

      const visitKey = `${ref.callerClass}::${callerMethodName}`;
      if (visited.has(visitKey)) {
        // Cycle — add as leaf without expanding
        children.push({
          className: ref.callerClass,
          method: ref.callerMethod,
          lineNumber: ref.lineNumber,
          fileLocation: ref.fileLocation,
          depth,
          children: [],
          childrenLoaded: true,
        });
        continue;
      }

      visited.add(visitKey);

      const grandChildren = buildChildren(ref.callerClass, callerMethodName, depth + 1);

      children.push({
        className: ref.callerClass,
        method: ref.callerMethod,
        lineNumber: ref.lineNumber,
        fileLocation: ref.fileLocation,
        depth,
        children: grandChildren,
        childrenLoaded: true,
      });

      visited.delete(visitKey);
    }

    return children;
  }

  // Root node represents the target method itself
  const root: CallerTreeNode = {
    className: targetClass,
    method: targetMethod,
    depth: 0,
    children: buildChildren(targetClass, targetMethod, 0),
    childrenLoaded: true,
  };

  return root;
}
