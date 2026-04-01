/**
 * shared/types.ts — Cross-layer data contracts for clang-blueprint.
 *
 * These types flow between:
 *   Data Layer (scanner JSON) → Analysis Layer → AI Layer → Extension Host → Webview
 *
 * Rule: nothing in this file imports from vscode or any layer-specific module.
 * All layers import *from* here; nothing here imports *from* the layers.
 */

// ---------------------------------------------------------------------------
// Core data (mirrors blueprint_index.json schema)
// ---------------------------------------------------------------------------

export interface Dependency {
  target: string;
  type: 'composition' | 'aggregation' | 'inheritance' | 'association' | 'dependency';
  cardinality?: string;
}

export interface MethodMeta {
  signature: string;
  lineNumber: number;
  /** Types used as parameters or return type — for badge display (P5-01) */
  usedTypes?: string[];
  /** Ordered member-access / call sequence from the method body (P9-02) */
  callSequence?: CallStep[];
}

/**
 * Private / protected method metadata produced by the scanner (P10-01).
 * Mirrors MethodMeta but adds an `access` discriminator.
 */
export interface PrivateMethodMeta {
  signature: string;
  lineNumber: number;
  access: 'protected' | 'private';
  usedTypes?: string[];
  callSequence?: CallStep[];
}

/** A single step in a method's call sequence (P9-02 / P11-01) */
export interface CallStep {
  targetClass: string;       // '_self_' for own-class access
  member: string;
  kind: 'call' | 'field';
  isWrite?: boolean;         // for field access: true = write, false = read
  lineNumber?: number;
}

/** Full class entry — canonical shape after the scanner. */
export interface ClassEntry {
  className: string;
  responsibility: string;
  namespace: string;
  fileLocation: string;
  lineNumber: number;
  baseClasses: string[];
  templateParams: string[];
  dependencies: Dependency[];

  // Member sections (P10-01)
  attributes?: string[];         // formatted field declarations
  interfaces: string[];          // public method signatures (string form)
  interfaceMeta?: MethodMeta[];       // rich per-method metadata (public)
  privateMethods?: PrivateMethodMeta[]; // protected/private method metadata

  // Type aliases discovered in this class (P8-04)
  typeAliases?: Array<{ alias: string; underlying: string }>;
}

// ---------------------------------------------------------------------------
// Analysis layer outputs
// ---------------------------------------------------------------------------

/** Result of an impact analysis: what changes if `origin` changes. */
export interface ImpactResult {
  origin: string;         // className that was changed
  direct: string[];       // classes with a direct dependency on origin
  indirect: string[];     // transitive dependents (≥2 hops)
}

/**
 * Structured summary for a class or namespace produced by an analysis provider.
 * Used in Explore Mode right panel (P18-03).
 */
export interface AnalysisSummary {
  /** One-line intent statement */
  intent: string;
  /** Key responsibilities as bullet points */
  responsibilities: string[];
  /** Class names that this entry is most used by */
  usedBy: string[];
  /** Class names that this entry primarily depends on */
  dependsOn: string[];
  /** Any additional notes (e.g. template specialisations, deprecation) */
  notes?: string;
}

/** A TF-IDF or AI relevance match for a search query */
export interface RelevanceMatch {
  entry: ClassEntry;
  score: number;
  matchedTerms?: string[];
}

// ---------------------------------------------------------------------------
// Chat types (P20-01)
// ---------------------------------------------------------------------------

export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

// ---------------------------------------------------------------------------
// IAnalysisProvider (P13-02)
// ---------------------------------------------------------------------------

/**
 * Pluggable analysis provider interface.
 *
 * Two concrete implementations:
 *   - LocalAnalysisProvider  (TF-IDF + heuristics, no API key needed)
 *   - ClaudeAnalysisProvider (Claude API, needs CLAUDE_API_KEY)
 *
 * The Extension Host creates the active provider via the factory in ai/factory.ts
 * and passes it down to Mode Controllers. Mode Controllers never import a
 * concrete provider — they only depend on this interface.
 */
export interface IAnalysisProvider {
  readonly providerId: 'local' | 'claude';

  /** Returns false if this provider cannot be used (e.g. missing API key). */
  isAvailable(): Promise<boolean>;

  /**
   * Produce a human-readable AnalysisSummary for a single class.
   * Used by ExploreController when a class node is selected.
   */
  summarize(entry: ClassEntry, context?: ClassEntry[]): Promise<AnalysisSummary>;

  /**
   * Return the most relevant classes for a free-text query.
   * Used by Explore Mode feature-keyword search (P18-04) and Chat context builder.
   */
  findRelevant(query: string, all: ClassEntry[]): Promise<RelevanceMatch[]>;

  /**
   * Produce a natural-language explanation of a call chain.
   * Used by Trace Mode right panel (P19-02).
   */
  explainChain(steps: CallStep[], context: ClassEntry[]): Promise<string>;

  /**
   * Given a raw error log or stack trace string, return the classes most
   * likely involved. Used by Trace Mode error-log anchor (P19-04).
   */
  locateAnchor(errorLog: string, all: ClassEntry[]): Promise<ClassEntry[]>;

  /**
   * Streaming chat. Calls `onChunk` for each streamed token.
   * Resolves when the full response is complete.
   * Used by Chat Mode (P20-01).
   */
  chat(
    messages: ChatMessage[],
    context: ClassEntry[],
    onChunk: (chunk: string) => void,
  ): Promise<void>;
}
