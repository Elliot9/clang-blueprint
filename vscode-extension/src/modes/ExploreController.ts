/**
 * modes/ExploreController.ts — P16-02 + P22-06 + P23.
 *
 * Handles Explore Mode: namespace tree, module cluster canvas, AI summaries,
 * and feature keyword search.
 */

import * as vscode from 'vscode';
import type { ModeController } from '../shell/ModeController';
import type { WebviewToExtension } from '../shared/messages';
import type { IAnalysisProvider, ClassEntry, ModuleEntry, ModuleEdge, EntryPoint } from '../shared/types';
import { buildExploreContext } from '../analysis/context';
import { buildCallTree } from '../analysis/callTree';
import { buildCallerTree } from '../analysis/callerIndex';

function maxClassesForWebview(): number {
  return vscode.workspace.getConfiguration('clangBlueprint').get<number>('maxClassesInDiagram') ?? 100;
}

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
    if (!this.panel) { return; }
    this.panel.webview.postMessage({
      type: 'callPathExplanation',
      className,
      explanation,
    });
  }

  private async _handleSummaryRequest(className: string): Promise<void> {
    const entry = this.allEntries.find(e => e.className === className);
    if (!entry || !this.panel) { return; }

    const context = buildExploreContext(entry.namespace ?? '', this.allEntries);
    const summary = await this.provider.summarize(entry, context);

    if (!this.panel) { return; }
    this.panel.webview.postMessage({
      type: 'summaryResult',
      className,
      ...summary,
    });
  }

  private async _handleFeatureQuery(query: string): Promise<void> {
    if (!this.panel) { return; }
    const matches = await this.provider.findRelevant(query, this.allEntries);
    if (!this.panel) { return; }
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
    if (!this.panel) { return; }
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
    // Webview replaces allEntries on moduleDrillDown with a subset; restore the full
    // index so namespace tree, feature search, and drilling into another module work again.
    const entries = this.allEntries;
    const maxC = maxClassesForWebview();
    const send = entries.length > 5000 ? entries.slice(0, maxC) : entries;
    this.panel.webview.postMessage({
      type: 'indexLoaded',
      entries: send,
      totalCount: entries.length,
    });
  }
}
