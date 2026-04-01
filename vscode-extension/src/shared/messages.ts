/**
 * shared/messages.ts — Extension Host ↔ Webview bidirectional message protocol.
 *
 * Convention:
 *   ExtensionToWebview  — messages posted by Extension Host, received in webview
 *   WebviewToExtension  — messages posted by webview, received in Extension Host
 *
 * Rule: no `any` types. All discriminants are string literals.
 * Both sides import from this file; this file has no vscode import.
 */

import type { ClassEntry, CallStep, ChatMessage, RelevanceMatch } from './types';

// ---------------------------------------------------------------------------
// Active application mode
// ---------------------------------------------------------------------------

export type AppMode = 'explore' | 'trace' | 'chat';

// ---------------------------------------------------------------------------
// Extension Host → Webview
// ---------------------------------------------------------------------------

/** Initial data load or refresh after rebuild */
export interface MsgIndexLoaded {
  type: 'indexLoaded';
  entries: ClassEntry[];
  totalCount: number;
}

/** Active mode changed (triggered by user clicking mode bar or Extension Host command) */
export interface MsgModeChanged {
  type: 'modeChanged';
  mode: AppMode;
}

/** Highlight a specific class node (from cursor-tracking or search) */
export interface MsgHighlight {
  type: 'highlight';
  className: string;
}

/** Filter the canvas to a subset of class names */
export interface MsgFilter {
  type: 'filter';
  pattern: string;
}

/** Result of a Trace Mode n-hop subgraph request */
export interface MsgTraceResult {
  type: 'traceResult';
  focalClass: string;
  focalMethod?: string;
  subgraph: ClassEntry[];
  callChain: CallStep[];
  explanation: string;
}

/** Result of an Explore Mode AI summary request */
export interface MsgSummaryResult {
  type: 'summaryResult';
  className: string;
  intent: string;
  responsibilities: string[];
  usedBy: string[];
  dependsOn: string[];
  notes?: string;
}

/** Result of a feature keyword / findRelevant query */
export interface MsgQueryResult {
  type: 'queryResult';
  query: string;
  matches: RelevanceMatch[];
}

/** Impact analysis result */
export interface MsgImpactResult {
  type: 'impactResult';
  origin: string;
  direct: string[];
  indirect: string[];
}

/** Streaming chunk from Chat Mode AI response */
export interface MsgChatChunk {
  type: 'chatChunk';
  chunk: string;
}

/** Chat response complete */
export interface MsgChatDone {
  type: 'chatDone';
}

/** Locate anchor result from error log */
export interface MsgAnchorResult {
  type: 'anchorResult';
  classes: ClassEntry[];
}

/** Layout direction preference */
export interface MsgLayoutDirection {
  type: 'layoutDirection';
  direction: 'TB' | 'LR' | 'BT' | 'RL';
}

/** Generic error notification to webview */
export interface MsgExtensionError {
  type: 'extensionError';
  message: string;
}

export type ExtensionToWebview =
  | MsgIndexLoaded
  | MsgModeChanged
  | MsgHighlight
  | MsgFilter
  | MsgTraceResult
  | MsgSummaryResult
  | MsgQueryResult
  | MsgImpactResult
  | MsgChatChunk
  | MsgChatDone
  | MsgAnchorResult
  | MsgLayoutDirection
  | MsgExtensionError;

// ---------------------------------------------------------------------------
// Webview → Extension Host
// ---------------------------------------------------------------------------

/** Webview finished loading its scripts and is ready to receive data */
export interface WvReady {
  type: 'ready';
}

/** User changed the active mode from the Mode Bar */
export interface WvModeSwitch {
  type: 'modeSwitch';
  mode: AppMode;
}

/** User double-clicked a class node → jump to source */
export interface WvNodeClick {
  type: 'nodeClick';
  fileLocation: string;
  lineNumber: number;
  className: string;
}

/** User double-clicked a method badge → jump to that method's line */
export interface WvMethodClick {
  type: 'methodClick';
  fileLocation: string;
  lineNumber: number;
  className: string;
  methodSignature: string;
}

/** Explore Mode: user clicked a class node to request AI summary */
export interface WvRequestSummary {
  type: 'requestSummary';
  className: string;
}

/** Explore Mode: user submitted feature keyword search */
export interface WvFeatureQuery {
  type: 'featureQuery';
  query: string;
}

/** Trace Mode: user set a new focal class/method and n-hop depth */
export interface WvSetFocal {
  type: 'setFocal';
  className: string;
  methodSignature?: string;
  hops: number;
}

/** Trace Mode: user requests impact analysis for a class */
export interface WvRequestImpact {
  type: 'requestImpact';
  className: string;
}

/** Trace Mode: user pasted an error log for anchor location */
export interface WvLocateAnchor {
  type: 'locateAnchor';
  errorLog: string;
}

/** Chat Mode: user sent a message (controller keeps history server-side) */
export interface WvChatMessage {
  type: 'chatMessage';
  text: string;
  selectedClasses: string[];
}

/** Chat Mode: user updated context class list */
export interface WvContextUpdate {
  type: 'contextUpdate';
  selectedClasses: string[];
}

/** Server-side search (large codebase) */
export interface WvSearch {
  type: 'search';
  pattern: string;
}

/** Copy text to clipboard via Extension Host */
export interface WvCopyText {
  type: 'copyText';
  text: string;
}

/** Error from webview JS */
export interface WvError {
  type: 'error';
  message: string;
}

export type WebviewToExtension =
  | WvReady
  | WvModeSwitch
  | WvNodeClick
  | WvMethodClick
  | WvRequestSummary
  | WvFeatureQuery
  | WvSetFocal
  | WvRequestImpact
  | WvLocateAnchor
  | WvChatMessage
  | WvContextUpdate
  | WvSearch
  | WvCopyText
  | WvError;
