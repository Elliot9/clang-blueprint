"""
scanner/semantic_enricher.py — M28-02/M28-03

Semantic enrichment for ClassEntry dicts.

Two modes:
  1. Heuristic (default, no API key needed):
       enrich_all_heuristic(entries, reverse_deps) → in-place update

  2. LLM (opt-in, requires ANTHROPIC_API_KEY or GEMINI_API_KEY):
       enrich_all_llm(entries, reverse_deps, cache_path, api_key) → in-place update
       Falls back to heuristic when LLM fails or api_key is absent.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import tempfile
from typing import Any

# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

def _split_camel(name: str) -> list[str]:
    """DiskManager → ['Disk', 'Manager']"""
    words = re.sub(r"([A-Z][a-z]+)", r" \1", re.sub(r"([A-Z]+(?=[A-Z][a-z])|[A-Z]+$)", r" \1", name)).split()
    return [w for w in words if w]


_VERB_TEMPLATES: dict[str, str] = {
    "manager":    "Manages {noun}",
    "factory":    "Creates {noun} instances",
    "pool":       "Pools {noun} resources",
    "cache":      "Caches {noun} data",
    "handler":    "Handles {noun} events",
    "scheduler":  "Schedules {noun} tasks",
    "controller": "Controls {noun} lifecycle",
    "dispatcher": "Dispatches {noun} events",
    "observer":   "Observes {noun} changes",
    "builder":    "Builds {noun} objects",
    "parser":     "Parses {noun} data",
    "serializer": "Serializes {noun}",
    "validator":  "Validates {noun}",
    "queue":      "Queues {noun} work items",
    "listener":   "Listens for {noun} events",
    "engine":     "Core {noun} processing engine",
    "service":    "Provides {noun} services",
    "repository": "Stores and retrieves {noun}",
    "adapter":    "Adapts {noun} interface",
    "proxy":      "Proxies access to {noun}",
    "provider":   "Provides {noun} data",
    "driver":     "Drives {noun} hardware",
    "allocator":  "Allocates {noun} memory",
    "registry":   "Registers and looks up {noun}",
    "tracker":    "Tracks {noun} state",
    "collector":  "Collects {noun} data",
    "iterator":   "Iterates over {noun}",
    "visitor":    "Visits {noun} nodes",
    "watcher":    "Watches {noun} changes",
}

_PATTERN_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Observer|Listener|Subscriber", re.I),  "Observer"),
    (re.compile(r"Factory|Creator|Spawner",      re.I),  "Factory"),
    (re.compile(r"Singleton",                    re.I),  "Singleton"),
    (re.compile(r"Strategy|Policy|Algorithm",    re.I),  "Strategy"),
    (re.compile(r"Decorator|Wrapper",            re.I),  "Decorator"),
    (re.compile(r"Proxy",                        re.I),  "Proxy"),
    (re.compile(r"Adapter|Bridge",               re.I),  "Adapter"),
    (re.compile(r"Facade",                       re.I),  "Facade"),
    (re.compile(r"Builder",                      re.I),  "Builder"),
    (re.compile(r"Command",                      re.I),  "Command"),
    (re.compile(r"Iterator",                     re.I),  "Iterator"),
    (re.compile(r"Visitor",                      re.I),  "Visitor"),
    (re.compile(r"Composite",                    re.I),  "Composite"),
    (re.compile(r"Mediator",                     re.I),  "Mediator"),
    (re.compile(r"Flyweight",                    re.I),  "Flyweight"),
]


def _heuristic_intent(class_name: str, responsibility: str) -> str:
    words = _split_camel(class_name)
    last = words[-1].lower() if words else ""
    noun = " ".join(words[:-1]).lower() if len(words) > 1 else class_name.lower()
    noun = noun.strip() or class_name.lower()

    if last in _VERB_TEMPLATES:
        return _VERB_TEMPLATES[last].format(noun=noun).capitalize()

    if responsibility and responsibility not in ("Unknown", ""):
        return f"{responsibility}: {' '.join(words).lower()}"

    return f"Handles {' '.join(words).lower()} operations"


def _heuristic_tradeoffs(entry: dict, reverse_deps: dict[str, list[str]]) -> list[str]:
    result: list[str] = []
    deps: list[dict] = entry.get("dependencies", [])
    class_name: str = entry.get("className", "")

    agg_count = sum(1 for d in deps if d.get("type") == "aggregation")
    out_degree = len(deps)
    in_degree = len(reverse_deps.get(class_name, []))
    base_count = len(entry.get("baseClasses", []))

    if agg_count > 0:
        result.append(
            f"Shared ownership ({agg_count} shared_ptr/weak_ptr dep{'s' if agg_count > 1 else ''}) "
            "may cause lifecycle ambiguity"
        )
    if out_degree > 8:
        result.append(
            f"High fan-out ({out_degree} dependencies) — potential god-class, consider decomposing"
        )
    if base_count > 2:
        result.append(
            f"Deep inheritance ({base_count} base classes) increases coupling and reduces flexibility"
        )
    if in_degree == 0 and out_degree > 0:
        result.append(
            "Root node — not depended on by others; changes here propagate downward widely"
        )
    if in_degree >= 5:
        result.append(
            f"High fan-in ({in_degree} dependents) — changes here have wide blast radius"
        )

    return result


def _heuristic_change_risk(class_name: str, reverse_deps: dict[str, list[str]]) -> str:
    in_degree = len(reverse_deps.get(class_name, []))
    if in_degree >= 5:
        return "high"
    if in_degree >= 2:
        return "medium"
    return "low"


def _heuristic_design_pattern(class_name: str) -> str | None:
    for pattern, label in _PATTERN_KEYWORDS:
        if pattern.search(class_name):
            return label
    return None


def heuristic_enrich(entry: dict, reverse_deps: dict[str, list[str]]) -> dict:
    """
    Compute and return semantic fields for a single ClassEntry dict.
    Pure function — does not mutate the input.
    """
    class_name: str = entry.get("className", "")
    responsibility: str = entry.get("responsibility", "")

    return {
        "intent": _heuristic_intent(class_name, responsibility),
        "tradeoffs": _heuristic_tradeoffs(entry, reverse_deps),
        "changeRisk": _heuristic_change_risk(class_name, reverse_deps),
        "designPattern": _heuristic_design_pattern(class_name),
    }


def enrich_all_heuristic(
    entries: list[dict],
    reverse_deps: dict[str, list[str]],
) -> None:
    """
    In-place heuristic enrichment of all entries.
    Always runs; no API key required.
    """
    for entry in entries:
        semantics = heuristic_enrich(entry, reverse_deps)
        entry.update(semantics)


# ---------------------------------------------------------------------------
# LLM enrichment (opt-in)
# ---------------------------------------------------------------------------

def _entry_hash(entry: dict) -> str:
    """Stable hash of the structurally meaningful parts of a ClassEntry."""
    key_fields = {
        "className":    entry.get("className", ""),
        "responsibility": entry.get("responsibility", ""),
        "interfaces":   sorted(entry.get("interfaces", [])),
        "dependencies": sorted(
            (d.get("target", ""), d.get("type", ""))
            for d in entry.get("dependencies", [])
        ),
        "baseClasses":  sorted(entry.get("baseClasses", [])),
    }
    payload = json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_cache(cache_path: str) -> dict[str, dict]:
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache: dict[str, dict], cache_path: str) -> None:
    dir_path = os.path.dirname(os.path.abspath(cache_path))
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=dir_path, delete=False, suffix=".tmp"
    ) as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp = f.name
    os.replace(tmp, cache_path)


def _llm_prompt(entry: dict, heuristic: dict) -> str:
    """Build a compact prompt for LLM enrichment of a single class."""
    deps_summary = ", ".join(
        f"{d['target']}({d['type']})"
        for d in entry.get("dependencies", [])[:5]
    )
    ifaces = entry.get("interfaces", [])[:5]
    return (
        "You are analyzing a C++ class. Return ONLY a JSON object with these keys:\n"
        '  "intent": one sentence (≤20 words) describing what this class does\n'
        '  "tradeoffs": array of strings, each a specific design trade-off or risk (max 3)\n'
        '  "changeRisk": exactly one of "high", "medium", or "low"\n'
        '  "designPattern": one of the GoF pattern names, or null\n\n'
        f"Class: {entry.get('className')}\n"
        f"Responsibility: {entry.get('responsibility')}\n"
        f"Dependencies: {deps_summary or 'none'}\n"
        f"Public methods (first 5): {'; '.join(ifaces) or 'none'}\n"
        f"Base classes: {', '.join(entry.get('baseClasses', [])) or 'none'}\n\n"
        "Baseline heuristic (use as reference, improve if you can):\n"
        f"  intent: {heuristic['intent']}\n"
        f"  changeRisk: {heuristic['changeRisk']}\n"
        f"  designPattern: {heuristic['designPattern']}\n\n"
        "Return ONLY the JSON object, no markdown, no explanation."
    )


def _call_claude(prompt: str, api_key: str) -> dict | None:
    """Call Claude Haiku via the Anthropic API. Returns parsed dict or None."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return None


def _call_gemini(prompt: str, api_key: str) -> dict | None:
    """Call Gemini Flash via google-generativeai. Returns parsed dict or None."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return None


def _validate_llm_result(result: Any) -> dict | None:
    """Ensure LLM response has the required fields with correct types."""
    if not isinstance(result, dict):
        return None
    if not isinstance(result.get("intent"), str) or not result["intent"].strip():
        return None
    if result.get("changeRisk") not in ("high", "medium", "low"):
        return None
    if not isinstance(result.get("tradeoffs"), list):
        return None
    return result


def enrich_all_llm(
    entries: list[dict],
    reverse_deps: dict[str, list[str]],
    cache_path: str = ".blueprint_semantic_cache.json",
    anthropic_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> tuple[int, int, int]:
    """
    LLM enrichment with incremental cache.

    Returns (total, llm_called, cache_hit) counts.
    Falls back to heuristic per-entry when LLM fails.
    """
    cache = _load_cache(cache_path)
    llm_called = 0
    cache_hit = 0
    cache_dirty = False

    for entry in entries:
        class_name = entry.get("className", "")
        h = _entry_hash(entry)
        heuristic = heuristic_enrich(entry, reverse_deps)

        if h in cache:
            entry.update(cache[h])
            cache_hit += 1
            continue

        # Try LLM
        prompt = _llm_prompt(entry, heuristic)
        llm_result: dict | None = None

        if anthropic_api_key:
            llm_result = _validate_llm_result(_call_claude(prompt, anthropic_api_key))
        if llm_result is None and gemini_api_key:
            llm_result = _validate_llm_result(_call_gemini(prompt, gemini_api_key))

        semantics = llm_result if llm_result is not None else heuristic
        entry.update(semantics)
        cache[h] = semantics
        cache_dirty = True
        llm_called += 1

        if llm_result is None and (anthropic_api_key or gemini_api_key):
            print(f"  [enricher] LLM failed for {class_name}, using heuristic fallback")

    if cache_dirty:
        _save_cache(cache, cache_path)

    return len(entries), llm_called, cache_hit
