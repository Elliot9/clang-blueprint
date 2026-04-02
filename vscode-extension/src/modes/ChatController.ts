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
  private static readonly CHAT_TIMEOUT_MS = 120_000;

  constructor(
    private readonly provider: IAnalysisProvider,
    private readonly allEntries: ClassEntry[],
    private readonly log?: (line: string) => void,
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
    this.log?.(`Chat request started. provider=${this.provider.providerId} textLen=${text.length} contextCount=${context.length}`);

    try {
      let assistantReply = '';
      const chatPromise = this.provider.chat(this.history, context, (chunk) => {
        assistantReply += chunk;
        this.panel?.webview.postMessage({ type: 'chatChunk', chunk });
      });
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('AI chat timed out.')), ChatController.CHAT_TIMEOUT_MS);
      });
      await Promise.race([chatPromise, timeoutPromise]);
      this.log?.(`Chat request completed. provider=${this.provider.providerId} replyLen=${assistantReply.length}`);
      // Record assistant reply in history for follow-up turns
      if (assistantReply.trim()) {
        this.history.push({ role: 'assistant', content: assistantReply });
      }
    } catch (err) {
      const errText = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
      this.log?.(`Chat request failed. provider=${this.provider.providerId} error=${errText}`);
      this.panel.webview.postMessage({
        type: 'extensionError',
        message: `Chat error: ${errText}`,
      });
    } finally {
      this.log?.('Chat request finalized (chatDone sent).');
      this.panel.webview.postMessage({ type: 'chatDone' });
    }
  }
}
