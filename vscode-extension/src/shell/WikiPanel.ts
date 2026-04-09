/**
 * shell/WikiPanel.ts — Dedicated wiki webview panel for Blueprint.
 *
 * Renders a DeepWiki-style browsable knowledge base built on top of
 * blueprint_index.json (AST-precise structure + LLM-enriched semantics).
 *
 * Separate from AppShell / the graph diagram panel so each can evolve
 * independently.  Both panels are driven by the same blueprint_index.json.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

import type { BlueprintIndex, BlueprintChanges } from '../shared/types';

type WikiMessage =
  | { type: 'ready' }
  | { type: 'jumpToSource'; file: string; line: number };

export class WikiPanel {
  static readonly viewType = 'clangBlueprint.wiki';

  private panel: vscode.WebviewPanel | undefined;
  private fileWatcher: vscode.FileSystemWatcher | undefined;
  private readonly context: vscode.ExtensionContext;

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
  }

  show(): void {
    if (this.panel) {
      this.panel.reveal();
      return;
    }

    this.panel = vscode.window.createWebviewPanel(
      WikiPanel.viewType,
      'Blueprint Wiki',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        localResourceRoots: [
          vscode.Uri.joinPath(this.context.extensionUri, 'wiki-webview', 'dist'),
        ],
        retainContextWhenHidden: true,
      },
    );

    this.panel.iconPath = new vscode.ThemeIcon('book');
    this.panel.webview.html = this._buildHtml();

    // Handle messages from webview
    this.panel.webview.onDidReceiveMessage(
      (msg: WikiMessage) => {
        if (msg.type === 'ready') {
          this._loadIndex();
        } else if (msg.type === 'jumpToSource') {
          this._jumpToSource(msg.file, msg.line);
        }
      },
      undefined,
      this.context.subscriptions,
    );

    // Watch for blueprint_index.json changes
    this._setupWatcher();

    this.panel.onDidDispose(
      () => {
        this.panel = undefined;
        this.fileWatcher?.dispose();
        this.fileWatcher = undefined;
      },
      undefined,
      this.context.subscriptions,
    );
  }

  private _indexPath(): string | undefined {
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!root) return undefined;
    const cfg = vscode.workspace.getConfiguration('clangBlueprint');
    const rel = cfg.get<string>('blueprintIndexPath') ?? 'blueprint_index.json';
    return path.join(root, rel);
  }

  private _changesPath(): string | undefined {
    const indexPath = this._indexPath();
    if (!indexPath) return undefined;
    return path.join(path.dirname(indexPath), 'blueprint_changes.json');
  }

  private _loadIndex(): void {
    const indexPath = this._indexPath();
    if (!indexPath || !fs.existsSync(indexPath)) {
      this.panel?.webview.postMessage({
        type: 'error',
        message: 'blueprint_index.json not found. Run "Blueprint: Rebuild Index" first.',
      });
      return;
    }

    try {
      const raw = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
      // Support both v1 (bare array) and v2 (object with version)
      const index: BlueprintIndex = Array.isArray(raw)
        ? { version: 1, modules: [], moduleEdges: [], entryPoints: [], classes: raw }
        : raw;

      this.panel?.webview.postMessage({ type: 'load', index });
    } catch (err) {
      vscode.window.showErrorMessage(`Blueprint Wiki: failed to load index — ${err}`);
    }

    // Also send change history if available
    this._loadChanges();
  }

  private _loadChanges(): void {
    const changesPath = this._changesPath();
    if (!changesPath || !fs.existsSync(changesPath)) return;

    try {
      const raw = JSON.parse(fs.readFileSync(changesPath, 'utf-8'));
      const changes: BlueprintChanges = raw;
      this.panel?.webview.postMessage({ type: 'loadChanges', changes });
    } catch {
      // blueprint_changes.json is optional — silently skip parse errors
    }
  }

  private _setupWatcher(): void {
    const indexPath = this._indexPath();
    if (!indexPath) return;

    const dir = path.dirname(indexPath);

    // Watch blueprint_index.json
    const indexPattern = new vscode.RelativePattern(dir, path.basename(indexPath));
    this.fileWatcher = vscode.workspace.createFileSystemWatcher(indexPattern);
    this.fileWatcher.onDidChange(() => this._loadIndex());
    this.fileWatcher.onDidCreate(() => this._loadIndex());

    // Watch blueprint_changes.json (optional, same directory)
    const changesPattern = new vscode.RelativePattern(dir, 'blueprint_changes.json');
    const changesWatcher = vscode.workspace.createFileSystemWatcher(changesPattern);
    changesWatcher.onDidChange(() => this._loadChanges());
    changesWatcher.onDidCreate(() => this._loadChanges());
    this.context.subscriptions.push(changesWatcher);
  }

  private async _jumpToSource(file: string, line: number): Promise<void> {
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!root) return;

    const absPath = path.isAbsolute(file) ? file : path.join(root, file);
    if (!fs.existsSync(absPath)) {
      vscode.window.showWarningMessage(`Blueprint Wiki: file not found — ${absPath}`);
      return;
    }

    const uri = vscode.Uri.file(absPath);
    const pos = new vscode.Position(Math.max(0, line - 1), 0);
    const doc = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(doc, {
      selection: new vscode.Range(pos, pos),
      viewColumn: vscode.ViewColumn.Beside,
    });
  }

  private _buildHtml(): string {
    const webview = this.panel!.webview;
    const bundleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.context.extensionUri, 'wiki-webview', 'dist', 'bundle.js'),
    );
    const cssUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.context.extensionUri, 'wiki-webview', 'dist', 'bundle.css'),
    );
    const nonce = _nonce();

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none';
             script-src 'nonce-${nonce}' https://cdn.jsdelivr.net;
             style-src ${webview.cspSource} 'unsafe-inline';
             img-src ${webview.cspSource} data:;
             connect-src 'none';" />
  <title>Blueprint Wiki</title>
  <link rel="stylesheet" href="${cssUri}" />
</head>
<body>
  <div id="root"></div>
  <script nonce="${nonce}" src="${bundleUri}"></script>
</body>
</html>`;
  }
}

function _nonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}
