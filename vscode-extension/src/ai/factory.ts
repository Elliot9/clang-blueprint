/**
 * ai/factory.ts — Provider factory (P15-04).
 *
 * Creates the active IAnalysisProvider based on VS Code settings.
 * Falls back to LocalAnalysisProvider when:
 *   - setting is 'local', OR
 *   - setting is 'claude' but no API key is configured
 */

import * as vscode from 'vscode';
import type { IAnalysisProvider } from '../shared/types';
import { LocalAnalysisProvider } from './LocalAnalysisProvider';
import { ClaudeAnalysisProvider } from './ClaudeAnalysisProvider';

export async function createProvider(): Promise<IAnalysisProvider> {
  const cfg = vscode.workspace.getConfiguration('clangBlueprint');
  const providerSetting = cfg.get<string>('analysisProvider') ?? 'local';
  const apiKey = cfg.get<string>('claudeApiKey') ?? '';

  if (providerSetting === 'claude') {
    const claude = new ClaudeAnalysisProvider(apiKey);
    if (await claude.isAvailable()) {
      return claude;
    }
    vscode.window.showWarningMessage(
      'Clang Blueprint: Claude API key not set. Falling back to local analysis. ' +
      'Set clang-blueprint.claudeApiKey in settings to enable AI features.',
    );
  }

  return new LocalAnalysisProvider();
}
