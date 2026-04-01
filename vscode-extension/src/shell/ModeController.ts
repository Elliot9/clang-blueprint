/**
 * shell/ModeController.ts — Interface every mode controller must implement.
 *
 * AppShell holds exactly one active ModeController at a time.
 * Switching modes calls deactivate() on the old and activate() on the new.
 * All webview messages not consumed by AppShell are routed via handleMessage().
 */

import type * as vscode from 'vscode';
import type { WebviewToExtension } from '../shared/messages';

export interface ModeController {
  /** One-time setup. Called when the mode becomes active. */
  activate(panel: vscode.WebviewPanel): void;

  /** Tear-down. Called before switching to a different mode. */
  deactivate(): void;

  /**
   * Handle a message from the webview that AppShell didn't consume.
   * Return true if the message was handled, false to pass it on.
   */
  handleMessage(message: WebviewToExtension): boolean;
}
