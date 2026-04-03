"""
entry_detector.py — Detect entry points in a C++ codebase from ClassEntry data.

Entry point kinds:
  - main    : contains main() function
  - server  : class name matches Server/App/Handler/Controller/Main/Entry pattern
  - root    : in-degree 0 but out-degree > 0 in the dependency graph
  - hub     : top-N most depended-upon classes

Returns EntryPoint dicts for blueprint_index.json v2.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from typing import Any


# Patterns that suggest a class is a server / application entry
_ENTRY_NAME_PATTERNS = re.compile(
    r"(^main$|Main$|Server$|App$|Application$|Handler$|Controller$|Entry$|Daemon$|Service$)",
    re.IGNORECASE,
)


def detect_entry_points(
    entries: list[dict[str, Any]],
    reverse_deps: dict[str, list[str]] | None = None,
    *,
    hub_top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Analyse *entries* and return a list of EntryPoint dicts.

    Each dict has:
      className : str
      kind      : 'main' | 'server' | 'root' | 'hub'
      reason    : str   (human-readable explanation)
    """
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Precompute out-degree (number of distinct dependency targets per class)
    out_degree: dict[str, int] = {}
    for e in entries:
        cn = e.get("className", "")
        out_degree[cn] = len(e.get("dependencies", []))

    # Precompute in-degree from reverse_deps
    in_degree: dict[str, int] = defaultdict(int)
    if reverse_deps:
        for target, dependents in reverse_deps.items():
            in_degree[target] = len(dependents)

    all_class_names = {e["className"] for e in entries}

    # --- Kind: main ---
    for e in entries:
        cn = e.get("className", "")
        interfaces = e.get("interfaces", [])
        # Check for main() signature (free-function entries or class with main)
        has_main = any(
            "main(" in sig and ("int main" in sig or "void main" in sig)
            for sig in interfaces
        )
        if has_main and cn not in seen:
            results.append({
                "className": cn,
                "kind": "main",
                "reason": f"Contains main() entry function",
            })
            seen.add(cn)

    # --- Kind: server ---
    for e in entries:
        cn = e.get("className", "")
        if cn in seen:
            continue
        if _ENTRY_NAME_PATTERNS.search(cn):
            results.append({
                "className": cn,
                "kind": "server",
                "reason": f"Name matches entry-point pattern ({cn})",
            })
            seen.add(cn)

    # --- Kind: root (in-degree 0, out-degree >= 2) ---
    # Require at least 2 outgoing deps to filter out trivial leaves.
    # Also cap at 20 roots to keep the list useful.
    root_candidates: list[tuple[str, int]] = []
    for e in entries:
        cn = e.get("className", "")
        if cn in seen:
            continue
        od = out_degree.get(cn, 0)
        if in_degree.get(cn, 0) == 0 and od >= 2:
            root_candidates.append((cn, od))

    # Sort by out-degree descending, take top 20
    root_candidates.sort(key=lambda x: -x[1])
    for cn, od in root_candidates[:20]:
        results.append({
            "className": cn,
            "kind": "root",
            "reason": f"No incoming dependencies, {od} outgoing — graph root",
        })
        seen.add(cn)

    # --- Kind: hub (top N by in-degree) ---
    if reverse_deps:
        sorted_by_indeg = sorted(
            ((cn, deg) for cn, deg in in_degree.items() if cn in all_class_names),
            key=lambda x: -x[1],
        )
        for cn, deg in sorted_by_indeg[:hub_top_n]:
            if cn in seen:
                continue
            if deg < 2:
                continue
            results.append({
                "className": cn,
                "kind": "hub",
                "reason": f"Depended upon by {deg} classes — central hub",
            })
            seen.add(cn)

    print(
        f"[entry_detector] Found {len(results)} entry points "
        f"({sum(1 for r in results if r['kind']=='main')} main, "
        f"{sum(1 for r in results if r['kind']=='server')} server, "
        f"{sum(1 for r in results if r['kind']=='root')} root, "
        f"{sum(1 for r in results if r['kind']=='hub')} hub).",
        file=sys.stderr,
    )
    return results
