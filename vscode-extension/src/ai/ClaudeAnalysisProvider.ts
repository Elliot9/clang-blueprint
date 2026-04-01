/**
 * ai/ClaudeAnalysisProvider.ts — Stub for P15-02.
 *
 * Implements IAnalysisProvider by calling the Claude API.
 * Requires clang-blueprint.claudeApiKey to be set in VS Code settings.
 * Falls back gracefully when the key is absent.
 */

import type {
  IAnalysisProvider,
  ClassEntry,
  CallStep,
  ChatMessage,
  AnalysisSummary,
  RelevanceMatch,
} from '../shared/types';

export class ClaudeAnalysisProvider implements IAnalysisProvider {
  readonly providerId = 'claude' as const;

  constructor(private readonly apiKey: string) {}

  async isAvailable(): Promise<boolean> {
    return this.apiKey.trim().length > 0;
  }

  async summarize(_entry: ClassEntry, _context?: ClassEntry[]): Promise<AnalysisSummary> {
    // TODO P15-02: structured prompt → Claude API
    throw new Error('ClaudeAnalysisProvider.summarize not yet implemented (P15-02)');
  }

  async findRelevant(_query: string, _all: ClassEntry[]): Promise<RelevanceMatch[]> {
    // TODO P15-02: semantic search via Claude embeddings or structured prompt
    throw new Error('ClaudeAnalysisProvider.findRelevant not yet implemented (P15-02)');
  }

  async explainChain(_steps: CallStep[], _context: ClassEntry[]): Promise<string> {
    // TODO P15-02: narrate the call chain in natural language
    throw new Error('ClaudeAnalysisProvider.explainChain not yet implemented (P15-02)');
  }

  async locateAnchor(_errorLog: string, _all: ClassEntry[]): Promise<ClassEntry[]> {
    // TODO P15-02: ask Claude to identify classes from the error log
    throw new Error('ClaudeAnalysisProvider.locateAnchor not yet implemented (P15-02)');
  }

  async chat(
    _messages: ChatMessage[],
    _context: ClassEntry[],
    _onChunk: (chunk: string) => void,
  ): Promise<void> {
    // TODO P15-02: streaming Claude API call with token budget management
    throw new Error('ClaudeAnalysisProvider.chat not yet implemented (P15-02)');
  }
}
