"""
module_grouper.py — Groups ClassEntry dicts into modules and computes inter-module edges.

Grouping strategy (priority order):
  1. Explicit C++ namespace → module name (e.g. "grcore" → module "grcore")
  2. No namespace → group by first-level directory (e.g. "graidserver/foo.h" → module "graidserver")
  3. Orphans → "_ungrouped" module

Output:
  ModuleEntry dicts + ModuleEdge dicts, ready for blueprint_index.json v2.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from typing import Any


# ---------------------------------------------------------------------------
# Public types (dict-based, JSON-serialisable)
# ---------------------------------------------------------------------------
# ModuleEntry = {
#   "name": str,
#   "namespace": str | None,
#   "directory": str | None,
#   "classNames": [str],
#   "summarySeed": str,
#   "internalEdgeCount": int,
#   "externalDeps": [{"target": str, "weight": int, "depTypes": [str]}]
# }
#
# ModuleEdge = {
#   "source": str,
#   "target": str,
#   "weight": int,
#   "depTypes": [str]
# }

# Namespaces that come from third-party headers / standard library — never
# promoted to a top-level module; they are noise in the project's own module
# map.  We collapse them into a single "_thirdparty" bucket (or skip entirely).
_THIRDPARTY_NS_PREFIXES = (
    "std", "__gnu_cxx", "absl", "fmt", "google::protobuf", "grpc",
    "nlohmann", "spdlog", "YAML", "gzip", "thread_safety_analysis",
)

_THIRDPARTY_DIR_PREFIXES = (
    "3rd_party", "third_party", "vendor", "extern", "build",
    "cmake-build", "CMakeFiles",
)


def _top_namespace(ns: str) -> str:
    """Return the first component of a nested namespace.  'a::b::c' → 'a'."""
    return ns.split("::")[0] if ns else ""


def _top_directory(file_loc: str) -> str:
    """Return the first path component of a relative file location."""
    parts = file_loc.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def _is_thirdparty_ns(ns: str) -> bool:
    top = _top_namespace(ns)
    return any(top == pfx or ns.startswith(pfx + "::") for pfx in _THIRDPARTY_NS_PREFIXES)


def _is_thirdparty_dir(directory: str) -> bool:
    return any(directory.startswith(pfx) for pfx in _THIRDPARTY_DIR_PREFIXES)


# ---------------------------------------------------------------------------
# Core: group_into_modules
# ---------------------------------------------------------------------------

def group_into_modules(
    entries: list[dict[str, Any]],
    *,
    include_thirdparty: bool = False,
) -> list[dict[str, Any]]:
    """
    Partition *entries* into module groups.

    Returns a list of ModuleEntry dicts (without summarySeed — call
    ``generate_summary_seeds`` separately).
    """
    # bucket: module_name → list[entry]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        ns = entry.get("namespace", "")
        file_loc = entry.get("fileLocation", "")
        top_dir = _top_directory(file_loc)

        # --- decide module name ---
        if ns:
            if _is_thirdparty_ns(ns):
                if include_thirdparty:
                    buckets["_thirdparty"].append(entry)
                continue  # skip third-party by default
            buckets[_top_namespace(ns)].append(entry)
        elif top_dir:
            if _is_thirdparty_dir(top_dir):
                if include_thirdparty:
                    buckets["_thirdparty"].append(entry)
                continue
            buckets[top_dir].append(entry)
        else:
            buckets["_ungrouped"].append(entry)

    # Build ModuleEntry dicts
    modules: list[dict[str, Any]] = []
    for mod_name, mod_entries in sorted(buckets.items()):
        if not mod_entries:
            continue

        # Determine primary namespace / directory for metadata
        ns_counter: Counter[str] = Counter()
        dir_counter: Counter[str] = Counter()
        for e in mod_entries:
            if e.get("namespace"):
                ns_counter[_top_namespace(e["namespace"])] += 1
            fl = e.get("fileLocation", "")
            td = _top_directory(fl)
            if td:
                dir_counter[td] += 1

        primary_ns = ns_counter.most_common(1)[0][0] if ns_counter else None
        primary_dir = dir_counter.most_common(1)[0][0] if dir_counter else None

        # Class names belonging to this module
        class_names = sorted({e["className"] for e in mod_entries})

        # Internal edge count = dependencies where both src and target are in this module
        class_set = set(class_names)
        internal_edges = 0
        for e in mod_entries:
            for dep in e.get("dependencies", []):
                if dep.get("target", "") in class_set:
                    internal_edges += 1

        modules.append({
            "name": mod_name,
            "namespace": primary_ns,
            "directory": primary_dir,
            "classNames": class_names,
            "summarySeed": "",  # filled by generate_summary_seeds()
            "internalEdgeCount": internal_edges,
            "externalDeps": [],  # filled by compute_module_edges()
        })

    return modules


# ---------------------------------------------------------------------------
# Core: compute_module_edges
# ---------------------------------------------------------------------------

def compute_module_edges(
    entries: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Compute directed inter-module dependency edges.

    Returns a list of ModuleEdge dicts and populates each module's
    ``externalDeps`` field as a side-effect.
    """
    # Build className → moduleName lookup
    class_to_module: dict[str, str] = {}
    for mod in modules:
        for cn in mod["classNames"]:
            class_to_module[cn] = mod["name"]

    # Accumulate (src_module, tgt_module) → {weight, depTypes}
    edge_agg: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"weight": 0, "depTypes": set()}
    )

    for entry in entries:
        src_cn = entry.get("className", "")
        src_mod = class_to_module.get(src_cn)
        if not src_mod:
            continue
        for dep in entry.get("dependencies", []):
            tgt_cn = dep.get("target", "")
            tgt_mod = class_to_module.get(tgt_cn)
            if not tgt_mod or tgt_mod == src_mod:
                continue
            key = (src_mod, tgt_mod)
            edge_agg[key]["weight"] += 1
            edge_agg[key]["depTypes"].add(dep.get("type", "dependency"))

    # Convert to list of ModuleEdge dicts
    edges: list[dict[str, Any]] = []
    for (src, tgt), info in sorted(edge_agg.items()):
        edges.append({
            "source": src,
            "target": tgt,
            "weight": info["weight"],
            "depTypes": sorted(info["depTypes"]),
        })

    # Also populate each module's externalDeps
    ext_deps_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        ext_deps_map[edge["source"]].append({
            "target": edge["target"],
            "weight": edge["weight"],
            "depTypes": edge["depTypes"],
        })

    for mod in modules:
        mod["externalDeps"] = ext_deps_map.get(mod["name"], [])

    return edges


# ---------------------------------------------------------------------------
# Core: generate_summary_seeds
# ---------------------------------------------------------------------------

def generate_summary_seeds(
    modules: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    entry_points: list[dict[str, Any]] | None = None,
    reverse_deps: dict[str, list[str]] | None = None,
) -> None:
    """
    Fill each module's ``summarySeed`` with a heuristic one-liner (no AI).

    Mutates *modules* in place.
    """
    entry_points = entry_points or []
    reverse_deps = reverse_deps or {}

    # className → entry for quick lookup
    entry_map: dict[str, dict[str, Any]] = {
        e["className"]: e for e in entries
    }

    # entry point classes per module
    ep_map: dict[str, list[str]] = defaultdict(list)
    # Build className → moduleName
    class_to_module: dict[str, str] = {}
    for mod in modules:
        for cn in mod["classNames"]:
            class_to_module[cn] = mod["name"]
    for ep in entry_points:
        cn = ep.get("className", "")
        mod_name = class_to_module.get(cn)
        if mod_name:
            ep_map[mod_name].append(cn)

    for mod in modules:
        n_classes = len(mod["classNames"])
        name = mod["name"]

        # Top responsibility labels
        resp_counter: Counter[str] = Counter()
        for cn in mod["classNames"]:
            e = entry_map.get(cn)
            if e and e.get("responsibility"):
                resp_counter[e["responsibility"]] += 1

        top_resps = [r for r, _ in resp_counter.most_common(3)]

        # Hub class (most depended upon within module)
        hub = ""
        hub_count = 0
        for cn in mod["classNames"]:
            rd = reverse_deps.get(cn, [])
            if len(rd) > hub_count:
                hub_count = len(rd)
                hub = cn

        # Entry points in this module
        eps = ep_map.get(name, [])

        # Build seed
        parts: list[str] = [f'Module "{name}" contains {n_classes} class{"es" if n_classes != 1 else ""}']
        if top_resps:
            parts.append(f'primarily responsible for {", ".join(top_resps)}')
        if hub and hub_count > 1:
            parts.append(f'Key hub: {hub} (used by {hub_count} classes)')
        if eps:
            parts.append(f'Entry via {", ".join(eps[:2])}')

        mod["summarySeed"] = ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Convenience: full pipeline
# ---------------------------------------------------------------------------

def build_modules(
    entries: list[dict[str, Any]],
    entry_points: list[dict[str, Any]] | None = None,
    reverse_deps: dict[str, list[str]] | None = None,
    include_thirdparty: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Run the full module-building pipeline.

    Returns (modules, module_edges).
    """
    modules = group_into_modules(entries, include_thirdparty=include_thirdparty)
    edges = compute_module_edges(entries, modules)
    generate_summary_seeds(modules, entries, entry_points, reverse_deps)

    print(
        f"[module_grouper] Grouped {sum(len(m['classNames']) for m in modules)} classes "
        f"into {len(modules)} modules with {len(edges)} inter-module edges.",
        file=sys.stderr,
    )
    return modules, edges
