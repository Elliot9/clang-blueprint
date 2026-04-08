"""
semantic_enricher.py — Heuristic-based semantic enrichment for blueprint entries.

Infers intent, designPattern, tradeoffs, and changeRisk from structural facts
already present in the AST scan result (list of class dicts).  No LLM required.

LLM-based enrichment (for ambiguous or low-confidence cases) is handled
separately by the ai_api layer and writes back to the same fields.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Name tokenisation helpers
# ---------------------------------------------------------------------------

def _split_camel(name: str) -> list[str]:
    """Split CamelCase or snake_case identifier into lowercase tokens."""
    tokens = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    tokens = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", tokens)
    return [t.lower() for t in tokens.replace("__", "_").split("_") if t]


# ---------------------------------------------------------------------------
# Design pattern detection
# ---------------------------------------------------------------------------

_SINGLETON_HINTS = {"instance", "get_instance", "getinstance", "singleton"}
_FACTORY_HINTS   = {"factory", "creator", "builder", "make", "create", "build"}
_OBSERVER_HINTS  = {"listener", "observer", "subscribe", "notify", "dispatch",
                    "event", "handler", "callback", "emit", "signal", "slot"}
_STRATEGY_HINTS  = {"strategy", "policy", "algorithm", "selector"}
_FACADE_HINTS    = {"facade", "manager", "coordinator", "mediator", "controller",
                    "gateway", "proxy", "adapter"}
_REPO_HINTS      = {"repository", "store", "dao", "registry", "cache", "index"}
_VISITOR_HINTS   = {"visitor", "walker", "traversal", "traverse"}


def _method_tokens(entry: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for sig in entry.get("interfaces", []):
        m = re.match(r"[\w:~*&<>\s]+?\b(\w+)\s*\(", sig)
        if m:
            tokens.update(_split_camel(m.group(1)))
    return tokens


def detect_design_pattern(entry: dict[str, Any]) -> str | None:
    name_tokens = set(_split_camel(entry.get("className", "")))
    method_tok  = _method_tokens(entry)
    all_tokens  = name_tokens | method_tok

    # Singleton: has a static "get_instance"-style method AND/OR is named so
    has_static_instance = bool(all_tokens & _SINGLETON_HINTS)
    has_private_ctor = any(
        pm.get("access") in ("private",) and entry.get("className", "") in pm.get("signature", "")
        for pm in entry.get("privateMethods", [])
    )
    if has_static_instance and (has_private_ctor or "singleton" in name_tokens):
        return "Singleton"

    # Factory: name or methods suggest object creation
    if name_tokens & _FACTORY_HINTS or (
        method_tok & {"create", "make", "build"} and not entry.get("baseClasses")
    ):
        return "Factory"

    # Observer / Event system
    if all_tokens & _OBSERVER_HINTS:
        return "Observer"

    # Strategy / Policy
    if all_tokens & _STRATEGY_HINTS:
        return "Strategy"

    # Visitor
    if all_tokens & _VISITOR_HINTS:
        return "Visitor"

    # Pure-virtual interface
    interfaces = entry.get("interfaces", [])
    if interfaces and all("= 0" in sig for sig in interfaces):
        return "Interface"

    # Facade / Manager (large surface, many deps)
    dep_count  = len(entry.get("dependencies", []))
    iface_count = len(interfaces)
    if (name_tokens & _FACADE_HINTS) or (dep_count >= 4 and iface_count >= 4):
        return "Facade"

    # Repository / Store
    if name_tokens & _REPO_HINTS:
        return "Repository"

    return None


# ---------------------------------------------------------------------------
# Intent inference
# ---------------------------------------------------------------------------

_VERB_MAP: dict[str, str] = {
    "manager":    "Manages",
    "handler":    "Handles",
    "parser":     "Parses",
    "builder":    "Builds",
    "factory":    "Creates",
    "reader":     "Reads",
    "writer":     "Writes",
    "loader":     "Loads",
    "serializer": "Serialises",
    "validator":  "Validates",
    "dispatcher": "Dispatches",
    "scheduler":  "Schedules",
    "allocator":  "Allocates",
    "pool":       "Pools",
    "cache":      "Caches",
    "registry":   "Registers",
    "router":     "Routes",
    "encoder":    "Encodes",
    "decoder":    "Decodes",
    "converter":  "Converts",
    "formatter":  "Formats",
    "observer":   "Observes",
    "listener":   "Listens to",
    "controller": "Controls",
    "provider":   "Provides",
    "collector":  "Collects",
    "tracker":    "Tracks",
    "monitor":    "Monitors",
    "executor":   "Executes",
    "runner":     "Runs",
    "broker":     "Brokers",
    "proxy":      "Proxies",
    "adapter":    "Adapts",
    "wrapper":    "Wraps",
    "bridge":     "Bridges",
    "guard":      "Guards",
    "resolver":   "Resolves",
    "connector":  "Connects",
    "scanner":    "Scans",
    "walker":     "Walks",
    "visitor":    "Visits",
    "indexer":    "Indexes",
    "finder":     "Finds",
    "selector":   "Selects",
    "filter":     "Filters",
    "comparator": "Compares",
    "sorter":     "Sorts",
    "merger":     "Merges",
    "splitter":   "Splits",
    "generator":  "Generates",
    "emitter":    "Emits",
    "sink":       "Consumes",
    "source":     "Produces",
}


def infer_intent(entry: dict[str, Any]) -> str | None:
    class_name = entry.get("className", "")
    tokens = _split_camel(class_name)
    if not tokens:
        return None

    for i, tok in enumerate(tokens):
        if tok in _VERB_MAP:
            subject_parts = [t for j, t in enumerate(tokens) if j != i]
            if subject_parts:
                subject = " ".join(subject_parts)
                return f"{_VERB_MAP[tok]} {subject}"

    # Fallback to responsibility if it's informative
    resp = entry.get("responsibility", "")
    if resp and resp not in ("Unknown", "", "Resource Lifecycle"):
        return resp

    return None


# ---------------------------------------------------------------------------
# Change risk
# ---------------------------------------------------------------------------

def infer_change_risk(
    entry: dict[str, Any],
    all_entries: list[dict[str, Any]],
) -> str:
    """
    Estimate modification risk from:
    - Reverse dependency count (how many other classes depend on this one)
    - Public interface size
    - Whether it is used as a base class
    """
    class_name = entry.get("className", "")

    reverse_dep_count = sum(
        1
        for e in all_entries
        if any(d.get("target") == class_name for d in e.get("dependencies", []))
    )

    interface_size = len(entry.get("interfaces", []))
    is_base = any(class_name in e.get("baseClasses", []) for e in all_entries)

    score = reverse_dep_count * 2 + interface_size + (5 if is_base else 0)

    if score >= 15:
        return "high"
    if score >= 6:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def enrich(
    entries: list[dict[str, Any]],
    *,
    overwrite: bool = False,
) -> None:
    """
    Enrich all class entry dicts in-place with heuristic semantic fields.

    Args:
        entries:   list of class dicts from blueprint_index (mutated in-place)
        overwrite: if False (default), skip fields already set
                   (e.g. previously written by LLM post-processing)
    """
    for entry in entries:
        if overwrite or not entry.get("designPattern"):
            pattern = detect_design_pattern(entry)
            if pattern:
                entry["designPattern"] = pattern

        if overwrite or not entry.get("intent"):
            intent = infer_intent(entry)
            if intent:
                entry["intent"] = intent

        if overwrite or not entry.get("changeRisk"):
            entry["changeRisk"] = infer_change_risk(entry, entries)

        # tradeoffs: intentionally left for LLM — heuristics cannot reliably infer these
