/**
 * analysis/callerIndex.ts — M28-01/02/07
 *
 * Builds a reverse index from callSequence data so we can answer:
 * "Which methods call ClassName::methodName?"
 * "Which methods read/write ClassName::fieldName?"
 *
 * The scanner produces per-method callSequence (forward direction).
 * This module inverts that into a caller/accessor lookup (reverse direction).
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
 * Build a reverse index: for every (targetClass, member) **call** found in any
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
        if (step.kind === 'field') { continue; } // calls only — fields handled by buildFieldAccessIndex

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
// Field access index (M28-07)
// ---------------------------------------------------------------------------

export interface FieldAccessRef {
  /** Class that contains the accessor method */
  accessorClass: string;
  /** Signature of the accessor method */
  accessorMethod: string;
  /** true = write, false = read */
  isWrite: boolean;
  /** Line number of the access site */
  lineNumber?: number;
  /** File location of the accessor class */
  fileLocation?: string;
}

/**
 * Build a reverse index for field accesses: for every (targetClass, field)
 * pair in any callSequence where kind === 'field', record who accesses it
 * and whether it's a read or write.
 *
 * Key format: "ClassName::fieldName"
 */
export function buildFieldAccessIndex(entries: ClassEntry[]): Map<string, FieldAccessRef[]> {
  const index = new Map<string, FieldAccessRef[]>();

  for (const entry of entries) {
    const allMethods = [
      ...(entry.interfaceMeta ?? []),
      ...(entry.privateMethods ?? []),
    ];

    for (const method of allMethods) {
      if (!method.callSequence || method.callSequence.length === 0) { continue; }

      for (const step of method.callSequence) {
        if (step.targetClass === '_meta_') { continue; }
        if (step.kind !== 'field') { continue; } // fields only

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
          accessorClass: entry.className,
          accessorMethod: method.signature,
          isWrite: step.isWrite ?? false,
          lineNumber: step.lineNumber,
          fileLocation: entry.fileLocation,
        });
      }
    }
  }

  return index;
}

/** Summary of all accessors for a single field, grouped by R/W */
export interface FieldAccessResult {
  className: string;
  fieldName: string;
  readers: FieldAccessRef[];
  writers: FieldAccessRef[];
}

/**
 * Query the field access index for a specific field.
 */
export function queryFieldAccessors(
  className: string,
  fieldName: string,
  entries: ClassEntry[],
): FieldAccessResult {
  const index = buildFieldAccessIndex(entries);
  const shortClass = className.split('::').pop() ?? className;

  const key1 = `${className}::${fieldName}`;
  const key2 = `${shortClass}::${fieldName}`;
  const refs = index.get(key1) ?? index.get(key2) ?? [];

  const readers: FieldAccessRef[] = [];
  const writers: FieldAccessRef[] = [];
  for (const ref of refs) {
    if (ref.isWrite) {
      writers.push(ref);
    } else {
      readers.push(ref);
    }
  }

  return { className, fieldName, readers, writers };
}

// ---------------------------------------------------------------------------
// Type usage analysis (M28-10)
// ---------------------------------------------------------------------------

export interface TypeUsageRef {
  /** Class that uses the type */
  className: string;
  /** How it's used */
  usageKind: 'field' | 'param' | 'local' | 'inherit';
  /** Dependency type from scanner (composition/aggregation/association/dependency/inheritance) */
  depType: string;
  /** Method signature where the type appears (for param/local) */
  methodSignature?: string;
  /** File location of the referencing class */
  fileLocation?: string;
}

export interface TypeUsageResult {
  typeName: string;
  /** Classes that have this type as a member field */
  asField: TypeUsageRef[];
  /** Methods that use this type as parameter or return type */
  asParam: TypeUsageRef[];
  /** Methods that declare a local variable of this type */
  asLocal: TypeUsageRef[];
  /** Classes that inherit from this type */
  asBase: TypeUsageRef[];
}

/**
 * Find all usages of a given type across all class entries.
 * Works for structs, enums, and any type — even those without constructors.
 *
 * Sources:
 * - dependencies[].target matching typeName → field / param / local / inherit
 * - interfaceMeta[].usedTypes / privateMethods[].usedTypes → param/return usage
 */
export function queryTypeUsage(
  typeName: string,
  entries: ClassEntry[],
): TypeUsageResult {
  const shortName = typeName.split('::').pop() ?? typeName;

  const asField: TypeUsageRef[] = [];
  const asParam: TypeUsageRef[] = [];
  const asLocal: TypeUsageRef[] = [];
  const asBase: TypeUsageRef[] = [];

  function matches(target: string): boolean {
    return target === typeName || target === shortName;
  }

  for (const entry of entries) {
    // Skip self-references
    if (entry.className === typeName || entry.className.split('::').pop() === shortName) {
      continue;
    }

    // 1. Dependencies
    for (const dep of entry.dependencies) {
      if (!matches(dep.target)) { continue; }

      switch (dep.type) {
        case 'composition':
        case 'aggregation':
          asField.push({
            className: entry.className,
            usageKind: 'field',
            depType: dep.type,
            fileLocation: entry.fileLocation,
          });
          break;
        case 'association':
          asParam.push({
            className: entry.className,
            usageKind: 'param',
            depType: dep.type,
            fileLocation: entry.fileLocation,
          });
          break;
        case 'dependency':
          asLocal.push({
            className: entry.className,
            usageKind: 'local',
            depType: dep.type,
            fileLocation: entry.fileLocation,
          });
          break;
        case 'inheritance':
          asBase.push({
            className: entry.className,
            usageKind: 'inherit',
            depType: dep.type,
            fileLocation: entry.fileLocation,
          });
          break;
      }
    }

    // 2. usedTypes in method metadata — gives method-level granularity
    const allMethods = [
      ...(entry.interfaceMeta ?? []),
      ...(entry.privateMethods ?? []),
    ];
    for (const method of allMethods) {
      if (!method.usedTypes) { continue; }
      for (const ut of method.usedTypes) {
        if (matches(ut)) {
          // Check if already captured via dependency; add method-level detail
          asParam.push({
            className: entry.className,
            usageKind: 'param',
            depType: 'association',
            methodSignature: method.signature,
            fileLocation: entry.fileLocation,
          });
          break; // one per method is enough
        }
      }
    }
  }

  // Deduplicate asParam (dependency-level + method-level may overlap)
  const paramSeen = new Set<string>();
  const dedupedParam: TypeUsageRef[] = [];
  for (const ref of asParam) {
    const key = `${ref.className}::${ref.methodSignature ?? ''}`;
    if (!paramSeen.has(key)) {
      paramSeen.add(key);
      dedupedParam.push(ref);
    }
  }

  return { typeName, asField, asParam: dedupedParam, asLocal, asBase };
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
