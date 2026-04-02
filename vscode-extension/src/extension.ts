/**
 * extension.ts — Clang Blueprint extension entry point.
 *
 * This file is intentionally thin: it registers VS Code commands and wires
 * them to AppShell. All business logic lives in shell/, modes/, and ai/.
 */

import * as vscode from 'vscode';
import { AppShell } from './shell/AppShell';

let shell: AppShell | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const activationStart = Date.now();

  shell = new AppShell(context);
  shell.setupWatcher();

  // Re-create watcher when workspace config changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('clangBlueprint')) {
        shell?.setupWatcher();
      }
    }),
  );

  // ---- showDiagram ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.showDiagram', () => {
      shell?.showDiagram();
    }),
  );

  // ---- jumpToDefinition ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.jumpToDefinition', () => {
      shell?.jumpToDefinition();
    }),
  );

  // ---- rebuildIndex ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.rebuildIndex', async () => {
      const cfg = vscode.workspace.getConfiguration('clangBlueprint');
      const aiServerUrl = cfg.get<string>('aiServerUrl') ?? '';
      const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

      if (root) {
        const excludePaths = cfg.get<string[]>('excludePaths') ?? [];
        const excludeArgs = excludePaths.map(p => `--exclude "${p}"`).join(' ');
        const terminal = vscode.window.createTerminal('Blueprint Rebuild');
        terminal.show();
        terminal.sendText(
          `cd "${root}" && python3 -m scanner.main scan --project-root . --output blueprint_index.json${excludeArgs ? ' ' + excludeArgs : ''}`,
        );
      }

      vscode.window.setStatusBarMessage('$(sync~spin) Blueprint: rebuilding index…', 5000);
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const { default: fetch } = await import('node-fetch' as any).catch(() => ({ default: null }));
        if (fetch) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const response = await (fetch as any)(`${aiServerUrl}/rebuild-index`, { method: 'POST' });
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          if ((response as any).ok) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const data = await (response as any).json();
            vscode.window.showInformationMessage(
              `Blueprint: Index rebuilt — ${data.num_entries} entries in ${data.elapsed_ms}ms`,
            );
          }
        } else {
          vscode.window.showInformationMessage('Blueprint: Scan started in terminal. Reload the diagram after completion.');
        }
      } catch {
        vscode.window.showWarningMessage(
          `Blueprint: Could not reach AI server at ${aiServerUrl}. Run 'uvicorn ai_api.server:app' to enable AI queries.`,
        );
      }
    }),
  );

  // ---- filterDiagram ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.filterDiagram', () => {
      shell?.filterDiagram();
    }),
  );

  // ---- highlightUpstream / highlightDownstream ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.highlightUpstream', () => {
      shell?.highlightUpstream();
    }),
    vscode.commands.registerCommand('clangBlueprint.highlightDownstream', () => {
      shell?.highlightDownstream();
    }),
  );

  // ---- openSettings ----
  context.subscriptions.push(
    vscode.commands.registerCommand('clangBlueprint.openSettings', () => {
      vscode.commands.executeCommand('workbench.action.openSettings', 'clangBlueprint');
    }),
  );

  // ---- Cursor tracking (T-34) ----
  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorSelection(event => {
      const doc = event.textEditor.document;
      if (!['cpp', 'c', 'cxx', 'h', 'hpp'].includes(doc.languageId)) { return; }
      const position = event.selections[0]?.active;
      if (position) { shell?.onCursorMove(doc, position); }
    }),
  );

  // ---- Status bar ----
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.text = '$(type-hierarchy) Blueprint';
  statusBar.tooltip = 'Show Clang Blueprint Diagram';
  statusBar.command = 'clangBlueprint.showDiagram';
  statusBar.show();
  context.subscriptions.push(statusBar);

  const ms = Date.now() - activationStart;
  console.log(`[clang-blueprint] Activated in ${ms}ms`);
  if (ms > 2000) {
    console.warn(`[clang-blueprint] Activation took ${ms}ms — exceeds 2s target.`);
  }
}

export function deactivate(): void {
  shell?.dispose();
  shell = undefined;
}
