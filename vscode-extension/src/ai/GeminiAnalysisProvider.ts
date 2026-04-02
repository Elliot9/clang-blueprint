/**
 * ai/GeminiAnalysisProvider.ts
 *
 * Implements IAnalysisProvider using the Google Gemini API.
 * Requires clangBlueprint.geminiApiKey to be set in VS Code settings.
 */

import { GoogleGenerativeAI, type Content } from '@google/generative-ai';
import type {
  IAnalysisProvider,
  ClassEntry,
  CallStep,
  ChatMessage,
  AnalysisSummary,
  RelevanceMatch,
} from '../shared/types';
import { LocalAnalysisProvider } from './LocalAnalysisProvider';

// Prefer newer models first; fall back to older ones for compatibility.
const FAST_MODEL_CANDIDATES = [
  'gemini-2.5-flash',
  'gemini-2.0-flash',
  'gemini-1.5-flash',
] as const;

const CHAT_MODEL_CANDIDATES = [
  'gemini-2.5-pro',
  'gemini-2.5-flash',
  'gemini-2.0-flash',
  'gemini-1.5-pro',
  'gemini-1.5-flash',
] as const;

// ---------------------------------------------------------------------------
// Helpers (shared with ClaudeAnalysisProvider logic)
// ---------------------------------------------------------------------------

function _classDigest(entry: ClassEntry): string {
  const lines: string[] = [
    `class ${entry.namespace ? entry.namespace + '::' : ''}${entry.className}`,
  ];
  lines.push(`  location: ${entry.fileLocation}:${entry.lineNumber}`);
  if (entry.responsibility) { lines.push(`  purpose: ${entry.responsibility}`); }
  if (entry.baseClasses.length)    { lines.push(`  extends: ${entry.baseClasses.join(', ')}`); }
  if (entry.dependencies.length) {
    const deps = entry.dependencies.map(d => `${d.target}(${d.type})`).join(', ');
    lines.push(`  dependencies: ${deps}`);
  }
  const ctors = entry.interfaces.filter(sig => sig.includes(`${entry.className}(`)).slice(0, 3);
  if (ctors.length) { lines.push(`  ctors: ${ctors.join(' | ')}`); }
  if (entry.interfaces.length) {
    const pub = entry.interfaces.slice(0, 8).join('; ');
    lines.push(`  public: ${pub}${entry.interfaces.length > 8 ? ' …' : ''}`);
  }
  if (entry.privateMethods?.length) {
    const priv = entry.privateMethods.slice(0, 6).map(m => m.signature).join('; ');
    lines.push(`  internal: ${priv}${entry.privateMethods.length > 6 ? ' …' : ''}`);
  }
  return lines.join('\n');
}

function _chainDigest(steps: CallStep[]): string {
  return steps.map(s => {
    if (s.targetClass === '_self_') {
      return s.isWrite ? `write ${s.member}` : `read ${s.member}`;
    }
    return s.kind === 'call'
      ? `${s.targetClass}::${s.member}()`
      : (s.isWrite ? `write ${s.targetClass}::${s.member}` : `read ${s.targetClass}::${s.member}`);
  }).join(' → ');
}

// ---------------------------------------------------------------------------
// GeminiAnalysisProvider
// ---------------------------------------------------------------------------

export class GeminiAnalysisProvider implements IAnalysisProvider {
  readonly providerId = 'gemini' as const;
  private readonly genAI: GoogleGenerativeAI;
  private readonly _local = new LocalAnalysisProvider();

  constructor(private readonly apiKey: string) {
    this.genAI = new GoogleGenerativeAI(apiKey);
  }

  async isAvailable(): Promise<boolean> {
    return this.apiKey.trim().length > 0;
  }

  // -------------------------------------------------------------------------
  // summarize
  // -------------------------------------------------------------------------

  async summarize(entry: ClassEntry, context?: ClassEntry[]): Promise<AnalysisSummary> {
    const contextDigest = (context ?? [])
      .filter(e => e.className !== entry.className)
      .slice(0, 12)
      .map(_classDigest)
      .join('\n\n');

    const prompt = [
      'Analyse this C++ class and return a JSON object with exactly these fields:',
      '  "intent": one sentence describing what the class does',
      '  "responsibilities": array of 3-6 concise bullet strings (no leading "- ")',
      '  "usedBy": array of class names from the context that use this class (empty array if none)',
      '  "dependsOn": array of class names this class directly depends on (from its dependencies list)',
      '  "notes": optional string with extra observations (template specialisations, deprecation, etc.)',
      '',
      '=== TARGET CLASS ===',
      _classDigest(entry),
      '',
      ...(contextDigest ? ['=== CONTEXT CLASSES ===', contextDigest, ''] : []),
      'Return ONLY valid JSON. No markdown fences.',
    ].join('\n');

    const text = await this._generateWithFallback(prompt, FAST_MODEL_CANDIDATES);

    try {
      const parsed = JSON.parse(text) as Partial<AnalysisSummary>;
      return {
        intent:           parsed.intent          ?? entry.responsibility ?? entry.className,
        responsibilities: Array.isArray(parsed.responsibilities) ? parsed.responsibilities : [],
        usedBy:           Array.isArray(parsed.usedBy)           ? parsed.usedBy           : [],
        dependsOn:        Array.isArray(parsed.dependsOn)        ? parsed.dependsOn        : [],
        notes:            parsed.notes,
      };
    } catch {
      // Gemini returned non-JSON — fall back to local
      return this._local.summarize(entry, context);
    }
  }

  // -------------------------------------------------------------------------
  // findRelevant — delegate to local TF-IDF (no API cost, sufficient quality)
  // -------------------------------------------------------------------------

  async findRelevant(query: string, all: ClassEntry[]): Promise<RelevanceMatch[]> {
    return this._local.findRelevant(query, all);
  }

  // -------------------------------------------------------------------------
  // explainChain
  // -------------------------------------------------------------------------

  async explainChain(steps: CallStep[], context: ClassEntry[]): Promise<string> {
    if (steps.length === 0) { return 'No call chain recorded for this method.'; }

    const chain = _chainDigest(steps);
    const classNames = [...new Set(steps.map(s => s.targetClass).filter(c => c !== '_self_'))];
    const ctxDigest = context
      .filter(e => classNames.includes(e.className))
      .map(_classDigest)
      .join('\n\n');

    const prompt = [
      'Explain this C++ method call chain in 1-2 plain-English sentences.',
      'Focus on what data flows and what the overall effect is.',
      '',
      `Call chain: ${chain}`,
      ...(ctxDigest ? ['', 'Involved classes:', ctxDigest] : []),
    ].join('\n');

    const text = await this._generateWithFallback(prompt, FAST_MODEL_CANDIDATES);
    return text.trim() || chain;
  }

  // -------------------------------------------------------------------------
  // locateAnchor
  // -------------------------------------------------------------------------

  async locateAnchor(errorLog: string, all: ClassEntry[]): Promise<ClassEntry[]> {
    if (!errorLog.trim()) { return []; }

    const localHits = await this._local.locateAnchor(errorLog, all);
    const candidates = localHits.length > 0 ? localHits : all.slice(0, 50);
    const nameList = candidates.map(e => e.className).join(', ');

    const prompt = [
      'Given this C++ error log, list the class names most likely involved.',
      'Choose ONLY from the provided candidate list.',
      'Return one class name per line, most relevant first, up to 8 classes.',
      'If none are relevant, return an empty response.',
      '',
      `Error log:\n${errorLog.slice(0, 1500)}`,
      '',
      `Candidate classes: ${nameList}`,
    ].join('\n');

    const text = await this._generateWithFallback(prompt, FAST_MODEL_CANDIDATES);

    const mentioned = new Set(
      text.split('\n')
        .map(l => l.trim().replace(/^[-*•\d.)\s]+/, ''))
        .filter(Boolean),
    );

    const matched = candidates.filter(e => mentioned.has(e.className));
    return matched.length > 0 ? matched : localHits.slice(0, 5);
  }

  // -------------------------------------------------------------------------
  // chat (streaming)
  // -------------------------------------------------------------------------

  async chat(
    messages: ChatMessage[],
    context: ClassEntry[],
    onChunk: (chunk: string) => void,
  ): Promise<void> {
    const ctxDigest = context
      .slice(0, 20)
      .map(_classDigest)
      .join('\n\n');

    const systemInstruction = [
      'You are an expert C++ code assistant integrated into the clang-blueprint VS Code extension.',
      'You help developers understand a C++ codebase by analysing its class structure.',
      '',
      'Guidelines:',
      '- Be concise. Prefer bullet points over long prose.',
      '- When referencing classes, use their exact names.',
      '- If asked about something outside the provided blueprint, say so clearly.',
      '',
      ...(ctxDigest
        ? ['Blueprint context (selected classes):', '```', ctxDigest, '```']
        : ['No class context provided — answer based on the conversation only.']),
    ].join('\n');

    // Convert ChatMessage[] → Gemini Content[] history (all but last message)
    const nonSystem = messages.filter(m => m.role !== 'system');
    const history: Content[] = nonSystem.slice(0, -1).map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    }));
    const lastMessage = nonSystem[nonSystem.length - 1]?.content ?? '';

    let lastError: unknown;
    for (const modelName of CHAT_MODEL_CANDIDATES) {
      try {
        const model = this.genAI.getGenerativeModel({
          model: modelName,
          systemInstruction,
        });
        const chatSession = model.startChat({ history });
        const result = await chatSession.sendMessageStream(lastMessage);

        for await (const chunk of result.stream) {
          const text = chunk.text();
          if (text) { onChunk(text); }
        }
        return;
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError ?? new Error('Gemini chat failed: no compatible model available.');
  }

  private async _generateWithFallback(
    prompt: string,
    models: readonly string[],
  ): Promise<string> {
    let lastError: unknown;
    for (const modelName of models) {
      try {
        const model = this.genAI.getGenerativeModel({ model: modelName });
        const result = await model.generateContent(prompt);
        return result.response.text();
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError ?? new Error('Gemini request failed: no compatible model available.');
  }
}
