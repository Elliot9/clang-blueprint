/**
 * modes/ExploreController.ts — P16-02 + P22-06 + P23.
 *
 * Handles Explore Mode: namespace tree, module cluster canvas, AI summaries,
 * and feature keyword search.
 */

import type * as vscode from 'vscode';
import type { ModeController } from '../shell/ModeController';
import type { WebviewToExtension } from '../shared/messages';
import type { IAnalysisProvider, ClassEntry, ModuleEntry, ModuleEdge, EntryPoint } from '../shared/types';
import { buildExploreContext } from '../analysis/context';

export class ExploreController implements ModeController {
  private panel: vscode.WebviewPanel | undefined;

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
    private readonly modules: ModuleEntry[] = [],
    private readonly moduleEdges: ModuleEdge[] = [],
    private readonly entryPoints: EntryPoint[] = [],
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
      case 'requestSummary':
        this._handleSummaryRequest(message.className);
        return true;
      case 'featureQuery':
        this._handleFeatureQuery(message.query);
        return true;
      case 'requestModuleSummary':
        this._handleModuleSummary(message.moduleName);
        return true;
      case 'moduleDrillDown':
        this._handleModuleDrillDown(message.moduleName);
        return true;
      case 'moduleOverview':
        this._handleModuleOverview();
        return true;
      default:
        return false;
    }
  }

  private async _handleSummaryRequest(className: string): Promise<void> {
    const entry = this.allEntries.find(e => e.className === className);
    if (!entry || !this.panel) { return; }

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

  private async _handleModuleSummary(moduleName: string): Promise<void> {
    if (!this.panel) { return; }
    const mod = this.modules.find(m => m.name === moduleName);
    if (!mod) { return; }

    // Find neighbor modules (connected via moduleEdges)
    const neighborNames = new Set<string>();
    this.moduleEdges.forEach(e => {
      if (e.source === moduleName) { neighborNames.add(e.target); }
      if (e.target === moduleName) { neighborNames.add(e.source); }
    });
    const neighborModules = this.modules.filter(m => neighborNames.has(m.name));

    const summary = await this.provider.summarizeModule(mod, this.allEntries, neighborModules);
    this.panel.webview.postMessage({
      type: 'moduleSummaryResult',
      moduleName,
      summary,
    });
  }

  private _handleModuleDrillDown(moduleName: string): void {
    if (!this.panel) { return; }
    const mod = this.modules.find(m => m.name === moduleName);
    if (!mod) { return; }

    // Send only the classes belonging to this module + 1-hop external deps
    const classSet = new Set(mod.classNames);
    const modClasses = this.allEntries.filter(e => classSet.has(e.className));

    const extTargets = new Set<string>();
    modClasses.forEach(c => {
      c.dependencies.forEach(d => {
        if (!classSet.has(d.target)) { extTargets.add(d.target); }
      });
    });
    const extClasses = this.allEntries.filter(e => extTargets.has(e.className));

    const combined = [...modClasses, ...extClasses];
    this.panel.webview.postMessage({
      type: 'indexLoaded',
      entries: combined,
      totalCount: this.allEntries.length,
    });
  }

  private _handleModuleOverview(): void {
    if (!this.panel || this.modules.length === 0) { return; }
    this.panel.webview.postMessage({
      type: 'modulesLoaded',
      modules: this.modules,
      moduleEdges: this.moduleEdges,
      entryPoints: this.entryPoints,
    });
  }
}
