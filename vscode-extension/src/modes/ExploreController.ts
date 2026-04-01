/**
 * modes/ExploreController.ts — P16-02.
 *
 * Handles Explore Mode: namespace tree, module cluster canvas, AI summaries,
 * and feature keyword search.
 */

import type * as vscode from 'vscode';
import type { ModeController } from '../shell/ModeController';
import type { WebviewToExtension } from '../shared/messages';
import type { IAnalysisProvider, ClassEntry } from '../shared/types';
import { buildExploreContext } from '../analysis/context';

export class ExploreController implements ModeController {
  private panel: vscode.WebviewPanel | undefined;

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
  ) {}

  activate(panel: vscode.WebviewPanel): void {
    this.panel = panel;
    // TODO P18-01: send namespace tree data to webview
  }

  deactivate(): void {
    this.panel = undefined;
  }

  handleMessage(message: WebviewToExtension): boolean {
    if (!this.panel) { return false; }

    switch (message.type) {
      case 'requestSummary':
        this._handleSummaryRequest(message.className);
        return true;
      case 'featureQuery':
        this._handleFeatureQuery(message.query);
        return true;
      default:
        return false;
    }
  }

  private async _handleSummaryRequest(className: string): Promise<void> {
    const entry = this.allEntries.find(e => e.className === className);
    if (!entry || !this.panel) { return; }

    // Build context: the class's namespace neighbourhood
    const context = buildExploreContext(entry.namespace ?? '', this.allEntries);
    const summary = await this.provider.summarize(entry, context);

    this.panel.webview.postMessage({
      type: 'summaryResult',
      className,
      ...summary,
    });
  }

  private async _handleFeatureQuery(query: string): Promise<void> {
    if (!this.panel) { return; }
    const matches = await this.provider.findRelevant(query, this.allEntries);
    this.panel.webview.postMessage({ type: 'queryResult', query, matches });
  }
}
