# Implementation Roadmap

Phased delivery plan toward a complete Blueprint + Pi Agent ecosystem.
See [VISION.md](./VISION.md) for architecture rationale and design decisions.

---

## Phase 1 — Direction A: Complete LLM Narrative Layer

> Goal: Wiki becomes a genuine knowledge base with rich prose, not just structured metadata.
> Viewing the wiki never burns tokens — all prose is pre-generated and committed to git.

### 1A — Schema Extension
- [ ] Add `summary: string` to `ModuleEntry` (types.ts + wiki-webview/src/types.ts)
- [ ] Add `projectSummary: string` to `BlueprintIndex` (types.ts + wiki-webview/src/types.ts)
- [ ] Bump index version to v4 in scanner/main.py

### 1B — Enrich Command Extension
- [ ] Upgrade class-level LLM prompt: generate 2–3 sentence `intent` (currently ≤20 words)
- [ ] Add module-level LLM summary generation in `semantic_enricher.py`
  - Input: module name, class list, `summarySeed`, internal/external deps
  - Output: `summary` written back to each `ModuleEntry`
- [ ] Add project-level LLM summary generation in `semantic_enricher.py`
  - Input: module list, entry points, total class/dep counts
  - Output: `projectSummary` written to `BlueprintIndex` root
- [ ] All results written atomically back to `blueprint_index.json` (committed to git)
- [ ] Hash-based cache covers module + project summaries (keyed by module content hash)

### 1C — Wiki UI Prose Sections
- [ ] `SystemPage`: add project narrative paragraph below title (renders `index.projectSummary`)
- [ ] `ModulePage`: add module summary paragraph in header area (renders `mod.summary`)
- [ ] `ClassPage`: render `intent` as a paragraph (currently a short quoted line)
- [ ] Rebuild wiki bundle: `npm run build:wiki`

---

## Phase 2 — Direction B: Change Report

> Goal: Every AI-generated code change is accompanied by a deterministic architectural audit trail.
> `blueprint_changes.json` is committed to git — humans review it in PR, Agent reads it next session.

### 2A — Diff Engine (`scanner/diff_engine.py`)
- [ ] `load_index_from_git(ref)` — read `blueprint_index.json` from a specific git ref
- [ ] `diff_classes(old, new)` — detect added / removed / modified `ClassEntry` records
  - Track: interface changes, dependency type changes, new/removed deps, risk level changes
- [ ] `diff_modules(old, new)` — detect added / removed / modified `ModuleEntry` records
- [ ] `compute_impact(changed_classes, index)` — identify direct + indirect downstream dependents
- [ ] `build_change_record(git_meta, class_diffs, module_diffs, impact)` — assemble full record

### 2B — CLI Command (`blueprint diff`)
- [ ] Add `cmd_diff` to `scanner/main.py`
- [ ] Arguments: `--from` (git ref, default `HEAD`), `--to` (default working tree), `--output`
- [ ] Check: if no structural change → print "No structural changes" and exit 0
- [ ] On change: generate record, append to `blueprint_changes.json`, print summary to stdout
- [ ] Wire into `build_parser()` dispatch table

### 2C — `blueprint_changes.json` Schema
```json
{
  "version": 1,
  "changes": [
    {
      "commit": "a3f9d2c",
      "author": "Elliot Chen",
      "date": "2026-04-09T14:32:00Z",
      "message": "refactor error handling in DiskManager",
      "added": [
        { "className": "RetryPolicy", "designPattern": "Strategy", "changeRisk": "low" }
      ],
      "removed": [],
      "modified": [
        {
          "className": "DiskManager",
          "interfaceChanges": { "added": ["readAsync", "writeAsync"], "removed": [] },
          "depChanges": [{ "target": "NVMeDriver", "from": "aggregation", "to": "composition" }],
          "riskChange": { "from": "low", "to": "high" }
        }
      ],
      "impact": {
        "direct": ["IoScheduler", "FileSystem", "BlockCache"],
        "indirect": ["RequestQueue", "PageManager"]
      }
    }
  ]
}
```

### 2D — Git Hook (optional, both modes supported)
- [ ] `scripts/install-hooks.sh` — installs `post-commit` hook
- [ ] Hook: runs `blueprint diff` after each commit if `blueprint_index.json` exists
- [ ] Manual mode always available: `blueprint diff`

### 2E — Wiki Changes Page
- [ ] Add `ChangesPage.tsx` to wiki-webview
- [ ] Display timeline of entries from `blueprint_changes.json`
- [ ] Each entry: commit info, added/modified/removed class counts, expandable impact list
- [ ] Click on class name → navigate to ClassPage
- [ ] Add "Changes" entry to Sidebar navigation
- [ ] Update `WikiPanel.ts` to also load and send `blueprint_changes.json`
- [ ] Update `types.ts` with `ChangeRecord` + `BlueprintChanges` interfaces
- [ ] Rebuild wiki bundle

---

## Phase 3 — Direction C: Pi Agent Terminal Interface

> Goal: AI-driven development with humans reviewing via Blueprint.
> Agent uses Blueprint as structural memory — minimal tokens, maximum precision.

### 3A — Blueprint Query API (extend `ai_api/server.py`)
- [ ] `GET /context/class/{name}` — return class entry + reverse deps + recent changes
- [ ] `GET /context/module/{name}` — return module summary + classes + ext deps
- [ ] `GET /changes/recent?n=10` — return last N change records from `blueprint_changes.json`
- [ ] `POST /impact` — given a list of class names, return full impact analysis

### 3B — Terminal Agent Interface (`agent/pi_agent.py`)
- [ ] Natural language command parsing (via LLM)
- [ ] Pre-execution: query Blueprint for impact scope, surface trade-offs and risks
- [ ] Confirmation prompt: show impact to human before executing
- [ ] Post-execution: trigger `blueprint scan --incremental` + `blueprint diff`
- [ ] Session init: load recent `blueprint_changes.json` entries as context

### 3C — Agent Memory & Context
- [ ] At session start, read last N change records for continuity
- [ ] Maintain within-session change log (what has this agent done this session)
- [ ] After each modification: update in-session log, trigger incremental scan

---

## Future — Multi-Language Support

> Architecture is already language-agnostic at the schema level.
> Only the scanner layer is language-specific.

| Language | Scanner Approach | Priority |
|----------|-----------------|---------|
| Go | `go/ast` stdlib | Candidate |
| Rust | `syn` crate via subprocess | Candidate |
| TypeScript | TypeScript compiler API | Candidate |

All future scanners output the same `blueprint_index.json` schema.
Wiki, Change Report, and Pi Agent require zero changes.

---

## File Ownership Summary

| File | Phase | Committed to git |
|------|-------|-----------------|
| `blueprint_index.json` | 1 (enrich) | ✅ |
| `blueprint_changes.json` | 2 (diff) | ✅ |
| `blueprint_graph.json` | existing | optional |
| `.blueprint_cache.json` | existing | ❌ |
| `.blueprint_semantic_cache.json` | existing | ❌ |
