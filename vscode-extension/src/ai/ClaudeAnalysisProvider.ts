/**
 * ai/ClaudeAnalysisProvider.ts — P15-02.
 *
 * Implements IAnalysisProvider using the Anthropic Claude API.
 * Requires clangBlueprint.claudeApiKey to be set in VS Code settings.
 */

import Anthropic from '@anthropic-ai/sdk';
import type {
  IAnalysisProvider,
  ClassEntry,
  CallStep,
  ChatMessage,
  AnalysisSummary,
  RelevanceMatch,
  ModuleEntry,
  ModuleEdge,
  EntryPoint,
  ModuleSummary,
} from '../shared/types';
import { LocalAnalysisProvider } from './LocalAnalysisProvider';

// Models: haiku for low-latency single-turn calls, sonnet for chat.
const HAIKU  = 'claude-haiku-4-5-20251001';
const SONNET = 'claude-sonnet-4-6';

// ---------------------------------------------------------------------------
// Helpers
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
// ClaudeAnalysisProvider
// ---------------------------------------------------------------------------

export class ClaudeAnalysisProvider implements IAnalysisProvider {
  readonly providerId = 'claude' as const;
  private readonly client: Anthropic;
  private readonly _local = new LocalAnalysisProvider();

  constructor(private readonly apiKey: string) {
    this.client = new Anthropic({ apiKey });
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

    const msg = await this.client.messages.create({
      model: HAIKU,
      max_tokens: 512,
      messages: [{ role: 'user', content: prompt }],
    });

    const text = msg.content[0].type === 'text' ? msg.content[0].text : '';
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
      // Claude returned non-JSON — fall back to local
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

    const msg = await this.client.messages.create({
      model: HAIKU,
      max_tokens: 200,
      messages: [{ role: 'user', content: prompt }],
    });

    return msg.content[0].type === 'text' ? msg.content[0].text.trim() : chain;
  }

  // -------------------------------------------------------------------------
  // locateAnchor
  // -------------------------------------------------------------------------

  async locateAnchor(errorLog: string, all: ClassEntry[]): Promise<ClassEntry[]> {
    if (!errorLog.trim()) { return []; }

    // First do cheap local filter to get a candidate shortlist
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

    const msg = await this.client.messages.create({
      model: HAIKU,
      max_tokens: 200,
      messages: [{ role: 'user', content: prompt }],
    });

    const text = msg.content[0].type === 'text' ? msg.content[0].text : '';
    const mentioned = new Set(
      text.split('\n')
        .map(l => l.trim().replace(/^[-*•\d.)\s]+/, ''))
        .filter(Boolean),
    );

    const result = candidates.filter(e => mentioned.has(e.className));
    // If Claude found nothing, fall back to local results
    return result.length > 0 ? result : localHits.slice(0, 5);
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

    const systemPrompt = [
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

    // Convert ChatMessage[] → Anthropic MessageParam[]
    const apiMessages: Anthropic.MessageParam[] = messages
      .filter(m => m.role !== 'system')
      .map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }));

    const stream = this.client.messages.stream({
      model: SONNET,
      max_tokens: 1024,
      system: systemPrompt,
      messages: apiMessages,
    });

    for await (const event of stream) {
      if (
        event.type === 'content_block_delta' &&
        event.delta.type === 'text_delta'
      ) {
        onChunk(event.delta.text);
      }
    }

    await stream.finalMessage();
  }

  // -------------------------------------------------------------------------
  // summarizeModule (P23)
  // -------------------------------------------------------------------------

  async summarizeModule(
    module: ModuleEntry,
    classes: ClassEntry[],
    neighborModules: ModuleEntry[],
  ): Promise<ModuleSummary> {
    const classSet = new Set(module.classNames);
    const modClasses = classes.filter(c => classSet.has(c.className));
    const classDigests = modClasses.slice(0, 15).map(_classDigest).join('\n\n');
    const neighborList = neighborModules.map(m => `${m.name} (${m.classNames.length} classes)`).join(', ');

    const prompt = [
      'Analyse this C++ module and return a JSON object with exactly these fields:',
      '  "intent": one sentence describing what this module does',
      '  "keyClasses": array of the 3-5 most important class names in this module',
      '  "interactions": array of 2-4 sentences describing how this module interacts with neighbors',
      '  "entryPath": the class name that is the best starting point for understanding this module',
      '  "notes": optional string with extra observations',
      '',
      `=== MODULE: ${module.name} (${module.classNames.length} classes) ===`,
      classDigests,
      '',
      ...(neighborList ? [`Neighbor modules: ${neighborList}`, ''] : []),
      'Return ONLY valid JSON. No markdown fences.',
    ].join('\n');

    try {
      const msg = await this.client.messages.create({
        model: HAIKU,
        max_tokens: 512,
        messages: [{ role: 'user', content: prompt }],
      });
      const text = msg.content[0].type === 'text' ? msg.content[0].text : '';
      const parsed = JSON.parse(text) as Partial<ModuleSummary>;
      return {
        intent: parsed.intent ?? module.summarySeed,
        keyClasses: Array.isArray(parsed.keyClasses) ? parsed.keyClasses : [],
        interactions: Array.isArray(parsed.interactions) ? parsed.interactions : [],
        entryPath: parsed.entryPath,
        notes: parsed.notes,
      };
    } catch {
      return this._local.summarizeModule(module, classes, neighborModules);
    }
  }

  // -------------------------------------------------------------------------
  // summarizeProject (P23)
  // -------------------------------------------------------------------------

  async summarizeProject(
    modules: ModuleEntry[],
    entryPoints: EntryPoint[],
  ): Promise<string> {
    const moduleList = modules
      .slice(0, 15)
      .map(m => `${m.name} (${m.classNames.length} classes): ${m.summarySeed.slice(0, 80)}`)
      .join('\n');
    const eps = entryPoints
      .filter(e => e.kind === 'main' || e.kind === 'hub')
      .slice(0, 5)
      .map(e => `${e.className} (${e.kind})`)
      .join(', ');

    const prompt = [
      'Summarize this C++ project in 1-3 sentences. Focus on what it does, not how.',
      '',
      `Modules:\n${moduleList}`,
      ...(eps ? [`\nKey entry points: ${eps}`] : []),
      '\nReturn ONLY the summary text, no JSON or markdown.',
    ].join('\n');

    try {
      const msg = await this.client.messages.create({
        model: HAIKU,
        max_tokens: 150,
        messages: [{ role: 'user', content: prompt }],
      });
      return msg.content[0].type === 'text' ? msg.content[0].text.trim() : '';
    } catch {
      return this._local.summarizeProject(modules, entryPoints);
    }
  }

  // -------------------------------------------------------------------------
  // explainArchitecture (P24-04)
  // -------------------------------------------------------------------------

  async explainArchitecture(
    modules: ModuleEntry[],
    moduleEdges: ModuleEdge[],
    focusModule?: string,
  ): Promise<string> {
    const sorted = [...modules].sort((a, b) => b.classNames.length - a.classNames.length);
    const moduleList = sorted
      .slice(0, 12)
      .map(m => `${m.name} (${m.classNames.length} classes): ${m.summarySeed.slice(0, 80)}`)
      .join('\n');
    const edgeList = [...moduleEdges]
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 15)
      .map(e => `${e.source} → ${e.target} (${e.weight} connections, ${e.depTypes?.join('/') ?? 'mixed'})`)
      .join('\n');

    const focusPart = focusModule
      ? `\nFocus your explanation on module "${focusModule}" and its relationships.`
      : '';

    const prompt = [
      'Explain the architecture of this C++ project in 2-4 paragraphs.',
      'Describe why the modules are structured this way, what the key relationships are,',
      'and what design patterns or architectural decisions are evident.',
      focusPart,
      '',
      `Modules:\n${moduleList}`,
      '',
      `Inter-module dependencies:\n${edgeList}`,
      '',
      'Return ONLY the explanation text, no JSON or markdown fences.',
    ].join('\n');

    try {
      const msg = await this.client.messages.create({
        model: HAIKU,
        max_tokens: 600,
        messages: [{ role: 'user', content: prompt }],
      });
      return msg.content[0].type === 'text' ? msg.content[0].text.trim() : '';
    } catch {
      return this._local.explainArchitecture(modules, moduleEdges, focusModule);
    }
  }
}
