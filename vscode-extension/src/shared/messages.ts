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

import type { ClassEntry, CallStep, ChatMessage, RelevanceMatch, ModuleEntry, ModuleEdge, EntryPoint, ModuleSummary } from './types';
import type { ExplorationPath } from '../analysis/explorationPath';
import type { Flow } from '../analysis/flowBuilder';
import type { CallTreeNode } from '../analysis/callTree';
import type { CallerTreeNode, FieldAccessResult } from '../analysis/callerIndex';

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

/** Highlight all upstream (dependency) ancestors of a class */
export interface MsgHighlightUpstream {
  type: 'highlightUpstream';
  className: string;
}

/** Highlight all downstream (dependent) descendants of a class */
export interface MsgHighlightDownstream {
  type: 'highlightDownstream';
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

/** Module overview data for v2 index (P22) */
export interface MsgModulesLoaded {
  type: 'modulesLoaded';
  modules: ModuleEntry[];
  moduleEdges: ModuleEdge[];
  entryPoints: EntryPoint[];
  projectName?: string;
}

/** Module-level AI summary result (P23) */
export interface MsgModuleSummaryResult {
  type: 'moduleSummaryResult';
  moduleName: string;
  summary: ModuleSummary;
}

/** Project-level summary (P23) */
export interface MsgProjectSummary {
  type: 'projectSummary';
  summary: string;
}

/** Suggested exploration path (M24-05) */
export interface MsgExplorationPath {
  type: 'explorationPath';
  path: ExplorationPath;
}

/** Key flows for module overview (M25-03) */
export interface MsgKeyFlows {
  type: 'keyFlows';
  flows: Flow[];
}

/** Flow query result for Trace Mode (M25-04) */
export interface MsgFlowResult {
  type: 'flowResult';
  query: string;
  flows: Flow[];
}

/** Call tree result (M27-07) */
export interface MsgCallTreeResult {
  type: 'callTreeResult';
  className: string;
  methodSignature: string;
  tree: CallTreeNode;
}

/** AI explanation of a call path (M27-12) */
export interface MsgCallPathExplanation {
  type: 'callPathExplanation';
  className: string;
  explanation: string;
}

/** Reverse caller tree result (M28-02) */
export interface MsgCallerTreeResult {
  type: 'callerTreeResult';
  className: string;
  methodSignature: string;
  tree: CallerTreeNode;
}

/** Field accessor analysis result with R/W breakdown (M28-07) */
export interface MsgFieldAccessorsResult {
  type: 'fieldAccessorsResult';
  className: string;
  fieldName: string;
  result: FieldAccessResult;
}

/** Webview UI language (Traditional Chinese or English) */
export interface MsgUiLocaleChanged {
  type: 'uiLocaleChanged';
  locale: 'zh-TW' | 'en';
}

/** Standalone chat popout: sync context class list from extension */
export interface MsgChatPopoutInit {
  type: 'chatPopoutInit';
  selectedClasses: string[];
}

export type ExtensionToWebview =
  | MsgIndexLoaded
  | MsgModeChanged
  | MsgHighlight
  | MsgHighlightUpstream
  | MsgHighlightDownstream
  | MsgFilter
  | MsgTraceResult
  | MsgSummaryResult
  | MsgQueryResult
  | MsgImpactResult
  | MsgChatChunk
  | MsgChatDone
  | MsgAnchorResult
  | MsgLayoutDirection
  | MsgExtensionError
  | MsgModulesLoaded
  | MsgModuleSummaryResult
  | MsgProjectSummary
  | MsgExplorationPath
  | MsgKeyFlows
  | MsgFlowResult
  | MsgCallTreeResult
  | MsgCallPathExplanation
  | MsgCallerTreeResult
  | MsgFieldAccessorsResult
  | MsgUiLocaleChanged
  | MsgChatPopoutInit;

// ---------------------------------------------------------------------------
// Webview → Extension Host
// ---------------------------------------------------------------------------

/** Persist UI language to clangBlueprint.uiLocale */
export interface WvSetUiLocale {
  type: 'setUiLocale';
  locale: 'zh-TW' | 'en';
}

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

/** Explore Mode: user clicked a module to request its summary (P23) */
export interface WvRequestModuleSummary {
  type: 'requestModuleSummary';
  moduleName: string;
}

/** Explore Mode: user drilled down into a module (P22) */
export interface WvModuleDrillDown {
  type: 'moduleDrillDown';
  moduleName: string;
}

/** Explore Mode: user navigated back to module overview (P22) */
export interface WvModuleOverview {
  type: 'moduleOverview';
}

/** Trace Mode: user submitted a flow query (M25-04) */
export interface WvFlowQuery {
  type: 'flowQuery';
  query: string;
}

/** Request call tree for a method (M27-07) */
export interface WvRequestCallTree {
  type: 'requestCallTree';
  className: string;
  methodSignature: string;
  maxDepth?: number;
}

/** Request AI explanation of a call path (M27-12) */
export interface WvRequestCallPathExplain {
  type: 'requestCallPathExplain';
  className: string;
  methodSignature: string;
  path: CallStep[];
}

/** Request reverse caller tree for a method (M28-02) */
export interface WvRequestCallerTree {
  type: 'requestCallerTree';
  className: string;
  methodSignature: string;
  maxDepth?: number;
}

/** Request field accessor analysis with R/W (M28-07) */
export interface WvRequestFieldAccessors {
  type: 'requestFieldAccessors';
  className: string;
  fieldName: string;
}

/** Canvas selection sync → chat context (M26-03) */
export interface WvCanvasSelect {
  type: 'canvasSelect';
  className: string;
}

/** Open AI chat in a separate editor tab (same session as main webview) */
export interface WvOpenChatPopout {
  type: 'openChatPopout';
  selectedClasses: string[];
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
  | WvError
  | WvRequestModuleSummary
  | WvModuleDrillDown
  | WvModuleOverview
  | WvFlowQuery
  | WvRequestCallTree
  | WvRequestCallPathExplain
  | WvRequestCallerTree
  | WvRequestFieldAccessors
  | WvCanvasSelect
  | WvSetUiLocale
  | WvOpenChatPopout;
