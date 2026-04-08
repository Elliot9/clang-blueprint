/**
 * shell/AppShell.ts — Central coordinator for the clang-blueprint extension.
 *
 * Responsibilities (and *only* these):
 *   1. Manage WebviewPanel lifecycle
 *   2. Route incoming webview messages to the active ModeController
 *   3. Handle cross-mode messages (nodeClick, modeSwitch, search, copyText, error)
 *   4. Watch blueprint_index.json and reload on change
 *   5. Provide the "jump to source" action used by all modes
 *
 * AppShell does NOT know about namespace trees, call chains, AI prompts, etc.
 * That knowledge lives in the Mode Controllers.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

import type { ModeController } from './ModeController';
import type { ClassEntry, IAnalysisProvider, ModuleEntry, ModuleEdge, EntryPoint } from '../shared/types';
import type { AppMode, ExtensionToWebview, WebviewToExtension } from '../shared/messages';
import { ExploreController } from '../modes/ExploreController';
import { TraceController } from '../modes/TraceController';
import { ChatController } from '../modes/ChatController';
import { createProvider } from '../ai/factory';
import { generateExplorationPath } from '../analysis/explorationPath';
import { discoverKeyFlows } from '../analysis/flowBuilder';

// ---------------------------------------------------------------------------
// Config helpers
// ---------------------------------------------------------------------------

function cfg<T>(key: string): T {
  return vscode.workspace.getConfiguration('clangBlueprint').get<T>(key) as T;
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------

export class AppShell {
  private readonly output: vscode.OutputChannel;
  private panel: vscode.WebviewPanel | undefined;
  private fileWatcher: vscode.FileSystemWatcher | undefined;
  private selectionDebounce: ReturnType<typeof setTimeout> | undefined;

  private provider: IAnalysisProvider | undefined;
  private providerConfigSignature = '';
  private allEntries: ClassEntry[] = [];
  private reverseDeps: Record<string, string[]> = {};
  private allModules: ModuleEntry[] = [];
  private moduleEdges: ModuleEdge[] = [];
  private entryPoints: EntryPoint[] = [];
  private projectName = '';
  private activeMode: AppMode = 'explore';
  private controllers: Record<AppMode, ModeController | undefined> = {
    explore: undefined,
    trace: undefined,
    chat: undefined,
  };

  /** Standalone AI Chat webview tab (optional). */
  private chatPopoutPanel: vscode.WebviewPanel | undefined;
  /** Context class names to send to the popout on first load / reveal. */
  private pendingChatPopoutContext: string[] = [];

  constructor(private readonly context: vscode.ExtensionContext) {
    this.output = vscode.window.createOutputChannel('Clang Blueprint');
    this.context.subscriptions.push(this.output);
    this.context.subscriptions.push(
      vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration('clangBlueprint.uiLocale')) {
          const raw = cfg<string>('uiLocale') ?? 'zh-TW';
          const loc = raw === 'en' ? 'en' : 'zh-TW';
          this._post({ type: 'uiLocaleChanged', locale: loc });
        }
        if (
          event.affectsConfiguration('clangBlueprint.analysisProvider') ||
          event.affectsConfiguration('clangBlueprint.claudeApiKey') ||
          event.affectsConfiguration('clangBlueprint.geminiApiKey')
        ) {
          void this._recreateProviderIfNeeded();
        }
      }),
    );
  }

  // ---------------------------------------------------------------------------
  // Panel management
  // ---------------------------------------------------------------------------

  async showDiagram(): Promise<void> {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside);
      await this._reload();
      return;
    }

    this.panel = vscode.window.createWebviewPanel(
      'clangBlueprintDiagram',
      'Blueprint: Class Diagram',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.joinPath(this.context.extensionUri, 'webview'),
        ],
      },
    );

    this.panel.webview.html = this._getWebviewHtml();
    this.panel.webview.onDidReceiveMessage(
      (msg: WebviewToExtension) => this._onMessage(msg, this.panel!.webview),
      undefined,
      this.context.subscriptions,
    );
    this.panel.onDidDispose(() => {
      this.chatPopoutPanel?.dispose();
      this.chatPopoutPanel = undefined;
      this.controllers.explore?.deactivate();
      this.controllers.trace?.deactivate();
      this.controllers.chat?.deactivate();
      this.panel = undefined;
    }, undefined, this.context.subscriptions);

    // Provider is created lazily on first panel open
    if (!this.provider) {
      this.provider = await createProvider();
      this.providerConfigSignature = this._providerSignature();
      this._log(`Provider initialized: ${this.provider.providerId}`);
    }
  }

  dispose(): void {
    if (this.selectionDebounce) { clearTimeout(this.selectionDebounce); }
    this.fileWatcher?.dispose();
    this.panel?.dispose();
  }

  // ---------------------------------------------------------------------------
  // File watcher
  // ---------------------------------------------------------------------------

  setupWatcher(): void {
    this.fileWatcher?.dispose();
    const root = this._workspaceRoot();
    if (!root) { return; }
    const rel = cfg<string>('blueprintIndexPath');
    const pattern = new vscode.RelativePattern(root, rel);
    this.fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);

    const reload = () => {
      if (!cfg<boolean>('autoReloadOnChange') || !this.panel) { return; }
      setTimeout(() => {
        this._reload();
        vscode.window.setStatusBarMessage('$(refresh) Blueprint: diagram reloaded', 3000);
      }, 500);
    };
    this.fileWatcher.onDidChange(reload, undefined, this.context.subscriptions);
    this.fileWatcher.onDidCreate(reload, undefined, this.context.subscriptions);
    this.context.subscriptions.push(this.fileWatcher);
  }

  // ---------------------------------------------------------------------------
  // Cursor tracking (T-34)
  // ---------------------------------------------------------------------------

  onCursorMove(doc: vscode.TextDocument, position: vscode.Position): void {
    if (!this.panel) { return; }
    if (this.selectionDebounce) { clearTimeout(this.selectionDebounce); }
    this.selectionDebounce = setTimeout(() => {
      const entry = this._findClassAtCursor(doc, position);
      if (entry) {
        this._post({ type: 'highlight', className: entry.className });
      }
    }, 300);
  }

  // ---------------------------------------------------------------------------
  // Commands delegated from extension.ts
  // ---------------------------------------------------------------------------

  async jumpToDefinition(): Promise<void> {
    if (!this.allEntries.length) {
      vscode.window.showWarningMessage('No blueprint entries loaded.');
      return;
    }
    const items = this.allEntries.map(e => ({
      label: e.className,
      description: e.namespace ? `${e.namespace}::${e.className}` : e.className,
      detail: `${e.fileLocation}:${e.lineNumber} — ${e.responsibility}`,
      entry: e,
    }));
    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: 'Search classes…',
      matchOnDescription: true,
      matchOnDetail: true,
    });
    if (picked) {
      await this._jumpToSource(picked.entry.fileLocation, picked.entry.lineNumber);
    }
  }

  async highlightUpstream(): Promise<void> {
    const className = await this._resolveClassName();
    if (className) { this._post({ type: 'highlightUpstream', className }); }
  }

  async highlightDownstream(): Promise<void> {
    const className = await this._resolveClassName();
    if (className) { this._post({ type: 'highlightDownstream', className }); }
  }

  filterDiagram(): void {
    if (!this.panel) {
      vscode.window.showInformationMessage("Open the diagram first with 'Blueprint: Show Class Diagram'.");
      return;
    }
    vscode.window.showInputBox({ prompt: 'Filter classes by name pattern (regex)', placeHolder: 'e.g. Manager, ^Disk' })
      .then(pattern => {
        if (pattern !== undefined) { this._post({ type: 'filter', pattern }); }
      });
  }

  // ---------------------------------------------------------------------------
  // Private: message routing
  // ---------------------------------------------------------------------------

  private _onMessage(msg: WebviewToExtension, fromWebview?: vscode.Webview): void {
    // Shell-level messages: handled here, not routed to controllers
    switch (msg.type) {
      case 'ready':
        if (fromWebview && this.chatPopoutPanel && fromWebview === this.chatPopoutPanel.webview) {
          void this._bootstrapChatPopout();
          return;
        }
        void this._reload();
        return;

      case 'openChatPopout':
        void this._openChatPopout(msg.selectedClasses);
        return;

      case 'chatMessage':
      case 'contextUpdate':
        this._ensureChatControllerReady();
        this.controllers.chat?.handleMessage(msg);
        return;

      case 'modeSwitch':
        this._switchMode(msg.mode);
        return;

      case 'nodeClick':
        this._jumpToSource(msg.fileLocation, msg.lineNumber);
        return;

      case 'methodClick':
        this._jumpToSource(msg.fileLocation, msg.lineNumber);
        return;

      case 'search':
        this._handleSearch(msg.pattern);
        return;

      case 'copyText':
        vscode.env.clipboard.writeText(msg.text).then(() => {
          vscode.window.setStatusBarMessage('$(clippy) Blueprint: copied', 3000);
        });
        return;

      case 'error':
        vscode.window.showErrorMessage(`Blueprint webview error: ${msg.message}`);
        return;

      case 'setUiLocale': {
        const loc = msg.locale === 'en' ? 'en' : 'zh-TW';
        void vscode.workspace
          .getConfiguration('clangBlueprint')
          .update('uiLocale', loc, vscode.ConfigurationTarget.Global);
        return;
      }

      case 'canvasSelect':
        // M26-03: forward canvas selection to chat controller's context
        if (this.controllers.chat) {
          this.controllers.chat.handleMessage({
            type: 'contextUpdate',
            selectedClasses: [msg.className],
          });
        }
        return;
    }

    // Route to active mode controller
    const controller = this.controllers[this.activeMode as AppMode];
    if (controller) { controller.handleMessage(msg); }
  }

  private _switchMode(mode: AppMode): void {
    if (mode === this.activeMode) { return; }
    const panel = this.panel;
    if (!panel) { return; }

    this.controllers[this.activeMode]?.deactivate();
    this.activeMode = mode;

    // Lazily create controllers
    if (!this.controllers[mode]) {
      const p = this.provider!;
      const entries = this.allEntries;
      if (mode === 'explore') { this.controllers.explore = new ExploreController(p, entries, this.allModules, this.moduleEdges, this.entryPoints); }
      if (mode === 'trace')   { this.controllers.trace   = new TraceController(p, entries, this.reverseDeps, this.allModules); }
      if (mode === 'chat')    { this.controllers.chat    = new ChatController(p, entries, (line: string) => this._log(line)); }
    }

    this.controllers[mode]!.activate(panel);
    this._post({ type: 'modeChanged', mode });
  }

  /** Drop controller references only after deactivate() so in-flight async work stops posting to the webview. */
  private _disposeControllers(): void {
    this.controllers.explore?.deactivate();
    this.controllers.trace?.deactivate();
    this.controllers.chat?.deactivate();
    this.controllers.explore = undefined;
    this.controllers.trace = undefined;
    this.controllers.chat = undefined;
  }

  private async _recreateProviderIfNeeded(): Promise<void> {
    const nextSig = this._providerSignature();
    if (nextSig === this.providerConfigSignature) { return; }

    this.provider = await createProvider();
    this.providerConfigSignature = nextSig;
    this._log(`Provider reloaded from settings: ${this.provider.providerId}`);
    this._disposeControllers();

    if (this.panel) {
      await this._reload();
      vscode.window.setStatusBarMessage('$(sync) Blueprint: analysis provider updated', 3000);
    }
  }

  private async _reload(): Promise<void> {
    const panel = this.panel;
    if (!panel) { return; }

    const root = this._workspaceRoot();
    const entries = this._loadEntries();
    this.allEntries = entries;

    // Load blueprint_graph.json for reverseDeps (O(1) impact lookups)
    const indexPath = root ? this._indexPath(root) : 'blueprint_index.json';
    const graphPath = indexPath.replace('blueprint_index.json', 'blueprint_graph.json');
    this.reverseDeps = this._loadReverseDeps(graphPath);

    // Rebuild controllers with fresh data
    if (this.provider) {
      this._disposeControllers();
      this.controllers.explore = new ExploreController(this.provider, entries, this.allModules, this.moduleEdges, this.entryPoints);
      this.controllers.trace   = new TraceController(this.provider, entries, this.reverseDeps, this.allModules);
      this.controllers.chat    = new ChatController(this.provider, entries, (line: string) => this._log(line));
      this.controllers[this.activeMode]!.activate(panel);
    }

    const maxClasses = cfg<number>('maxClassesInDiagram') ?? 100;
    const send = entries.length > 5000 ? entries.slice(0, maxClasses) : entries;

    this._post({ type: 'indexLoaded', entries: send, totalCount: entries.length });
    this._post({ type: 'layoutDirection', direction: cfg<'TB' | 'LR' | 'BT' | 'RL'>('layoutDirection') ?? 'TB' });

    // Send module data if v2 index
    if (this.allModules.length > 0) {
      this._post({
        type: 'modulesLoaded',
        modules: this.allModules,
        moduleEdges: this.moduleEdges,
        entryPoints: this.entryPoints,
        projectName: this.projectName,
      });

      // Exploration path (M24-05)
      const expPath = generateExplorationPath(this.allModules, this.moduleEdges, this.entryPoints);
      if (expPath) {
        this._post({ type: 'explorationPath', path: expPath });
      }

      // Key flows (M25-03)
      const flows = discoverKeyFlows(entries, this.entryPoints, this.allModules);
      if (flows.length > 0) {
        this._post({ type: 'keyFlows', flows });
      }
    }

    if (entries.length === 0) {
      const searchedPath = root ? this._indexPath(root) : '(no workspace folder open)';
      vscode.window.showWarningMessage(
        `Clang Blueprint: No entries found at "${searchedPath}". Run "Blueprint: Rebuild Index" first.`,
      );
    } else {
      panel.title = `Blueprint: Class Diagram (${entries.length} classes)`;
    }

    if (this.chatPopoutPanel) {
      (this.controllers.chat as ChatController | undefined)?.registerPopoutWebview(
        this.chatPopoutPanel.webview,
      );
    }
  }

  private _handleSearch(pattern: string): void {
    if (!pattern || !this.allEntries.length) { return; }
    let matched: ClassEntry[];
    try {
      const re = new RegExp(pattern, 'i');
      matched = this.allEntries.filter(e => re.test(e.className));
    } catch { return; }

    const neighborNames = new Set<string>();
    matched.forEach(e => {
      e.dependencies.forEach(d => neighborNames.add(d.target));
      e.baseClasses.forEach(b => neighborNames.add(b));
    });
    const matchedNames = new Set(matched.map(e => e.className));
    const neighbors = this.allEntries.filter(
      e => !matchedNames.has(e.className) && neighborNames.has(e.className),
    );
    this._post({ type: 'indexLoaded', entries: [...matched, ...neighbors], totalCount: this.allEntries.length });
  }

  // ---------------------------------------------------------------------------
  // Private: jump to source
  // ---------------------------------------------------------------------------

  private async _jumpToSource(fileLocation: string, lineNumber: number): Promise<void> {
    const root = this._workspaceRoot();
    if (!root) { vscode.window.showErrorMessage('No workspace folder open.'); return; }

    const abs = path.isAbsolute(fileLocation) ? fileLocation : path.join(root, fileLocation);
    if (!fs.existsSync(abs)) {
      vscode.window.showErrorMessage(`Blueprint: File not found: ${abs}`);
      return;
    }
    const doc  = await vscode.workspace.openTextDocument(abs);
    const line = Math.max(0, lineNumber - 1);
    const range = new vscode.Range(line, 0, line, 0);
    await vscode.window.showTextDocument(doc, {
      viewColumn: vscode.ViewColumn.One,
      selection: range,
      preserveFocus: false,
    });
    const editor = vscode.window.visibleTextEditors.find(e => e.document.uri.fsPath === abs);
    if (editor) {
      editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
      const deco = vscode.window.createTextEditorDecorationType({
        backgroundColor: new vscode.ThemeColor('editor.findMatchHighlightBackground'),
        isWholeLine: true,
      });
      editor.setDecorations(deco, [range]);
      setTimeout(() => deco.dispose(), 2000);
    }
  }

  // ---------------------------------------------------------------------------
  // Private: data loading
  // ---------------------------------------------------------------------------

  private _loadEntries(): ClassEntry[] {
    const root = this._workspaceRoot();
    if (!root) { return []; }
    const indexPath = this._indexPath(root);
    try {
      if (!fs.existsSync(indexPath)) { return []; }
      const raw = fs.readFileSync(indexPath, 'utf-8');
      const parsed = JSON.parse(raw);
      // V2 format: object with { version, classes, modules, ... }
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && parsed.version === 2) {
        this.allModules = parsed.modules ?? [];
        this.moduleEdges = parsed.moduleEdges ?? [];
        this.entryPoints = parsed.entryPoints ?? [];
        this.projectName = parsed.projectName ?? '';
        return (parsed.classes ?? []) as ClassEntry[];
      }
      // V1 format: bare array
      if (Array.isArray(parsed)) {
        this.allModules = [];
        this.moduleEdges = [];
        this.entryPoints = [];
        this.projectName = '';
        return parsed as ClassEntry[];
      }
      throw new Error('blueprint_index.json must be a JSON array or v2 object');
    } catch (err) {
      vscode.window.showErrorMessage(`Clang Blueprint: Failed to load index: ${err}`);
      return [];
    }
  }

  private async _resolveClassName(): Promise<string | undefined> {
    if (!this.panel) {
      vscode.window.showInformationMessage("Open the diagram first with 'Blueprint: Show Class Diagram'.");
      return undefined;
    }
    if (!this.allEntries.length) {
      vscode.window.showWarningMessage('No blueprint entries loaded.');
      return undefined;
    }
    // Try class at current cursor first
    const editor = vscode.window.activeTextEditor;
    if (editor) {
      const entry = this._findClassAtCursor(editor.document, editor.selection.active);
      if (entry) { return entry.className; }
    }
    // Fall back to quick pick
    const items = this.allEntries.map(e => ({
      label: e.className,
      description: e.namespace ?? '',
    }));
    const picked = await vscode.window.showQuickPick(items, { placeHolder: 'Select a class to highlight' });
    return picked?.label;
  }

  private _findClassAtCursor(doc: vscode.TextDocument, position: vscode.Position): ClassEntry | undefined {
    const root = this._workspaceRoot();
    if (!root || !this.allEntries.length) { return undefined; }
    const norm = (p: string) => p.replace(/\\/g, '/');
    const docNorm = norm(doc.uri.fsPath);
    const curLine = position.line + 1;

    const candidates = this.allEntries.filter(e => {
      const abs = norm(path.isAbsolute(e.fileLocation) ? e.fileLocation : path.join(root, e.fileLocation));
      return abs === docNorm;
    });

    let best: ClassEntry | undefined;
    let bestDist = Infinity;
    for (const c of candidates) {
      const dist = curLine - c.lineNumber;
      if (dist >= 0 && dist < bestDist) { bestDist = dist; best = c; }
    }
    return best;
  }

  // ---------------------------------------------------------------------------
  // Private: helpers
  // ---------------------------------------------------------------------------

  private _post(msg: ExtensionToWebview): void {
    this.panel?.webview.postMessage(msg);
    this._mirrorDataToChatPopout(msg);
  }

  /** Keep the optional chat popout index/modules in sync with the main diagram tab. */
  private _mirrorDataToChatPopout(msg: ExtensionToWebview): void {
    const w = this.chatPopoutPanel?.webview;
    if (!w) { return; }
    const t = (msg as { type: string }).type;
    const syncTypes = new Set([
      'indexLoaded',
      'modulesLoaded',
      'layoutDirection',
      'explorationPath',
      'keyFlows',
      'uiLocaleChanged',
    ]);
    if (syncTypes.has(t)) {
      void w.postMessage(msg);
    }
  }

  private _ensureChatControllerReady(): void {
    const panel = this.panel;
    if (!panel || !this.provider) { return; }
    if (!this.controllers.chat) {
      this.controllers.chat = new ChatController(this.provider, this.allEntries, (line: string) => this._log(line));
    }
    this.controllers.chat.activate(panel);
  }

  private async _openChatPopout(selectedClasses: string[]): Promise<void> {
    this.pendingChatPopoutContext = [...selectedClasses];
    if (!this.panel) {
      await this.showDiagram();
    }
    if (!this.panel || !this.provider) {
      vscode.window.showWarningMessage('Clang Blueprint: Open the class diagram first.');
      return;
    }
    this._ensureChatControllerReady();

    if (this.chatPopoutPanel) {
      this.chatPopoutPanel.reveal(vscode.ViewColumn.One);
      (this.controllers.chat as ChatController).registerPopoutWebview(this.chatPopoutPanel.webview);
      void this.chatPopoutPanel.webview.postMessage({
        type: 'chatPopoutInit',
        selectedClasses: this.pendingChatPopoutContext,
      });
      return;
    }

    const pop = vscode.window.createWebviewPanel(
      'clangBlueprintChatPopout',
      'Blueprint: AI Chat',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(this.context.extensionUri, 'webview')],
      },
    );
    this.chatPopoutPanel = pop;
    pop.webview.html = this._getWebviewHtml(true);
    pop.webview.onDidReceiveMessage(
      (m: WebviewToExtension) => this._onMessage(m, pop.webview),
      undefined,
      this.context.subscriptions,
    );
    pop.onDidDispose(
      () => {
        (this.controllers.chat as ChatController | undefined)?.registerPopoutWebview(undefined);
        this.chatPopoutPanel = undefined;
      },
      undefined,
      this.context.subscriptions,
    );
  }

  private async _bootstrapChatPopout(): Promise<void> {
    const pop = this.chatPopoutPanel;
    if (!pop) { return; }
    this._ensureChatControllerReady();
    (this.controllers.chat as ChatController).registerPopoutWebview(pop.webview);

    const maxClasses = cfg<number>('maxClassesInDiagram') ?? 100;
    const entries = this.allEntries;
    const send = entries.length > 5000 ? entries.slice(0, maxClasses) : entries;

    void pop.webview.postMessage({
      type: 'indexLoaded',
      entries: send,
      totalCount: entries.length,
    });
    void pop.webview.postMessage({
      type: 'layoutDirection',
      direction: cfg<'TB' | 'LR' | 'BT' | 'RL'>('layoutDirection') ?? 'TB',
    });
    void pop.webview.postMessage({ type: 'modeChanged', mode: 'chat' });
    void pop.webview.postMessage({
      type: 'chatPopoutInit',
      selectedClasses: this.pendingChatPopoutContext,
    });
    this.pendingChatPopoutContext = [];

    const raw = cfg<string>('uiLocale') ?? 'zh-TW';
    const loc = raw === 'en' ? 'en' : 'zh-TW';
    void pop.webview.postMessage({ type: 'uiLocaleChanged', locale: loc });

    if (this.allModules.length > 0) {
      void pop.webview.postMessage({
        type: 'modulesLoaded',
        modules: this.allModules,
        moduleEdges: this.moduleEdges,
        entryPoints: this.entryPoints,
        projectName: this.projectName,
      });
    }
  }

  private _log(line: string): void {
    this.output.appendLine(`[${new Date().toISOString()}] ${line}`);
  }

  private _workspaceRoot(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }

  private _indexPath(root: string): string {
    const p = cfg<string>('blueprintIndexPath');
    return path.isAbsolute(p) ? p : path.join(root, p);
  }

  private _providerSignature(): string {
    const provider = cfg<string>('analysisProvider') ?? 'local';
    const claude = cfg<string>('claudeApiKey') ?? '';
    const gemini = cfg<string>('geminiApiKey') ?? '';
    return `${provider}|${claude}|${gemini}`;
  }

  private _loadReverseDeps(graphPath: string): Record<string, string[]> {
    try {
      if (!fs.existsSync(graphPath)) { return {}; }
      const raw = fs.readFileSync(graphPath, 'utf-8');
      const data = JSON.parse(raw);
      return (data?.reverseDeps as Record<string, string[]>) ?? {};
    } catch {
      return {};
    }
  }

  private _getWebviewHtml(chatPopout = false): string {
    const htmlPath = vscode.Uri.joinPath(this.context.extensionUri, 'webview', 'index.html');
    const i18nPath = vscode.Uri.joinPath(this.context.extensionUri, 'webview', 'i18n-bundle.js');
    try {
      let html = fs.readFileSync(htmlPath.fsPath, 'utf-8');
      let bundle = '';
      try {
        bundle = fs.readFileSync(i18nPath.fsPath, 'utf-8');
      } catch {
        bundle = "window.BLUEPRINT_I18N={ 'zh-TW':{}, en:{} };";
      }
      const raw = vscode.workspace.getConfiguration('clangBlueprint').get<string>('uiLocale') ?? 'zh-TW';
      const safeLoc = raw === 'en' ? 'en' : 'zh-TW';
      const popoutFlag = chatPopout ? "window.__BLUEPRINT_CHAT_POPOUT__=true;\n" : '';
      const inject = `window.__BLUEPRINT_UI_LOCALE__='${safeLoc}';\n${popoutFlag}${bundle}\n\n`;
      const needle = '<script>\n// ╔══════════════════════════════════════════════════════════════╗';
      if (html.includes(needle)) {
        html = html.replace(needle, `<script>\n${inject}// ╔══════════════════════════════════════════════════════════════╗`);
      }
      return html;
    } catch {
      return `<!DOCTYPE html><html><body style="background:#1e1e1e;color:#ccc;padding:2rem;">
        <h2>Clang Blueprint</h2><p>Webview HTML not found.</p></body></html>`;
    }
  }
}
