/**
 * extension.ts — Clang Blueprint VS Code extension entry point.
 *
 * Registers commands, opens the React Flow WebviewPanel, handles
 * node-click jump-to-file, and watches blueprint_index.json for changes.
 */

import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";

// ---------------------------------------------------------------------------
// Types mirroring the blueprint_index schema
// ---------------------------------------------------------------------------

interface Dependency {
  target: string;
  type: "composition" | "inheritance" | "association" | "dependency";
}

interface BlueprintEntry {
  className: string;
  responsibility: string;
  dependencies: Dependency[];
  /** Member fields: visibility (+/#/-) + type + name (from FIELD_DECL). */
  attributes?: string[];
  interfaces: string[];
  fileLocation: string;
  lineNumber: number;
  namespace: string;
  baseClasses: string[];
  templateParams: string[];
}

// Messages sent from extension → webview
type ExtensionMessage =
  | { type: "loadEntries"; entries: BlueprintEntry[]; totalCount?: number }
  | { type: "filter"; pattern: string }
  | { type: "highlight"; className: string }
  | { type: "layoutDirection"; direction: "TB" | "LR" | "BT" | "RL" };

// Messages sent from webview → extension
type WebviewMessage =
  | { type: "nodeClick"; fileLocation: string; lineNumber: number; className: string }
  | { type: "ready" }
  | { type: "error"; message: string };

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let diagramPanel: vscode.WebviewPanel | undefined;
let fileWatcher: vscode.FileSystemWatcher | undefined;
let cachedEntries: BlueprintEntry[] = [];          // T-34: for cursor-to-class lookup
let selectionDebounce: ReturnType<typeof setTimeout> | undefined;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getConfig<T>(key: string): T {
  return vscode.workspace.getConfiguration("clangBlueprint").get<T>(key) as T;
}

function getBlueprintIndexPath(workspaceRoot: string): string {
  const configPath = getConfig<string>("blueprintIndexPath");
  return path.isAbsolute(configPath)
    ? configPath
    : path.join(workspaceRoot, configPath);
}

function loadBlueprintEntries(indexPath: string): BlueprintEntry[] {
  try {
    if (!fs.existsSync(indexPath)) {
      return [];
    }
    const raw = fs.readFileSync(indexPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error("blueprint_index.json must be a JSON array");
    }
    return parsed as BlueprintEntry[];
  } catch (err) {
    vscode.window.showErrorMessage(`Clang Blueprint: Failed to load index: ${err}`);
    return [];
  }
}

function getWorkspaceRoot(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  return folders?.[0]?.uri.fsPath;
}

// ---------------------------------------------------------------------------
// WebviewPanel management
// ---------------------------------------------------------------------------

function getWebviewContent(
  webview: vscode.Webview,
  extensionUri: vscode.Uri
): string {
  // Load the self-contained HTML from the webview folder
  const htmlPath = vscode.Uri.joinPath(extensionUri, "webview", "index.html");
  try {
    const html = fs.readFileSync(htmlPath.fsPath, "utf-8");
    // Replace any local resource URIs if needed (CDN-only build doesn't need this)
    return html;
  } catch {
    // Inline fallback if the file isn't available
    return `<!DOCTYPE html>
<html>
<body style="background:#1e1e1e;color:#ccc;font-family:sans-serif;padding:2rem;">
  <h2>Clang Blueprint</h2>
  <p>Webview HTML not found. Build the extension first.</p>
</body>
</html>`;
  }
}

function createOrShowPanel(context: vscode.ExtensionContext): vscode.WebviewPanel {
  if (diagramPanel) {
    diagramPanel.reveal(vscode.ViewColumn.Beside);
    return diagramPanel;
  }

  diagramPanel = vscode.window.createWebviewPanel(
    "clangBlueprintDiagram",
    "Blueprint: Class Diagram",
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [
        vscode.Uri.joinPath(context.extensionUri, "webview"),
      ],
    }
  );

  diagramPanel.iconPath = vscode.ThemeIcon.File;
  diagramPanel.webview.html = getWebviewContent(
    diagramPanel.webview,
    context.extensionUri
  );

  // Handle messages from the webview
  diagramPanel.webview.onDidReceiveMessage(
    (message: WebviewMessage) => {
      switch (message.type) {
        case "ready":
          // Webview is ready — send the current entries
          sendEntriesToWebview(diagramPanel!, context);
          break;

        case "nodeClick":
          handleNodeClick(message.fileLocation, message.lineNumber, message.className);
          break;

        case "error":
          vscode.window.showErrorMessage(`Blueprint webview error: ${message.message}`);
          break;
      }
    },
    undefined,
    context.subscriptions
  );

  // Clean up when panel is closed
  diagramPanel.onDidDispose(
    () => {
      diagramPanel = undefined;
    },
    undefined,
    context.subscriptions
  );

  return diagramPanel;
}

function sendEntriesToWebview(
  panel: vscode.WebviewPanel,
  _context: vscode.ExtensionContext
): void {
  const root = getWorkspaceRoot();
  if (!root) {
    return;
  }
  const indexPath = getBlueprintIndexPath(root);
  const entries = loadBlueprintEntries(indexPath);
  const maxClasses = getConfig<number>("maxClassesInDiagram") ?? 100;
  const layoutDirection = getConfig<"TB" | "LR" | "BT" | "RL">("layoutDirection") ?? "TB";

  // For large codebases send all entries; webview applies its own view limit.
  // For very large sets (>5000) send only up to maxClasses to avoid postMessage
  // size limits — the webview filter/search handles focused navigation.
  const sendEntries = entries.length > 5000 ? entries.slice(0, maxClasses) : entries;
  const msg: ExtensionMessage = {
    type: "loadEntries",
    entries: sendEntries,
    totalCount: entries.length,
  };
  panel.webview.postMessage(msg);

  // Also send layout direction
  panel.webview.postMessage({
    type: "layoutDirection",
    direction: layoutDirection,
  } as ExtensionMessage);

  cachedEntries = entries; // T-34: keep local copy for cursor lookup

  if (entries.length === 0) {
    vscode.window.showWarningMessage(
      `Clang Blueprint: No entries found at ${indexPath}. Run "Blueprint: Rebuild Index" first.`
    );
  } else {
    panel.title = `Blueprint: Class Diagram (${entries.length} classes)`;
  }
}

// ---------------------------------------------------------------------------
// T-34: cursor → class lookup helper
// ---------------------------------------------------------------------------

function findClassAtCursor(
  document: vscode.TextDocument,
  position: vscode.Position
): BlueprintEntry | undefined {
  if (!cachedEntries.length) { return undefined; }
  const root = getWorkspaceRoot();
  if (!root) { return undefined; }

  const docAbs  = document.uri.fsPath;
  const curLine = position.line + 1; // convert to 1-based

  // Normalise separators for cross-platform comparison
  const norm = (p: string) => p.replace(/\\/g, "/");
  const docNorm = norm(docAbs);

  // Candidates: entries whose fileLocation resolves to the current file
  const candidates = cachedEntries.filter((e) => {
    const entryAbs = norm(
      path.isAbsolute(e.fileLocation)
        ? e.fileLocation
        : path.join(root, e.fileLocation)
    );
    return entryAbs === docNorm;
  });

  if (!candidates.length) { return undefined; }

  // Closest class definition line that is ≤ cursor position
  let best: BlueprintEntry | undefined;
  let bestDist = Infinity;
  for (const c of candidates) {
    const dist = curLine - c.lineNumber;
    if (dist >= 0 && dist < bestDist) {
      bestDist = dist;
      best = c;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Jump-to-definition
// ---------------------------------------------------------------------------

async function handleNodeClick(
  fileLocation: string,
  lineNumber: number,
  _className: string
): Promise<void> {
  const root = getWorkspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage("No workspace folder open.");
    return;
  }

  const absolutePath = path.isAbsolute(fileLocation)
    ? fileLocation
    : path.join(root, fileLocation);

  if (!fs.existsSync(absolutePath)) {
    vscode.window.showErrorMessage(
      `Blueprint: File not found: ${absolutePath}`
    );
    return;
  }

  try {
    const doc = await vscode.workspace.openTextDocument(absolutePath);
    const line = Math.max(0, lineNumber - 1); // VS Code uses 0-based lines
    const range = new vscode.Range(line, 0, line, 0);
    await vscode.window.showTextDocument(doc, {
      viewColumn: vscode.ViewColumn.One,
      selection: range,
      preserveFocus: false,
    });
    // Reveal the line in the editor
    const editor = vscode.window.visibleTextEditors.find(
      (e) => e.document.uri.fsPath === absolutePath
    );
    if (editor) {
      editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
      // Briefly highlight the line
      const decoration = vscode.window.createTextEditorDecorationType({
        backgroundColor: new vscode.ThemeColor("editor.findMatchHighlightBackground"),
        isWholeLine: true,
      });
      editor.setDecorations(decoration, [range]);
      setTimeout(() => decoration.dispose(), 2000);
    }
  } catch (err) {
    vscode.window.showErrorMessage(
      `Blueprint: Failed to open ${absolutePath}: ${err}`
    );
  }
}

// ---------------------------------------------------------------------------
// File watcher
// ---------------------------------------------------------------------------

function setupFileWatcher(context: vscode.ExtensionContext): void {
  // Dispose existing watcher
  fileWatcher?.dispose();

  const root = getWorkspaceRoot();
  if (!root) {
    return;
  }

  const indexRelPath = getConfig<string>("blueprintIndexPath");
  const pattern = new vscode.RelativePattern(root, indexRelPath);

  fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);

  const onIndexChanged = () => {
    const autoReload = getConfig<boolean>("autoReloadOnChange");
    if (!autoReload || !diagramPanel) {
      return;
    }
    // Debounce: wait 500ms after last change
    setTimeout(() => {
      if (diagramPanel) {
        sendEntriesToWebview(diagramPanel, context);
        vscode.window.setStatusBarMessage("$(refresh) Blueprint: diagram reloaded", 3000);
      }
    }, 500);
  };

  fileWatcher.onDidChange(onIndexChanged, undefined, context.subscriptions);
  fileWatcher.onDidCreate(onIndexChanged, undefined, context.subscriptions);

  context.subscriptions.push(fileWatcher);
}

// ---------------------------------------------------------------------------
// Extension activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  // T-39: measure activation time
  const _activationStart = Date.now();

  // Set up file watcher for auto-reload
  setupFileWatcher(context);

  // Re-create watcher when workspace config changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("clangBlueprint")) {
        setupFileWatcher(context);
      }
    })
  );

  // ---- Command: showDiagram ----
  context.subscriptions.push(
    vscode.commands.registerCommand("clangBlueprint.showDiagram", () => {
      const panel = createOrShowPanel(context);
      sendEntriesToWebview(panel, context);
    })
  );

  // ---- Command: jumpToDefinition ----
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "clangBlueprint.jumpToDefinition",
      async () => {
        const root = getWorkspaceRoot();
        if (!root) {
          vscode.window.showErrorMessage("No workspace folder open.");
          return;
        }
        const indexPath = getBlueprintIndexPath(root);
        const entries = loadBlueprintEntries(indexPath);
        if (entries.length === 0) {
          vscode.window.showWarningMessage("No blueprint entries loaded.");
          return;
        }

        // Quick pick from class names
        const items = entries.map((e) => ({
          label: e.className,
          description: e.namespace ? `${e.namespace}::${e.className}` : e.className,
          detail: `${e.fileLocation}:${e.lineNumber} — ${e.responsibility}`,
          entry: e,
        }));

        const picked = await vscode.window.showQuickPick(items, {
          placeHolder: "Search classes...",
          matchOnDescription: true,
          matchOnDetail: true,
        });

        if (picked) {
          await handleNodeClick(
            picked.entry.fileLocation,
            picked.entry.lineNumber,
            picked.entry.className
          );
        }
      }
    )
  );

  // ---- Command: rebuildIndex ----
  context.subscriptions.push(
    vscode.commands.registerCommand("clangBlueprint.rebuildIndex", async () => {
      const aiServerUrl = getConfig<string>("aiServerUrl");

      // Also trigger a Python scan if a terminal is available
      const root = getWorkspaceRoot();
      if (root) {
        const terminal = vscode.window.createTerminal("Blueprint Rebuild");
        terminal.show();
        terminal.sendText(`cd "${root}" && python -m scanner.main scan --project-root . --output blueprint_index.json`);
      }

      // Rebuild the AI server index
      const rebuildUrl = `${aiServerUrl}/rebuild-index`;
      vscode.window.setStatusBarMessage("$(sync~spin) Blueprint: rebuilding index...", 5000);

      try {
        /* eslint-disable @typescript-eslint/no-explicit-any */
        const { default: fetch } = await import("node-fetch" as any).catch(() => ({
          default: null,
        }));

        if (fetch) {
          const response = await (fetch as any)(rebuildUrl, { method: "POST" });
          /* eslint-disable @typescript-eslint/no-explicit-any */
          if ((response as any).ok) {
            const data = await (response as any).json();
            /* eslint-enable @typescript-eslint/no-explicit-any */
            vscode.window.showInformationMessage(
              `Blueprint: Index rebuilt — ${data.num_entries} entries in ${data.elapsed_ms}ms`
            );
          } else {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const status = (response as any).status as number;
            vscode.window.showWarningMessage(
              `Blueprint: AI server responded with ${status}. Index may be stale.`
            );
          }
        } else {
          vscode.window.showInformationMessage(
            "Blueprint: Scan started in terminal. Reload the diagram after completion."
          );
        }
      } catch (err) {
        vscode.window.showWarningMessage(
          `Blueprint: Could not reach AI server at ${aiServerUrl}. ` +
          `Run 'uvicorn ai_api.server:app' to enable AI queries.`
        );
      }
    })
  );

  // ---- Command: filterDiagram ----
  context.subscriptions.push(
    vscode.commands.registerCommand("clangBlueprint.filterDiagram", async () => {
      if (!diagramPanel) {
        vscode.window.showInformationMessage(
          "Open the diagram first with 'Blueprint: Show Class Diagram'."
        );
        return;
      }

      const pattern = await vscode.window.showInputBox({
        prompt: "Filter classes by name pattern (regex)",
        placeHolder: "e.g. Manager, ^Disk, .*Driver$",
      });

      if (pattern !== undefined) {
        diagramPanel.webview.postMessage({
          type: "filter",
          pattern,
        } as ExtensionMessage);
      }
    })
  );

  // ---- T-34: editor selection → webview highlight ----
  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorSelection((event) => {
      const doc = event.textEditor.document;
      // Only act on C/C++ files
      if (!["cpp", "c", "cxx"].includes(doc.languageId)) { return; }
      if (!diagramPanel) { return; }

      // Debounce: wait 300 ms after last cursor move
      if (selectionDebounce) { clearTimeout(selectionDebounce); }
      selectionDebounce = setTimeout(() => {
        const position = event.selections[0]?.active;
        if (!position) { return; }
        const entry = findClassAtCursor(doc, position);
        if (entry) {
          diagramPanel?.webview.postMessage({
            type: "highlight",
            className: entry.className,
          } as ExtensionMessage);
        }
      }, 300);
    })
  );

  // ---- T-35: highlightUpstream command ----
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "clangBlueprint.highlightUpstream",
      async () => {
        if (!diagramPanel) {
          vscode.window.showInformationMessage(
            "Open the diagram first with 'Blueprint: Show Class Diagram'."
          );
          return;
        }
        const className = await _pickClass("Highlight upstream callers of…");
        if (className) {
          diagramPanel.webview.postMessage({
            type: "highlightUpstream",
            className,
          });
        }
      }
    )
  );

  // ---- T-35: highlightDownstream command ----
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "clangBlueprint.highlightDownstream",
      async () => {
        if (!diagramPanel) {
          vscode.window.showInformationMessage(
            "Open the diagram first with 'Blueprint: Show Class Diagram'."
          );
          return;
        }
        const className = await _pickClass("Highlight downstream dependencies of…");
        if (className) {
          diagramPanel.webview.postMessage({
            type: "highlightDownstream",
            className,
          });
        }
      }
    )
  );

  // ---- Command: openSettings ----
  context.subscriptions.push(
    vscode.commands.registerCommand("clangBlueprint.openSettings", () => {
      vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "clangBlueprint"
      );
    })
  );

  // T-39: report activation time; warn if > 2000ms
  const _activationMs = Date.now() - _activationStart;
  console.log(`[clang-blueprint] Activated in ${_activationMs}ms`);
  if (_activationMs > 2000) {
    console.warn(
      `[clang-blueprint] Activation took ${_activationMs}ms — exceeds 2s target. ` +
      "Consider deferring heavy work until first command use."
    );
  }

  // Status bar item
  const statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBar.text = "$(type-hierarchy) Blueprint";
  statusBar.tooltip = "Show Clang Blueprint Diagram";
  statusBar.command = "clangBlueprint.showDiagram";
  statusBar.show();
  context.subscriptions.push(statusBar);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function _pickClass(placeholder: string): Promise<string | undefined> {
  if (!cachedEntries.length) {
    vscode.window.showWarningMessage("No blueprint entries loaded.");
    return undefined;
  }
  const items = cachedEntries.map((e) => ({
    label: e.className,
    description: e.namespace || "",
    detail: e.responsibility,
  }));
  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: placeholder,
    matchOnDescription: true,
  });
  return picked?.label;
}

export function deactivate(): void {
  if (selectionDebounce) { clearTimeout(selectionDebounce); }
  fileWatcher?.dispose();
  diagramPanel?.dispose();
}
