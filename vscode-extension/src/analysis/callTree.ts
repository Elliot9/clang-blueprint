/**
 * analysis/callTree.ts — M27-06
 *
 * Builds a recursive call tree from flat per-method callSequence data.
 * The scanner produces single-depth callSequence per method; this module
 * stitches them together into a multi-level tree at runtime.
 */

import type { ClassEntry, CallStep } from '../shared/types';

export interface CallTreeNode {
  className: string;
  method: string;
  kind: 'call' | 'field';
  isWrite?: boolean;
  isConstructor?: boolean;
  lineNumber?: number;
  annotation?: string;
  depth: number;
  children: CallTreeNode[];
  childrenLoaded: boolean;
  fileLocation?: string;
}

/**
 * Build a recursive call tree starting from rootClass::rootMethod.
 *
 * @param rootClass   - The class name containing the root method
 * @param rootMethod  - The method name (short name, not full signature)
 * @param entries     - All ClassEntry data (from blueprint_index.json)
 * @param maxDepth    - Maximum recursion depth (default 10)
 * @returns Root CallTreeNode with children populated recursively
 */
export function buildCallTree(
  rootClass: string,
  rootMethod: string,
  entries: ClassEntry[],
  maxDepth: number = 10,
): CallTreeNode {
  // Build lookup maps
  const entryMap = new Map<string, ClassEntry>();
  for (const e of entries) {
    entryMap.set(e.className, e);
    // Also index by short name for matching
    const short = e.className.split('::').pop() ?? e.className;
    if (!entryMap.has(short)) {
      entryMap.set(short, e);
    }
  }

  const visited = new Set<string>();

  function findCallSequence(className: string, methodName: string): CallStep[] | null {
    const entry = entryMap.get(className);
    if (!entry) { return null; }

    // Search in interfaceMeta (public methods)
    if (entry.interfaceMeta) {
      for (const m of entry.interfaceMeta) {
        if (matchesMethod(m.signature, methodName)) {
          return m.callSequence ?? [];
        }
      }
    }
    // Search in privateMethods
    if (entry.privateMethods) {
      for (const m of entry.privateMethods) {
        if (matchesMethod(m.signature, methodName)) {
          return m.callSequence ?? [];
        }
      }
    }
    return null;
  }

  function matchesMethod(signature: string, methodName: string): boolean {
    if (!signature) { return false; }
    // Match "void foo(int)" against "foo", or exact match
    const nameMatch = signature.match(/\b([a-zA-Z_~]\w*)\s*\(/);
    if (nameMatch && nameMatch[1] === methodName) { return true; }
    return signature === methodName;
  }

  function buildNode(
    className: string,
    method: string,
    step: CallStep | null,
    depth: number,
  ): CallTreeNode {
    const entry = entryMap.get(className);
    const node: CallTreeNode = {
      className,
      method,
      kind: step?.kind ?? 'call',
      isWrite: step?.isWrite,
      isConstructor: step?.isConstructor,
      lineNumber: step?.lineNumber,
      annotation: step?.annotation,
      depth,
      children: [],
      childrenLoaded: false,
      fileLocation: entry?.fileLocation,
    };

    // Cycle detection
    const visitKey = `${className}::${method}`;
    if (visited.has(visitKey) || depth >= maxDepth) {
      node.childrenLoaded = true;
      return node;
    }

    // Field accesses are leaf nodes
    if (step?.kind === 'field') {
      node.childrenLoaded = true;
      return node;
    }

    visited.add(visitKey);

    const callSeq = findCallSequence(className, method);
    if (callSeq && callSeq.length > 0) {
      node.childrenLoaded = true;
      for (const childStep of callSeq) {
        if (childStep.targetClass === '_meta_') { continue; }
        const childNode = buildNode(
          childStep.targetClass,
          childStep.member,
          childStep,
          depth + 1,
        );
        node.children.push(childNode);
      }
    } else {
      node.childrenLoaded = true;
    }

    visited.delete(visitKey);
    return node;
  }

  return buildNode(rootClass, rootMethod, null, 0);
}
