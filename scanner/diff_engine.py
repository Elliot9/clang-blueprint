"""
scanner/diff_engine.py — Deterministic architectural diff between two Blueprint indices.

Compares two blueprint_index.json snapshots and produces a structured ChangeRecord.
No LLM involved — all facts come from AST-parsed data.

Usage:
    from scanner.diff_engine import load_index_from_git, diff_indices, build_change_record
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def load_index_from_git(ref: str, index_filename: str = "blueprint_index.json") -> dict | None:
    """
    Read blueprint_index.json from a git ref (e.g. 'HEAD', 'HEAD~1', 'main').
    Returns parsed dict, or None if the file didn't exist at that ref.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{index_filename}"],
            capture_output=True, text=True, check=True,
        )
        raw = json.loads(result.stdout)
        # Normalise v1 (bare array) to object form
        if isinstance(raw, list):
            return {"version": 1, "classes": raw, "modules": [], "moduleEdges": [], "entryPoints": []}
        return raw
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None


def get_git_commit_meta(ref: str = "HEAD") -> dict[str, str]:
    """Return commit metadata for a git ref."""
    fmt = "%H%n%an%n%ae%n%aI%n%s"
    try:
        result = subprocess.run(
            ["git", "log", "-1", f"--format={fmt}", ref],
            capture_output=True, text=True, check=True,
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 5:
            return {
                "commit": lines[0],
                "author": lines[1],
                "email": lines[2],
                "date": lines[3],
                "message": lines[4],
            }
    except subprocess.CalledProcessError:
        pass
    return {
        "commit": "unknown",
        "author": "unknown",
        "email": "",
        "date": datetime.now(timezone.utc).isoformat(),
        "message": "",
    }


# ---------------------------------------------------------------------------
# Index normalisation helpers
# ---------------------------------------------------------------------------

def _classes_by_name(index: dict) -> dict[str, dict]:
    return {c["className"]: c for c in index.get("classes", [])}


def _modules_by_name(index: dict) -> dict[str, dict]:
    return {m["name"]: m for m in index.get("modules", [])}


def _iface_set(entry: dict) -> set[str]:
    return set(entry.get("interfaces", []))


def _dep_map(entry: dict) -> dict[str, str]:
    """Returns {target: depType} for quick comparison."""
    return {d["target"]: d["type"] for d in entry.get("dependencies", [])}


def _entry_structural_hash(entry: dict) -> str:
    """Hash the structurally significant parts of a ClassEntry."""
    key = {
        "interfaces": sorted(entry.get("interfaces", [])),
        "dependencies": sorted(
            f"{d['target']}:{d['type']}" for d in entry.get("dependencies", [])
        ),
        "baseClasses": sorted(entry.get("baseClasses", [])),
        "attributes": sorted(entry.get("attributes", [])),
    }
    payload = json.dumps(key, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Class diff
# ---------------------------------------------------------------------------

def diff_classes(old_index: dict, new_index: dict) -> dict[str, Any]:
    """
    Compare class entries between two indices.
    Returns:
      {
        "added":    [ClassEntry, ...],
        "removed":  [ClassEntry, ...],
        "modified": [ClassDiff, ...],   # see _diff_single_class
      }
    """
    old_classes = _classes_by_name(old_index)
    new_classes = _classes_by_name(new_index)

    old_names = set(old_classes)
    new_names = set(new_classes)

    added   = [new_classes[n] for n in sorted(new_names - old_names)]
    removed = [old_classes[n] for n in sorted(old_names - new_names)]

    modified = []
    for name in sorted(old_names & new_names):
        old_e = old_classes[name]
        new_e = new_classes[name]
        if _entry_structural_hash(old_e) != _entry_structural_hash(new_e):
            diff = _diff_single_class(old_e, new_e)
            if diff:
                modified.append(diff)

    return {"added": added, "removed": removed, "modified": modified}


def _diff_single_class(old_e: dict, new_e: dict) -> dict | None:
    """Produce a ClassDiff dict for one modified class. Returns None if no meaningful change."""
    result: dict[str, Any] = {"className": old_e["className"]}
    changed = False

    # Interface changes
    old_ifaces = _iface_set(old_e)
    new_ifaces = _iface_set(new_e)
    iface_added   = sorted(new_ifaces - old_ifaces)
    iface_removed = sorted(old_ifaces - new_ifaces)
    if iface_added or iface_removed:
        result["interfaceChanges"] = {"added": iface_added, "removed": iface_removed}
        changed = True

    # Dependency changes
    old_deps = _dep_map(old_e)
    new_deps = _dep_map(new_e)
    dep_changes: list[dict] = []
    for target in sorted(set(old_deps) | set(new_deps)):
        old_type = old_deps.get(target)
        new_type = new_deps.get(target)
        if old_type is None:
            dep_changes.append({"target": target, "change": "added", "type": new_type})
        elif new_type is None:
            dep_changes.append({"target": target, "change": "removed", "type": old_type})
        elif old_type != new_type:
            dep_changes.append({"target": target, "change": "type_changed",
                                 "from": old_type, "to": new_type})
    if dep_changes:
        result["depChanges"] = dep_changes
        changed = True

    # Risk change
    old_risk = old_e.get("changeRisk")
    new_risk = new_e.get("changeRisk")
    if old_risk and new_risk and old_risk != new_risk:
        result["riskChange"] = {"from": old_risk, "to": new_risk}
        changed = True

    # File location change
    if old_e.get("fileLocation") != new_e.get("fileLocation"):
        result["fileLocationChange"] = {
            "from": old_e.get("fileLocation", ""),
            "to":   new_e.get("fileLocation", ""),
        }
        changed = True

    return result if changed else None


# ---------------------------------------------------------------------------
# Module diff
# ---------------------------------------------------------------------------

def diff_modules(old_index: dict, new_index: dict) -> dict[str, Any]:
    """Compare module entries between two indices."""
    old_mods = _modules_by_name(old_index)
    new_mods = _modules_by_name(new_index)

    old_names = set(old_mods)
    new_names = set(new_mods)

    added   = [new_mods[n]["name"] for n in sorted(new_names - old_names)]
    removed = [old_mods[n]["name"] for n in sorted(old_names - new_names)]

    modified = []
    for name in sorted(old_names & new_names):
        old_m = old_mods[name]
        new_m = new_mods[name]
        old_classes = set(old_m.get("classNames", []))
        new_classes = set(new_m.get("classNames", []))
        cls_added   = sorted(new_classes - old_classes)
        cls_removed = sorted(old_classes - new_classes)
        if cls_added or cls_removed:
            modified.append({
                "name": name,
                "classesAdded": cls_added,
                "classesRemoved": cls_removed,
            })

    return {"added": added, "removed": removed, "modified": modified}


# ---------------------------------------------------------------------------
# Impact analysis
# ---------------------------------------------------------------------------

def compute_impact(
    changed_class_names: list[str],
    new_index: dict,
    max_hops: int = 3,
) -> dict[str, list[str]]:
    """
    Given a list of changed class names, find all classes that depend on them.

    Returns:
      {
        "direct":   [className, ...],   # 1-hop dependents
        "indirect": [className, ...],   # 2+ hops
      }
    """
    # Build reverse dep map from new index
    reverse_deps: dict[str, set[str]] = {}
    for cls in new_index.get("classes", []):
        for dep in cls.get("dependencies", []):
            target = dep["target"]
            reverse_deps.setdefault(target, set()).add(cls["className"])

    changed = set(changed_class_names)
    direct:   set[str] = set()
    indirect: set[str] = set()

    # BFS
    frontier = set(changed)
    visited  = set(changed)

    for hop in range(max_hops):
        next_frontier: set[str] = set()
        for name in frontier:
            for dependent in reverse_deps.get(name, set()):
                if dependent not in visited:
                    visited.add(dependent)
                    next_frontier.add(dependent)
                    if hop == 0:
                        direct.add(dependent)
                    else:
                        indirect.add(dependent)
        frontier = next_frontier
        if not frontier:
            break

    # Remove any overlap (direct takes priority)
    indirect -= direct
    # Remove changed classes from results
    direct   -= changed
    indirect -= changed

    return {
        "direct":   sorted(direct),
        "indirect": sorted(indirect),
    }


# ---------------------------------------------------------------------------
# Change record assembly
# ---------------------------------------------------------------------------

def build_change_record(
    git_meta: dict[str, str],
    class_diffs: dict[str, Any],
    module_diffs: dict[str, Any],
    impact: dict[str, list[str]],
    index_filename: str = "blueprint_index.json",
) -> dict[str, Any]:
    """Assemble a single ChangeRecord for blueprint_changes.json."""
    return {
        "commit":    git_meta.get("commit", "unknown"),
        "author":    git_meta.get("author", "unknown"),
        "email":     git_meta.get("email", ""),
        "date":      git_meta.get("date", datetime.now(timezone.utc).isoformat()),
        "message":   git_meta.get("message", ""),
        "indexFile": index_filename,
        "added":   [
            {
                "className":     c.get("className"),
                "fileLocation":  c.get("fileLocation"),
                "designPattern": c.get("designPattern"),
                "changeRisk":    c.get("changeRisk"),
            }
            for c in class_diffs.get("added", [])
        ],
        "removed": [
            {"className": c.get("className"), "fileLocation": c.get("fileLocation")}
            for c in class_diffs.get("removed", [])
        ],
        "modified":       class_diffs.get("modified", []),
        "modulesAdded":   module_diffs.get("added", []),
        "modulesRemoved": module_diffs.get("removed", []),
        "modulesModified":module_diffs.get("modified", []),
        "impact":         impact,
    }


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def diff_indices(
    old_index: dict,
    new_index: dict,
    git_meta: dict[str, str] | None = None,
    index_filename: str = "blueprint_index.json",
) -> dict[str, Any] | None:
    """
    Full diff: old → new.
    Returns a ChangeRecord dict, or None if there are no structural changes.
    """
    class_diffs  = diff_classes(old_index, new_index)
    module_diffs = diff_modules(old_index, new_index)

    has_changes = any([
        class_diffs["added"],
        class_diffs["removed"],
        class_diffs["modified"],
        module_diffs["added"],
        module_diffs["removed"],
        module_diffs["modified"],
    ])

    if not has_changes:
        return None

    # Collect all changed class names for impact analysis
    changed_names = (
        [c.get("className") for c in class_diffs["added"]]
        + [c.get("className") for c in class_diffs["removed"]]
        + [d.get("className") for d in class_diffs["modified"]]
    )
    impact = compute_impact(changed_names, new_index)

    return build_change_record(
        git_meta or {},
        class_diffs,
        module_diffs,
        impact,
        index_filename,
    )
