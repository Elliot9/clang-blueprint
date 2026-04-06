/**
 * modes/TraceController.ts — P16-03.
 *
 * Handles Trace Mode: focal point + n-hop subgraph, call chain panel,
 * impact analysis, and error log anchor.
 *
 * Context assembly is delegated to analysis/context.ts (pure functions).
 * The reverseDeps map is loaded from blueprint_graph.json by AppShell and
 * passed in at construction time so lookups are O(1).
 */

import type * as vscode from 'vscode';
import type { ModeController } from '../shell/ModeController';
import type { WebviewToExtension } from '../shared/messages';
import type { IAnalysisProvider, ClassEntry, ModuleEntry } from '../shared/types';
import { buildTraceContext, computeImpact } from '../analysis/context';
import { buildFlow } from '../analysis/flowBuilder';
import { buildCallTree } from '../analysis/callTree';
import { buildCallerTree } from '../analysis/callerIndex';

export class TraceController implements ModeController {
  private panel: vscode.WebviewPanel | undefined;

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
    /** reverseDeps from blueprint_graph.json — pass {} if not available */
    private readonly reverseDeps: Record<string, string[]> = {},
    private readonly modules: ModuleEntry[] = [],
  ) {}

  activate(panel: vscode.WebviewPanel): void {
    this.panel = panel;
  }

  deactivate(): void {
    this.panel = undefined;
  }

  handleMessage(message: WebviewToExtension): boolean {
    if (!this.panel) { return false; }

    switch (message.type) {
      case 'setFocal':
        this._handleSetFocal(message.className, message.methodSignature, message.hops);
        return true;
      case 'requestImpact':
        this._handleImpactRequest(message.className);
        return true;
      case 'locateAnchor':
        this._handleLocateAnchor(message.errorLog);
        return true;
      case 'flowQuery':
        this._handleFlowQuery(message.query);
        return true;
      case 'requestCallTree':
        this._handleCallTree(message.className, message.methodSignature, message.maxDepth);
        return true;
      case 'requestCallPathExplain':
        this._handleCallPathExplain(message.className, message.methodSignature, message.path);
        return true;
      case 'requestCallerTree':
        this._handleCallerTree(message.className, message.methodSignature, message.maxDepth);
        return true;
      default:
        return false;
    }
  }

  private async _handleSetFocal(
    className: string,
    methodSignature: string | undefined,
    hops: number,
  ): Promise<void> {
    if (!this.panel) { return; }

    const subgraph = buildTraceContext(className, hops, this.allEntries, this.reverseDeps);
    const focalEntry = this.allEntries.find(e => e.className === className);
    // callSequence lives inside interfaceMeta / privateMethods per-method objects,
    // NOT at the top-level ClassEntry — look it up by signature.
    let callChain: import('../shared/types').CallStep[] = [];
    if (focalEntry && methodSignature) {
      const pubMeta = focalEntry.interfaceMeta?.find(m => m.signature === methodSignature);
      const privMeta = focalEntry.privateMethods?.find(m => m.signature === methodSignature);
      callChain = pubMeta?.callSequence ?? privMeta?.callSequence ?? [];
    }
    const explanation = await this.provider.explainChain(callChain, subgraph);

    this.panel.webview.postMessage({
      type: 'traceResult',
      focalClass: className,
      focalMethod: methodSignature,
      subgraph,
      callChain,
      explanation,
    });
  }

  private _handleImpactRequest(className: string): void {
    if (!this.panel) { return; }
    const { direct, indirect } = computeImpact(className, this.reverseDeps);
    this.panel.webview.postMessage({
      type: 'impactResult',
      origin: className,
      direct,
      indirect,
    });
  }

  private async _handleLocateAnchor(errorLog: string): Promise<void> {
    if (!this.panel) { return; }
    const classes = await this.provider.locateAnchor(errorLog, this.allEntries);
    this.panel.webview.postMessage({ type: 'anchorResult', classes });
  }

  private async _handleFlowQuery(query: string): Promise<void> {
    if (!this.panel) { return; }

    // Build classToModule lookup
    const classToModule: Record<string, string> = {};
    for (const m of this.modules) {
      for (const cn of m.classNames) { classToModule[cn] = m.name; }
    }

    // Use AI to find relevant classes, then try building flows from their methods
    const matches = await this.provider.findRelevant(query, this.allEntries);
    const flows: import('../analysis/flowBuilder').Flow[] = [];

    for (const match of matches.slice(0, 10)) {
      const entry = match.entry;
      for (const sig of entry.interfaces.slice(0, 3)) {
        const nameMatch = sig.match(/\b([a-zA-Z_]\w*)\s*\(/);
        if (!nameMatch) { continue; }
        const flow = buildFlow(entry.className, nameMatch[1], this.allEntries, classToModule);
        if (flow && flow.steps.length >= 2) {
          flows.push(flow);
        }
      }
      if (flows.length >= 5) { break; }
    }

    // Sort by step count desc
    flows.sort((a, b) => b.steps.length - a.steps.length);

    this.panel.webview.postMessage({
      type: 'flowResult',
      query,
      flows: flows.slice(0, 5),
    });
  }

  private _handleCallTree(className: string, methodSignature: string, maxDepth?: number): void {
    if (!this.panel) { return; }
    const nameMatch = methodSignature.match(/\b([a-zA-Z_~]\w*)\s*\(/);
    const methodName = nameMatch ? nameMatch[1] : methodSignature;
    const tree = buildCallTree(className, methodName, this.allEntries, maxDepth ?? 10);
    this.panel.webview.postMessage({
      type: 'callTreeResult',
      className,
      methodSignature,
      tree,
    });
  }

  private _handleCallerTree(className: string, methodSignature: string, maxDepth?: number): void {
    if (!this.panel) { return; }
    const nameMatch = methodSignature.match(/\b([a-zA-Z_~]\w*)\s*\(/);
    const methodName = nameMatch ? nameMatch[1] : methodSignature;
    const tree = buildCallerTree(className, methodName, this.allEntries, maxDepth ?? 6);
    this.panel.webview.postMessage({
      type: 'callerTreeResult',
      className,
      methodSignature,
      tree,
    });
  }

  private async _handleCallPathExplain(
    className: string,
    _methodSignature: string,
    path: import('../shared/types').CallStep[],
  ): Promise<void> {
    if (!this.panel) { return; }
    const subgraph = this.allEntries.filter(e => {
      const short = e.className.split('::').pop();
      return path.some(s => s.targetClass === e.className || s.targetClass === short);
    });
    const explanation = await this.provider.explainChain(path, subgraph);
    this.panel.webview.postMessage({
      type: 'callPathExplanation',
      className,
      explanation,
    });
  }
}
