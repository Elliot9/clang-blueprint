# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Full scan of a C++ project
python -m scanner.main scan --project-root <dir> --output blueprint_index.json

# Incremental scan (only re-parses changed files)
python -m scanner.main scan --project-root <dir> --incremental

# Semantic enrichment — heuristic only (no API key needed)
python -m scanner.main enrich --input blueprint_index.json

# Semantic enrichment — full LLM (requires ANTHROPIC_API_KEY or GEMINI_API_KEY)
# Writes intent/tradeoffs/changeRisk/designPattern on each class,
# plus module.summary and projectSummary; bumps version to 4
python -m scanner.main enrich --input blueprint_index.json --llm

# Architectural diff (append ChangeRecord to blueprint_changes.json)
python -m scanner.main diff                        # working-tree vs HEAD
python -m scanner.main diff --from HEAD~1 --to HEAD  # two git refs

# Install git post-commit hook (auto-runs blueprint diff after every commit)
bash scripts/install-hooks.sh

# Generate class diagram (.mmd file)
python -m scanner.main diagram --type class --input blueprint_index.json

# Generate sequence diagram from GDB backtrace
python -m scanner.main diagram --type sequence --gdb-backtrace trace.txt

# Start AI query server
uvicorn ai_api.server:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_ast_parser.py -v

# Run a single test
pytest tests/test_ast_parser.py::test_unique_ptr_is_composition -v

# Build VS Code extension host
cd vscode-extension && npm install && npm run compile

# Build Wiki webview bundle (esbuild + Preact)
cd vscode-extension && npm run build:wiki

# Watch Wiki webview (dev)
cd vscode-extension && npm run watch:wiki
```

## Architecture

### Three-stage pipeline

```
C++ source files
  → scanner/ast_parser.py        (libclang AST walk, ≤60s for 100k LOC)
  → blueprint_index.json v3      (ClassEntry array + modules + entryPoints)

blueprint_index.json v3
  → scanner/semantic_enricher.py (heuristic: always; LLM: opt-in via --llm)
  → blueprint_index.json v4      (adds intent, tradeoffs, changeRisk,
                                   designPattern, module.summary, projectSummary)
  → .blueprint_semantic_cache.json (local, not committed; keyed by structural hash)

blueprint_index.json (committed to git)
  → scanner/diff_engine.py       (pure AST diff, no LLM)
  → blueprint_changes.json       (ChangeRecord log, committed to git)

blueprint_index.json + blueprint_changes.json
  → vscode-extension/WikiPanel   (DeepWiki-style browsable wiki)
  → vscode-extension/AppShell    (interactive diagram canvas)
```

### scanner/ — Python

- **ast_parser.py** — Core parser. `ASTVisitor` walks a libclang `TranslationUnit`, extracts `BlueprintEntry` dataclasses. Dependency types: `composition` (direct member/unique_ptr), `aggregation` (shared_ptr/weak_ptr/raw ptr), `inheritance` (base specifier), `association` (method param/return), `dependency` (local var). Entry point: `parse_files(files, project_root)` and `scan_directory(root)`.
- **incremental.py** — SHA256-based cache in `.blueprint_cache.json`. Only re-parses files whose hash changed. Atomic writes via `tempfile + os.replace()`. Entry point: `incremental_scan(project_root)`.
- **semantic_enricher.py** — Two tiers: `enrich_all_heuristic()` (CamelCase split + verb templates + pattern keywords, always runs after scan); `enrich_index_llm()` (Anthropic/Gemini, opt-in, cached). Also generates `module.summary` via `enrich_modules_llm()` and `projectSummary` via `enrich_project_llm()`.
- **diff_engine.py** — Deterministic architectural diff. `load_index_from_git(ref)` reads index from any git ref. `diff_classes` / `diff_modules` produce structured added/removed/modified records. `compute_impact` BFS on reverse dep graph (up to 3 hops). `diff_indices` is the main entry point; returns `None` when no structural changes.
- **module_grouper.py** — Groups classes into modules by directory heuristic, computes `internalEdgeCount` and `externalDeps`.
- **entry_detector.py** — Identifies entry point classes (hub nodes, `main`, servers) from the graph.
- **graph_builder.py** — Builds `blueprint_graph.json` with forward and reverse dependency maps.
- **mermaid_generator.py** — Converts blueprint entries → Mermaid `classDiagram`; call graph dicts → `sequenceDiagram`; parses GDB backtraces via `parse_gdb_backtrace()`.
- **main.py** — `argparse` CLI: `scan`, `enrich`, `diff`, `diagram`, `cache-stats` subcommands.

### ai_api/ — Python + FastAPI

- **indexer.py** — `BlueprintIndexer`: TF-IDF over CamelCase-expanded text. `build(entries)`, `query(text, top_k)`, persists to `.blueprint_tfidf.pkl`.
- **server.py** — FastAPI. `POST /query`, `POST /rebuild-index`, `GET /health`. Config via env vars: `BLUEPRINT_INDEX_PATH`, `TFIDF_INDEX_PATH`, `MAX_TOP_K`.

### vscode-extension/ — TypeScript

- **src/extension.ts** — Registers commands. Creates `WikiPanel` and `AppShell` (diagram). Watches `blueprint_index.json` via `createFileSystemWatcher`.
- **src/shell/WikiPanel.ts** — DeepWiki-style wiki panel. Loads `blueprint_index.json` and `blueprint_changes.json`; watches both for live-reload; handles `jumpToSource` postMessage → opens file at line beside panel.
- **wiki-webview/** — Preact + esbuild SPA bundled to `dist/bundle.js` + `dist/bundle.css`.
  - `src/pages/SystemPage.tsx` — Overview: stats, entry points, module dependency graph (Mermaid).
  - `src/pages/ModulePage.tsx` — Module detail: summary prose, external deps, class diagram, class table.
  - `src/pages/ClassPage.tsx` — Class detail: intent, dependency diagram, interfaces, base classes, deps, used-by, attributes.
  - `src/pages/ChangesPage.tsx` — Change Report: collapsible ChangeRecord cards (newest-first), diff detail, impact chips.
  - `src/components/Sidebar.tsx` — Project tree with search; "Change Report" nav item (visible only when `blueprint_changes.json` present).

### blueprint_index.json schema (v4)

```json
{
  "version": 4,
  "projectName": "MyProject",
  "projectSummary": "...",
  "modules": [{
    "name": "Storage",
    "classNames": ["DiskManager"],
    "summary": "...",
    "internalEdgeCount": 3,
    "externalDeps": [{ "target": "Network", "weight": 2, "depTypes": ["association"] }]
  }],
  "moduleEdges": [{ "source": "Storage", "target": "Network", "weight": 2 }],
  "entryPoints": [{ "className": "Server", "kind": "server", "reason": "..." }],
  "classes": [{
    "className": "DiskManager",
    "responsibility": "Resource Lifecycle",
    "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
    "interfaces": ["void readBlock(int lba, char * buf)"],
    "fileLocation": "src/core/disk_mgr.cpp",
    "lineNumber": 42,
    "namespace": "core",
    "baseClasses": ["IoBase"],
    "templateParams": [],
    "intent": "Orchestrates raw NVMe I/O with cache write-through.",
    "designPattern": "Facade",
    "changeRisk": "high",
    "tradeoffs": ["Tight coupling to NVMeDriver limits portability"]
  }]
}
```

### blueprint_changes.json schema (v1)

```json
{
  "version": 1,
  "records": [{
    "commit": "a1b2c3d4",
    "author": "Alice",
    "date": "2026-04-09T10:00:00+00:00",
    "message": "refactor: split DiskManager",
    "added":    [{ "className": "NvmeDiskManager", "changeRisk": "high" }],
    "removed":  [{ "className": "LegacyDiskManager" }],
    "modified": [{
      "className": "BlockCache",
      "depChanges": [{ "target": "NvmeDiskManager", "change": "added", "type": "composition" }]
    }],
    "modulesAdded": [], "modulesRemoved": [], "modulesModified": [],
    "impact": { "direct": ["StorageController"], "indirect": ["MetadataManager"] }
  }]
}
```

## Key constraints

- Scanner must complete full scan of 100k LOC in ≤60s; incremental in ≤5s.
- Sequence diagram accuracy vs GDB backtrace must be ≥95%.
- `ast_parser.py` uses `PARSE_SKIP_FUNCTION_BODIES` for performance; only `_scan_body_for_deps` re-enters method bodies for local variable dependency detection.
- `diff_engine.py` must be **LLM-free** — it is the authoritative audit trail; no hallucination risk allowed.
- `blueprint enrich --llm` writes prose back to `blueprint_index.json` which is **committed to git**. All viewers share it; viewing the Wiki never calls an LLM.
- `.blueprint_semantic_cache.json` and `.blueprint_cache.json` are local-only (add to `.gitignore`); `blueprint_index.json` and `blueprint_changes.json` are committed.
- libclang version must match the system clang installation. If `clang.cindex` fails to load, set `DYLD_LIBRARY_PATH` (macOS) or `LD_LIBRARY_PATH` (Linux) to the clang lib directory.
- The wiki webview uses esbuild + Preact (no React, no CDN at runtime). Rebuild with `npm run build:wiki` after any change to `wiki-webview/src/`.
