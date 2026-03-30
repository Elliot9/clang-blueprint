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

# Build VS Code extension
cd vscode-extension && npm install && npm run compile
```

## Architecture

### Data flow
```
C++ source files
  → scanner/ast_parser.py  (libclang AST walk)
  → blueprint_index.json   (array of ClassEntry dicts)
  → ai_api/indexer.py      (TF-IDF over className + responsibility + interfaces)
  → POST /query            (cosine similarity ranking)

blueprint_index.json
  → vscode-extension       (postMessage to WebviewPanel)
  → webview/index.html     (React Flow canvas, pan/zoom/click)
  → vscode.showTextDocument (jump to fileLocation:lineNumber)
```

### scanner/ — Phase 1 (Python)
- **ast_parser.py** — Core parser. `ASTVisitor` walks a libclang `TranslationUnit`, extracts `BlueprintEntry` dataclasses. Dependency types: `composition` (direct member/unique_ptr), `aggregation` (shared_ptr/weak_ptr/raw ptr), `inheritance` (base specifier), `association` (method param/return), `dependency` (local var). Entry point: `parse_files(files, project_root)` and `scan_directory(root)`.
- **incremental.py** — SHA256-based cache in `.blueprint_cache.json`. Only re-parses files whose hash changed. Atomic writes via `tempfile + os.replace()`. Entry point: `incremental_scan(project_root)`.
- **mermaid_generator.py** — Converts blueprint entries → Mermaid `classDiagram`; call graph dicts → `sequenceDiagram`; parses GDB backtraces via `parse_gdb_backtrace()`.
- **main.py** — `argparse` CLI: `scan` and `diagram` subcommands.

### ai_api/ — Phase 3 (Python + FastAPI)
- **indexer.py** — `BlueprintIndexer`: TF-IDF over CamelCase-expanded text. `build(entries)`, `query(text, top_k)`, persists to `.blueprint_tfidf.pkl`.
- **server.py** — FastAPI. `POST /query`, `POST /rebuild-index`, `GET /health`. Config via env vars: `BLUEPRINT_INDEX_PATH`, `TFIDF_INDEX_PATH`, `MAX_TOP_K`.

### vscode-extension/ — Phase 2 (TypeScript)
- **src/extension.ts** — Registers 5 commands. Opens `WebviewPanel` with `webview/index.html`. Handles `nodeClick` postMessage → `vscode.window.showTextDocument`. Watches `blueprint_index.json` via `createFileSystemWatcher`.
- **webview/index.html** — Self-contained (no bundler). Renders nodes/edges on an absolute-positioned canvas. Pan/zoom via mouse wheel + drag. Node double-click → postMessage to extension. Minimap in bottom-right corner.

### blueprint_index.json schema
```json
{
  "className": "DiskManager",
  "responsibility": "Resource Lifecycle",
  "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
  "interfaces": ["void readBlock(int lba, char * buf)"],
  "fileLocation": "src/core/disk_mgr.cpp",
  "lineNumber": 42,
  "namespace": "core",
  "baseClasses": ["IoBase"],
  "templateParams": []
}
```

## Key constraints
- Scanner must complete full scan of 100k LOC in ≤60s; incremental in ≤5s.
- Sequence diagram accuracy vs GDB backtrace must be ≥95%.
- `ast_parser.py` uses `PARSE_SKIP_FUNCTION_BODIES` for performance; only `_scan_body_for_deps` re-enters method bodies for local variable dependency detection.
- The webview has no build step — it uses only inline JS and does not import npm packages.
- libclang version must match the system clang installation. If `clang.cindex` fails to load, set `DYLD_LIBRARY_PATH` (macOS) or `LD_LIBRARY_PATH` (Linux) to the clang lib directory.
