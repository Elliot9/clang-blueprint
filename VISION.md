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

---

## Solution Positioning

**Blueprint complements tools like DeepWiki as foundational infrastructure, and serves as the bridge for humans to understand AI-generated output.**

| Layer | Responsible Party | Provides |
|-------|------------------|---------|
| Structural Facts | Blueprint (libclang AST) | Class relationships, dependencies, interfaces — 100% precise |
| Semantic Understanding | LLM | Intent, design philosophy, trade-offs |
| Execution & Reasoning | Pi Agent | Impact analysis, change planning, risk surfacing |
| **Human Comprehension** | **Blueprint visualization + change narrative** | **Clear presentation from high-level thinking to concrete implementation** |
| Human-Machine Interface | Terminal | Natural language command input |

---

## Five Core Requirements

### 1. Blueprint as the Agent's Structural Memory
- Agent does not need to load the entire codebase each time
- Retrieves precise structural facts from Blueprint queries with minimal tokens
- Guaranteed correct by libclang AST — not approximated

### 2. Semantic Layer Integration
- Blueprint schema extended with new fields: `intent`, `tradeoffs`, `changeRisk`, `designPattern`
- First pass: heuristic inference (naming analysis, comment extraction, structural pattern detection) — zero cost
- Second pass: LLM fills in only what heuristics cannot determine (ambiguous intent, cross-file design philosophy)
- Incrementally updated — only re-analyzes classes affected by code changes

### 3. Human-Agent Collaboration Terminal Interface (Pi Agent)
- Humans issue natural language instructions via terminal
- Pi Agent queries Blueprint first to confirm impact scope and trade-offs before executing changes
- Incremental scan triggered automatically after modification — Blueprint stays in sync
- Fully traceable: every change maps back to abstract intent and concrete class-level delta

### 4. Human Comprehension Layer
- AI output speed far exceeds human line-by-line review capacity — layered summaries are required
- After each Agent modification, a change report is automatically generated:
  - **Why**: the intent behind this change
  - **What changed (high-level)**: which modules and design decisions were affected
  - **What changed (concrete)**: which classes, interfaces, and dependency relationships changed
  - **Risk**: potential issues and trade-off reminders
- Humans do not need to read every diff — Blueprint's hierarchical structure enables meaningful judgment
- **Goal: keep humans in control and informed, rather than blindly trusting AI output**

### 5. Wiki UI — Browsable Knowledge Base
A DeepWiki-style interface built on top of Blueprint's AST-precise + LLM-enriched data, surfaced as a VS Code Webview Panel.

**Page hierarchy:**
```
System Overview
  └── Module Page (per namespace / module)
        └── Class Page (per class)
```

**Each page contains:**
- Intent and responsibility description
- Design pattern annotation
- Dependency relationship diagram (Mermaid, AST-guaranteed accurate)
- Interface list with signatures
- Trade-offs and change risk
- Direct link to source file and line number

**Two separate VS Code Webview Panels, one data source:**
```
blueprint_index.json
  ├── Panel A: Graph View   — visual canvas, pan/zoom, class relationship diagram (existing)
  └── Panel B: Wiki View    — sidebar navigation + paginated wiki + Markdown + Mermaid (new)
```

**Technical direction for Wiki Panel:**
- Introduces a build step (esbuild) for the wiki webview only
- Enables use of npm packages: React (or Preact), `marked`, `mermaid`
- Graph View panel retains its current no-build-step, inline JS approach
- Both panels are driven by the same `blueprint_index.json` — single source of truth
- Wiki pages auto-regenerate when Blueprint is updated after a code change

---

## Open Source Positioning

- Published on GitHub for C++ developers to self-host
- No dependency on specific cloud services — can run fully local

---

## Validation Strategy

Run a comparative experiment on a real project:

| Metric | DeepWiki (control) | Blueprint + Pi (experiment) |
|--------|-------------------|----------------------------|
| Answer accuracy | Baseline | Target: higher |
| Token cost per query | Baseline | Target: lower |
| Structural relationship correctness | Approximate | 100% (AST-guaranteed) |
| Modification risk surfacing | None | Yes |
| **Human comprehension cost** | **Requires line-by-line review** | **Layered summary — grasp quickly** |
| **Wiki / knowledge base** | **Generated by LLM (approximated)** | **AST-precise + LLM-enriched (accurate)** |

Experiment results will serve as the core evidence in the open-source project documentation.
