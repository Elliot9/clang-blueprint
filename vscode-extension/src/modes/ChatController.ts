/**
 * modes/ChatController.ts — P16-04.
 *
 * Handles Chat Mode: conversation history, context class management,
 * streaming AI responses.
 */

import type * as vscode from 'vscode';
import type { ModeController } from '../shell/ModeController';
import type { WebviewToExtension } from '../shared/messages';
import type { IAnalysisProvider, ClassEntry, ChatMessage } from '../shared/types';
import { buildChatContext } from '../analysis/context';

export class ChatController implements ModeController {
  private panel: vscode.WebviewPanel | undefined;
  private history: ChatMessage[] = [];

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
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
      case 'chatMessage':
        this._handleChat(message.text, message.selectedClasses);
        return true;
      case 'contextUpdate':
        // Context is sent with each message; no server-side state needed.
        return true;
      default:
        return false;
    }
  }

  private async _handleChat(text: string, contextNames: string[]): Promise<void> {
    if (!this.panel) { return; }

    // Append user message to history
    this.history.push({ role: 'user', content: text });

    // Build rich context: selected classes + their direct deps
    const context = buildChatContext(contextNames, this.allEntries);

    try {
      let assistantReply = '';
      await this.provider.chat(this.history, context, (chunk) => {
        assistantReply += chunk;
        this.panel?.webview.postMessage({ type: 'chatChunk', chunk });
      });
      // Record assistant reply in history for follow-up turns
      this.history.push({ role: 'assistant', content: assistantReply });
      this.panel.webview.postMessage({ type: 'chatDone' });
    } catch (err) {
      this.panel.webview.postMessage({
        type: 'extensionError',
        message: `Chat error: ${err}`,
      });
    }
  }
}
