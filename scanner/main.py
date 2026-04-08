"""
main.py — CLI entry point for clang-blueprint scanner.

Commands:
  scan   --project-root <dir> [--output <file>] [--incremental]
         [--compile-commands <path>]
  diagram --type class|sequence [--filter <pattern>]
          [--namespace <prefix>] [--input <blueprint_index.json>]
          [--output-dir <dir>] [--gdb-backtrace <file>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    if isinstance(data, list):
        print(f"[blueprint] Wrote {len(data)} entries to {path}")
    elif isinstance(data, dict):
        n_classes = len(data.get("classes", []))
        n_modules = len(data.get("modules", []))
        print(f"[blueprint] Wrote v2 index ({n_classes} classes, {n_modules} modules) to {path}")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    """Handle the `scan` subcommand."""
    project_root = os.path.abspath(args.project_root)
    if not os.path.isdir(project_root):
        print(f"ERROR: project-root does not exist: {project_root}", file=sys.stderr)
        return 1

    output_path = args.output or os.path.join(project_root, "blueprint_index.json")
    compile_commands = args.compile_commands

    # Auto-discover compile_commands.json if not provided
    if not compile_commands:
        candidates = [
            os.path.join(project_root, "compile_commands.json"),
            os.path.join(project_root, "build", "compile_commands.json"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                compile_commands = c
                print(f"[blueprint] Auto-detected compile_commands: {compile_commands}")
                break

    t0 = time.perf_counter()

    # P6-01: collect --exclude patterns (may be repeated); None = use defaults
    exclude_patterns: Optional[list[str]] = args.exclude if args.exclude else None

    if os.environ.get("BLUEPRINT_DEBUG_BACKFILL"):
        print(
            "[blueprint] BLUEPRINT_DEBUG_BACKFILL: [BACKFILL] trace lines go to stderr; "
            "progress bar and scan summaries go to stdout — use e.g. "
            "`2>backfill_debug.txt` to capture debug without hiding progress.",
            flush=True,
        )

    if args.incremental:
        from scanner.incremental import incremental_scan
        cache_path = args.cache or None
        print(f"[blueprint] Starting incremental scan of {project_root} ...")
        entries = incremental_scan(
            project_root=project_root,
            compile_commands_path=compile_commands,
            cache_path=cache_path,
            exclude_patterns=exclude_patterns,
        )
    else:
        from scanner.ast_parser import scan_directory
        print(f"[blueprint] Starting full scan of {project_root} ...")
        entries = scan_directory(
            project_root=project_root,
            compile_commands_path=compile_commands,
            exclude_patterns=exclude_patterns,
        )

    elapsed = time.perf_counter() - t0
    print(f"[blueprint] Scan complete in {elapsed:.2f}s — {len(entries)} classes indexed.")

    if elapsed > 60:
        print(
            f"WARNING: Full scan took {elapsed:.1f}s (target: <60s). "
            "Consider using --incremental for subsequent runs.",
            flush=True,
        )

    # B2: also output blueprint_graph.json (reverseDeps for O(1) impact lookups)
    from scanner.graph_builder import build_graph, write_graph, graph_path_for
    graph = build_graph(entries)
    graph_output = args.graph_output or graph_path_for(output_path)
    write_graph(graph, graph_output)

    # Semantic enrichment: heuristic inference of intent, designPattern, changeRisk
    from scanner.semantic_enricher import enrich as semantic_enrich
    semantic_enrich(entries)

    # P21: build module layer + entry points → v2 index
    from scanner.module_grouper import build_modules
    from scanner.entry_detector import detect_entry_points

    reverse_deps = graph.get("reverseDeps", {})
    entry_points = detect_entry_points(entries, reverse_deps=reverse_deps)
    modules, module_edges = build_modules(
        entries, entry_points=entry_points, reverse_deps=reverse_deps
    )

    # M28-04: heuristic semantic enrichment (always, no API key needed)
    from scanner.semantic_enricher import enrich_all_heuristic, enrich_all_llm
    enrich_all_heuristic(entries, reverse_deps)

    # LLM enrichment (opt-in)
    if getattr(args, "enrich_llm", False):
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not anthropic_key and not gemini_key:
            print(
                "WARNING: --enrich-llm requires ANTHROPIC_API_KEY or GEMINI_API_KEY env var. "
                "Heuristic enrichment already applied.",
                file=sys.stderr,
            )
        else:
            sem_cache = os.path.join(os.path.dirname(output_path), ".blueprint_semantic_cache.json")
            total, llm_n, cached_n = enrich_all_llm(
                entries, reverse_deps,
                cache_path=sem_cache,
                anthropic_api_key=anthropic_key,
                gemini_api_key=gemini_key,
            )
            print(
                f"[blueprint] Semantic enrichment complete — "
                f"LLM: {llm_n}, cached: {cached_n}, total: {total}"
            )

    v2_index: dict[str, Any] = {
        "version": 3,
        "generatedAt": graph.get("generatedAt", ""),
        "projectName": os.path.basename(project_root),
        "modules": modules,
        "moduleEdges": module_edges,
        "entryPoints": entry_points,
        "classes": entries,
    }
    _save_json(output_path, v2_index)

    return 0


def cmd_diagram(args: argparse.Namespace) -> int:
    """Handle the `diagram` subcommand."""
    from scanner.mermaid_generator import (
        generate_class_diagram,
        generate_sequence_diagram,
        parse_gdb_backtrace,
        write_diagram,
    )

    input_path = args.input or "blueprint_index.json"
    if not os.path.isfile(input_path):
        print(f"ERROR: Blueprint index not found: {input_path}", file=sys.stderr)
        print("Run `blueprint scan` first to generate the index.", file=sys.stderr)
        return 1

    raw = _load_json(input_path)
    # Support both v1 (bare array) and v2 (object with "classes" key)
    entries: list[dict] = raw if isinstance(raw, list) else raw.get("classes", [])
    diagram_type = args.type
    filter_pattern: Optional[str] = args.filter
    namespace_filter: Optional[str] = args.namespace
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(input_path))

    if diagram_type == "class":
        diagram = generate_class_diagram(
            entries,
            filter_pattern=filter_pattern,
            namespace_filter=namespace_filter,
            title="C++ Blueprint — Class Diagram",
        )
        out_path = os.path.join(output_dir, "class_diagram.mmd")
        write_diagram(diagram, out_path)
        print(diagram)

    elif diagram_type == "sequence":
        call_graph: list[dict] = []

        if args.gdb_backtrace:
            if not os.path.isfile(args.gdb_backtrace):
                print(f"ERROR: GDB backtrace file not found: {args.gdb_backtrace}", file=sys.stderr)
                return 1
            with open(args.gdb_backtrace, "r") as f:
                backtrace_text = f.read()
            call_graph = parse_gdb_backtrace(backtrace_text)
            print(f"[blueprint] Parsed {len(call_graph)} call edges from GDB backtrace.")

        elif args.call_graph:
            if not os.path.isfile(args.call_graph):
                print(f"ERROR: Call graph file not found: {args.call_graph}", file=sys.stderr)
                return 1
            call_graph = _load_json(args.call_graph)

        diagram = generate_sequence_diagram(
            call_graph,
            filter_pattern=filter_pattern,
            namespace_filter=namespace_filter,
            title="C++ Blueprint — Sequence Diagram",
        )
        out_path = os.path.join(output_dir, "sequence_diagram.mmd")
        write_diagram(diagram, out_path)
        print(diagram)

    else:
        print(f"ERROR: Unknown diagram type: {diagram_type!r}. Use 'class' or 'sequence'.",
              file=sys.stderr)
        return 1

    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    """Handle the `enrich` subcommand — add semantic fields to an existing index."""
    input_path = args.input or "blueprint_index.json"
    if not os.path.isfile(input_path):
        print(f"ERROR: Blueprint index not found: {input_path}", file=sys.stderr)
        print("Run `blueprint scan` first to generate the index.", file=sys.stderr)
        return 1

    raw = _load_json(input_path)
    if isinstance(raw, list):
        entries = raw
        reverse_deps: dict = {}
    else:
        entries = raw.get("classes", [])
        # Try to load reverse deps from graph file
        graph_file = os.path.join(os.path.dirname(os.path.abspath(input_path)), "blueprint_graph.json")
        if os.path.isfile(graph_file):
            g = _load_json(graph_file)
            reverse_deps = g.get("reverseDeps", {})
        else:
            reverse_deps = {}

    from scanner.semantic_enricher import enrich_all_heuristic, enrich_all_llm

    use_llm = getattr(args, "llm", False)
    if use_llm:
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not anthropic_key and not gemini_key:
            print(
                "WARNING: --llm requires ANTHROPIC_API_KEY or GEMINI_API_KEY. "
                "Falling back to heuristic.",
                file=sys.stderr,
            )
            use_llm = False

    enrich_all_heuristic(entries, reverse_deps)

    llm_n = cached_n = 0
    if use_llm:
        sem_cache = os.path.join(
            os.path.dirname(os.path.abspath(input_path)),
            ".blueprint_semantic_cache.json",
        )
        total, llm_n, cached_n = enrich_all_llm(
            entries, reverse_deps,
            cache_path=sem_cache,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        )
        print(
            f"[blueprint] LLM enrichment: {llm_n} new, {cached_n} cached, {total} total"
        )
    else:
        print(
            f"[blueprint] Heuristic enrichment: {len(entries)} classes "
            f"(heuristic: {len(entries)}, llm: 0)"
        )

    if isinstance(raw, list):
        _save_json(input_path, entries)
    else:
        raw["version"] = 3
        _save_json(input_path, raw)

    return 0


def cmd_cache_stats(args: argparse.Namespace) -> int:
    """Show incremental cache statistics."""
    from scanner.incremental import get_cache_stats, DEFAULT_CACHE_NAME
    cache_path = args.cache or os.path.join(
        os.path.abspath(args.project_root or "."), DEFAULT_CACHE_NAME
    )
    stats = get_cache_stats(cache_path)
    print(json.dumps(stats, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blueprint",
        description="clang-blueprint: C++ codebase scanner and diagram generator",
    )
    parser.add_argument(
        "--version", action="version", version="clang-blueprint 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- scan ---
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan C/C++ source files and produce blueprint_index.json",
    )
    scan_parser.add_argument(
        "--project-root", "-p",
        default=".",
        help="Root directory of the C/C++ project (default: current directory)",
    )
    scan_parser.add_argument(
        "--output", "-o",
        help="Output path for blueprint_index.json (default: <project-root>/blueprint_index.json)",
    )
    scan_parser.add_argument(
        "--incremental", "-i",
        action="store_true",
        help="Use hash-based incremental scan (only re-parse changed files)",
    )
    scan_parser.add_argument(
        "--compile-commands", "-c",
        help="Path to compile_commands.json (auto-detected if omitted)",
    )
    scan_parser.add_argument(
        "--cache",
        help="Path to incremental cache file (default: <project-root>/.blueprint_cache.json)",
    )
    scan_parser.add_argument(
        "--exclude", "-e",
        action="append",
        metavar="PATTERN",
        help=(
            "Glob pattern of paths to exclude from scanning "
            "(may be repeated, e.g. --exclude 'third_party/**' --exclude 'build/**'). "
            "Patterns in .blueprintignore are always merged in automatically."
        ),
    )
    scan_parser.add_argument(
        "--graph-output",
        help="Output path for blueprint_graph.json (default: same directory as --output)",
    )
    scan_parser.add_argument(
        "--enrich-llm",
        action="store_true",
        dest="enrich_llm",
        help=(
            "After scanning, enrich semantic fields via LLM (requires ANTHROPIC_API_KEY "
            "or GEMINI_API_KEY). Heuristic enrichment always runs regardless of this flag."
        ),
    )

    # --- enrich ---
    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Add/update semantic fields (intent, tradeoffs, changeRisk, designPattern) on an existing index",
    )
    enrich_parser.add_argument(
        "--input", "-i",
        help="Path to blueprint_index.json (default: ./blueprint_index.json)",
    )
    enrich_parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM enrichment (requires ANTHROPIC_API_KEY or GEMINI_API_KEY)",
    )

    # --- diagram ---
    diag_parser = subparsers.add_parser(
        "diagram",
        help="Generate Mermaid diagrams from blueprint_index.json",
    )
    diag_parser.add_argument(
        "--type", "-t",
        choices=["class", "sequence"],
        required=True,
        help="Diagram type: 'class' or 'sequence'",
    )
    diag_parser.add_argument(
        "--filter", "-f",
        help="Regex pattern to filter by class name",
    )
    diag_parser.add_argument(
        "--namespace", "-n",
        help="Namespace prefix to restrict diagram (e.g. 'core' or 'io::net')",
    )
    diag_parser.add_argument(
        "--input",
        help="Path to blueprint_index.json (default: ./blueprint_index.json)",
    )
    diag_parser.add_argument(
        "--output-dir",
        help="Directory to write .mmd files (default: same directory as input)",
    )
    diag_parser.add_argument(
        "--gdb-backtrace",
        help="Path to a GDB backtrace text file (for sequence diagrams)",
    )
    diag_parser.add_argument(
        "--call-graph",
        help="Path to a call_graph.json file (for sequence diagrams)",
    )

    # --- cache-stats ---
    stats_parser = subparsers.add_parser(
        "cache-stats",
        help="Show incremental scan cache statistics",
    )
    stats_parser.add_argument("--project-root", "-p", default=".")
    stats_parser.add_argument("--cache", help="Path to cache file")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "scan": cmd_scan,
        "diagram": cmd_diagram,
        "enrich": cmd_enrich,
        "cache-stats": cmd_cache_stats,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n[blueprint] Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[blueprint] FATAL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
