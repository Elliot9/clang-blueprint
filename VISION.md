# Product Vision

## Core Goal

Build an open-source intelligent code comprehension and collaboration ecosystem based on Blueprint, enabling AI Agents to understand and operate on C++ projects with **minimum token cost** and **maximum accuracy**, while allowing humans to **clearly grasp the full picture and every change without reading every line of code**.

---

## Problem Statement

Limitations of existing tools (e.g., DeepWiki):
- Require loading large amounts of source code each time, resulting in high token costs
- Structural relationships are approximated by LLM inference, lacking precision
- No coherent view from high-level design intent down to concrete class relationships
- Unable to effectively surface trade-offs and potential modification risks
- **AI output speed far exceeds human review capacity — humans lose understanding and control over the codebase**
- No persistent architectural change history that AI agents can reference across sessions

---

## Solution Positioning

**Blueprint complements tools like DeepWiki as foundational infrastructure, and serves as the bridge for humans to understand AI-generated output.**

| Layer | Responsible Party | Provides |
|-------|------------------|---------|
| Structural Facts | Blueprint (libclang AST) | Class relationships, dependencies, interfaces — 100% precise |
| Semantic Understanding | LLM (`blueprint enrich`) | Intent prose, design philosophy, trade-offs — committed to git, shared by team |
| Change Tracking | `blueprint diff` + git | Architectural change history — deterministic, no LLM |
| Execution & Reasoning | Pi Agent | Impact analysis, change planning, risk surfacing |
| **Human Comprehension** | **Wiki UI + Change Report** | **Clear presentation from high-level thinking to concrete implementation** |
| Human-Machine Interface | Terminal | Natural language command input |

---

## Primary Workflow

> AI-driven development, humans review and audit.

```
Pi Agent writes code
    ↓
blueprint scan          — updates blueprint_index.json (no LLM, ≤60s)
blueprint diff          — generates Change Report (no LLM, git-based)
git commit              — code + blueprint_index.json + blueprint_changes.json together
    ↓
Human opens PR          — reads Change Report to understand what AI changed structurally
Human opens Wiki        — browses class/module pages to understand full picture
    ↓
Next AI session         — reads blueprint_changes.json to know what was done previously
```

---

## Six Core Requirements

### 1. Blueprint as the Agent's Structural Memory
- Agent does not need to load the entire codebase each time
- Retrieves precise structural facts from Blueprint queries with minimal tokens
- Guaranteed correct by libclang AST — not approximated
- Agent reads `blueprint_changes.json` at session start to understand recent changes

### 2. Semantic Layer Integration — Three-Stage Pipeline

**Stage 1 — `blueprint scan` (always runs, no LLM)**
- libclang AST extraction: class relationships, dependencies, interfaces
- Heuristic enrichment: naming analysis → `intent`, structural pattern detection → `designPattern`, reverse-dep scoring → `changeRisk`
- Output: `blueprint_index.json` (committed to git)
- Performance target: full scan ≤ 60s, incremental ≤ 5s

**Stage 2 — `blueprint enrich` (manual, one-time per meaningful change, LLM)**
- Reads `blueprint_index.json` + original source files
- LLM generates rich prose for each class/module: detailed `intent`, `tradeoffs`, architecture notes
- Writes enriched fields back into `blueprint_index.json`
- Result is committed to git — **all team members share the prose, zero per-view token cost**
- LLM sees both source code and heuristic results (complete context)

**Stage 3 — `blueprint diff` (manual, no LLM)**
- Compares current `blueprint_index.json` with previous committed version via git
- Produces `blueprint_changes.json` — see §5 Change Report
- Committed to git alongside code changes

### 3. Human-Agent Collaboration Terminal Interface (Pi Agent)
- Humans issue natural language instructions via terminal
- Pi Agent queries Blueprint first to confirm impact scope and trade-offs before executing changes
- Agent reads `blueprint_changes.json` at session start for recent change context
- Incremental scan triggered automatically after modification — Blueprint stays in sync
- Fully traceable: every change maps to abstract intent and concrete class-level delta

### 4. Human Comprehension Layer
- AI output speed far exceeds human line-by-line review capacity — layered summaries are required
- Humans review AI changes via Change Report (structural facts) + Wiki UI (full context)
- **Goal: keep humans in control and informed, rather than blindly trusting AI output**

### 5. Change Report — Git-Integrated Architectural Audit Trail

**Design principles:**
- Triggered manually: `blueprint diff`
- Checks first: if no structural change since last committed version → "No changes"
- Content: AST diff + git metadata — **no LLM, 100% deterministic**
- Output: `blueprint_changes.json` — committed to git

**Report content:**
```
commit:  a3f9d2c
author:  Elliot Chen
date:    2026-04-09 14:32
message: "refactor error handling in DiskManager"

Added:
  + RetryPolicy (io/retry.cpp:12)  pattern: Strategy  risk: low

Modified:
  ~ DiskManager
      + method: readAsync(int lba, Callback cb)
      + method: writeAsync(int lba, Callback cb)
      ~ dependency: NVMeDriver  aggregation → composition
      changeRisk: low → HIGH  (reverse deps: 3 → 7)

Impact:
  Direct:   IoScheduler, FileSystem, BlockCache
  Indirect: RequestQueue, PageManager
```

**Why committed to git:**
- Human can review in PR — sees structural impact alongside code diff
- AI next session reads history without re-running diff
- Bug investigation: trace which commit introduced a high-risk structural change
- Serves as the formal record of "what the AI changed and why it matters"

### 6. Wiki UI — Browsable Knowledge Base

A DeepWiki-style interface built on AST-precise + LLM-enriched data, surfaced as a VS Code Webview Panel.

**Page hierarchy:**
```
System Overview  (project stats, entry points, module dependency graph)
  └── Module Page  (class list, internal class diagram, external deps)
        └── Class Page  (intent, design pattern, change risk, dependency diagram,
                         interfaces, used-by, source jump)
  └── Changes Page  (timeline of blueprint_changes.json entries)
```

**Wiki viewing never burns tokens** — all prose comes from committed `blueprint_index.json`.
LLM is only called during explicit `blueprint enrich` runs.

**Two separate VS Code Webview Panels, one data source:**
```
blueprint_index.json + blueprint_changes.json
  ├── Panel A: Graph View   — visual canvas, pan/zoom (existing)
  └── Panel B: Wiki View    — sidebar + pages + Mermaid + source jump (new)
```

**Technical stack:**
- Wiki Panel: Preact + esbuild (27KB bundle)
- Graph Panel: inline JS, no build step (unchanged)
- Both panels watch `blueprint_index.json` for live reload

---

## File Responsibilities

| File | Committed | Generated by | Content |
|------|-----------|-------------|---------|
| `blueprint_index.json` | ✅ | `scan` + `enrich` | Classes, modules, semantic fields |
| `blueprint_changes.json` | ✅ | `diff` | Change report history |
| `blueprint_graph.json` | optional | `scan` | Reverse dep graph for O(1) lookups |
| `.blueprint_cache.json` | ❌ | `scan` (incremental) | File hash cache |

---

## Language Support

**Current:** C++ (libclang AST)

**Future — architecture is already language-agnostic:**
- `blueprint_index.json` schema is language-neutral
- Semantic enricher, Wiki UI, Change Report, Pi Agent all operate on the schema
- Adding a new language = adding a new scanner only
- Candidates: Go, Rust, TypeScript (not current priority)

---

## Current Implementation Status

### Done ✅
- `blueprint scan`: libclang AST extraction, heuristic enrichment (`intent`, `designPattern`, `changeRisk`, `tradeoffs`), module grouping, entry point detection
- `blueprint enrich --llm`: class-level LLM enrichment (Anthropic / Gemini), hash-based cache, writes back to `blueprint_index.json`
- Wiki Panel (VS Code Webview): Sidebar, SystemPage, ModulePage, ClassPage, Mermaid diagrams, source jump
- `blueprint diff` CLI: not yet implemented
- Schema: `ClassEntry` semantic fields in place; module/project prose fields missing

### Direction A — LLM Narrative (Partially done)
| Sub-task | Status |
|----------|--------|
| Class-level heuristic enrichment | ✅ |
| Class-level LLM enrichment (`blueprint enrich --llm`) | ✅ |
| `ModuleEntry.summary` schema field | ❌ |
| `BlueprintIndex.projectSummary` schema field | ❌ |
| Module-level LLM summary generation | ❌ |
| Project-level LLM summary generation | ❌ |
| Class intent: richer prose (2–3 sentences, not ≤20 words) | ❌ |
| `SystemPage` project narrative section | ❌ |
| `ModulePage` module summary section | ❌ |

### Direction B — Change Report
| Sub-task | Status |
|----------|--------|
| `scanner/diff_engine.py` | ❌ |
| `blueprint diff` CLI command | ❌ |
| `blueprint_changes.json` schema + output | ❌ |
| Wiki Changes page | ❌ |

### Direction C — Pi Agent
| Sub-task | Status |
|----------|--------|
| Terminal natural language interface | ❌ |
| Blueprint context query for Agent | ❌ |
| Agent reads `blueprint_changes.json` at session start | ❌ |
| Post-modification scan + diff trigger | ❌ |

---

## Open Source Positioning

- Published on GitHub for developers to self-host
- No dependency on specific cloud services — can run fully local
- LLM provider is pluggable: Claude, Gemini, or local model

---

## Validation Strategy

Run a comparative experiment on a real project (Blueprint ecosystem vs DeepWiki alone):

| Metric | DeepWiki (control) | Blueprint + Pi (experiment) |
|--------|-------------------|----------------------------|
| Answer accuracy | Baseline | Target: higher |
| Token cost per query | Baseline | Target: lower |
| Structural relationship correctness | Approximate | 100% (AST-guaranteed) |
| Modification risk surfacing | None | Yes — changeRisk scoring |
| Human comprehension cost | Line-by-line review | Change Report + Wiki |
| Wiki accuracy | LLM-approximated | AST-precise + LLM-enriched |
| **Cross-session AI continuity** | **None** | **blueprint_changes.json** |
| **Team change communication** | **None** | **Committed audit trail** |

Experiment results will serve as the core evidence in the open-source project documentation.
