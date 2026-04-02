/**
 * ai/factory.ts — Provider factory (P15-04).
 *
 * Creates the active IAnalysisProvider based on VS Code settings.
 * Falls back to LocalAnalysisProvider when:
 *   - setting is 'local', OR
 *   - setting is 'claude' but no API key is configured, OR
 *   - setting is 'gemini' but no API key is configured
 */

import * as vscode from 'vscode';
import type { IAnalysisProvider } from '../shared/types';
import { LocalAnalysisProvider } from './LocalAnalysisProvider';
import { ClaudeAnalysisProvider } from './ClaudeAnalysisProvider';
import { GeminiAnalysisProvider } from './GeminiAnalysisProvider';

export async function createProvider(): Promise<IAnalysisProvider> {
  const cfg = vscode.workspace.getConfiguration('clangBlueprint');
  const providerSetting = cfg.get<string>('analysisProvider') ?? 'local';

  if (providerSetting === 'claude') {
    const apiKey = cfg.get<string>('claudeApiKey') ?? '';
    const claude = new ClaudeAnalysisProvider(apiKey);
    if (await claude.isAvailable()) {
      return claude;
    }
    vscode.window.showWarningMessage(
      'Clang Blueprint: Claude API key not set. Falling back to local analysis. ' +
      'Set clangBlueprint.claudeApiKey in settings to enable AI features.',
    );
  }

  if (providerSetting === 'gemini') {
    const apiKey = cfg.get<string>('geminiApiKey') ?? '';
    const gemini = new GeminiAnalysisProvider(apiKey);
    if (await gemini.isAvailable()) {
      return gemini;
    }
    vscode.window.showWarningMessage(
      'Clang Blueprint: Gemini API key not set. Falling back to local analysis. ' +
      'Set clangBlueprint.geminiApiKey in settings to enable AI features.',
    );
  }

  return new LocalAnalysisProvider();
}
