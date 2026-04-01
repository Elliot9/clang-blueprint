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
import type { IAnalysisProvider, ClassEntry } from '../shared/types';
import { buildTraceContext, computeImpact } from '../analysis/context';

export class TraceController implements ModeController {
  private panel: vscode.WebviewPanel | undefined;

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
    /** reverseDeps from blueprint_graph.json — pass {} if not available */
    private readonly reverseDeps: Record<string, string[]> = {},
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
    const callChain = focalEntry && methodSignature
      ? (focalEntry.callSequence?.[methodSignature] ?? [])
      : [];
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
}
