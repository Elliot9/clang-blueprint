"""
graph_builder.py — Derives graph structures from blueprint_index entries.

Computes data that is NOT already in blueprint_index.json and would be
expensive to recompute per request in the extension host.

Currently produces:
  reverseDeps  — inverse of dependencies[].target
                 key: className  →  value: list of classes that depend on it
                 Enables O(1) impact lookups; TraceController does BFS on this.

Deliberately NOT precomputed here:
  impact_set   — computed on-demand via BFS over reverseDeps (only when user
                 selects a class), so we don't store O(n²) data
  call_graph   — already present as callSequence per ClassEntry in the index

Output schema (blueprint_graph.json):
{
  "version": 1,
  "generatedAt": "<ISO-8601>",
  "reverseDeps": {
    "NVMeDriver": ["DiskManager", "StorageController"],
    "IoBase":     ["DiskManager"]
  }
}
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

GRAPH_VERSION = 1


def build_reverse_deps(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    """
    Compute the reverse dependency map from a list of ClassEntry dicts.

    For every dependency edge A→B recorded in entries, add A to reverseDeps[B].
    Returns a dict mapping each target className to the list of classNames that
    depend on it (deduped, sorted for deterministic output).
    """
    reverse: dict[str, list[str]] = {}
    for entry in entries:
        src = entry.get("className", "")
        if not src:
            continue
        for dep in entry.get("dependencies", []):
            target = dep.get("target", "")
            if not target or target == src:
                continue
            if target not in reverse:
                reverse[target] = []
            if src not in reverse[target]:
                reverse[target].append(src)

    # Sort for determinism
    for key in reverse:
        reverse[key].sort()
    return reverse


def build_graph(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the full blueprint_graph structure from parsed entries."""
    return {
        "version": GRAPH_VERSION,
        "generatedAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reverseDeps": build_reverse_deps(entries),
    }


def write_graph(graph: dict[str, Any], output_path: str) -> None:
    """Atomically write blueprint_graph.json to disk."""
    dir_path = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2)
        os.replace(tmp, output_path)
        n = len(graph.get("reverseDeps", {}))
        print(f"[blueprint] Wrote graph ({n} reverse-dep entries) to {output_path}")
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def graph_path_for(index_path: str) -> str:
    """Return the conventional blueprint_graph.json path next to the index."""
    p = Path(index_path)
    return str(p.parent / "blueprint_graph.json")


def load_graph(graph_path: str) -> dict[str, Any]:
    """Load blueprint_graph.json, returning empty structure if missing or corrupt."""
    empty: dict[str, Any] = {"version": GRAPH_VERSION, "reverseDeps": {}}
    p = Path(graph_path)
    if not p.exists():
        return empty
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != GRAPH_VERSION:
            print(
                f"[graph_builder] Graph version mismatch or corrupt; returning empty.",
                file=sys.stderr,
            )
            return empty
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[graph_builder] WARNING: Cannot load graph {graph_path}: {e}", file=sys.stderr)
        return empty
