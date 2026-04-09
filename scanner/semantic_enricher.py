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
    """Build a prompt for LLM enrichment of a single class."""
    deps_summary = ", ".join(
        f"{d['target']}({d['type']})"
        for d in entry.get("dependencies", [])[:8]
    )
    ifaces = entry.get("interfaces", [])[:6]
    tradeoffs_hint = "; ".join(heuristic.get("tradeoffs", [])[:2])
    return (
        "You are a senior C++ architect analyzing a class. "
        "Return ONLY a JSON object with these exact keys:\n"
        '  "intent": 2-3 sentences explaining what this class does, why it exists, '
        "and its role in the system. Be specific, not generic.\n"
        '  "tradeoffs": array of strings (max 3), each a concrete design trade-off or risk '
        "specific to this class (e.g. memory ownership, thread-safety, coupling).\n"
        '  "changeRisk": exactly one of "high", "medium", or "low".\n'
        '  "designPattern": one GoF pattern name if clearly applicable, or null.\n\n'
        f"Class: {entry.get('className')}\n"
        f"Namespace: {entry.get('namespace') or 'global'}\n"
        f"Responsibility: {entry.get('responsibility')}\n"
        f"Dependencies ({len(entry.get('dependencies', []))} total, first 8): {deps_summary or 'none'}\n"
        f"Public methods (first 6): {'; '.join(ifaces) or 'none'}\n"
        f"Base classes: {', '.join(entry.get('baseClasses', [])) or 'none'}\n\n"
        "Heuristic baseline (use as starting point, improve with domain reasoning):\n"
        f"  intent: {heuristic['intent']}\n"
        f"  changeRisk: {heuristic['changeRisk']}\n"
        f"  designPattern: {heuristic.get('designPattern')}\n"
        f"  tradeoffs: {tradeoffs_hint or 'none detected'}\n\n"
        "Return ONLY the JSON object. No markdown, no explanation, no extra keys."
    )


def _llm_prompt_module(module: dict, top_classes: list[dict]) -> str:
    """Build a prompt for LLM module-level summary."""
    class_names = module.get("classNames", [])
    ext_deps = [d["target"] for d in module.get("externalDeps", [])[:5]]
    key_classes = [c.get("className") for c in top_classes[:5]]
    intents = [
        f"{c.get('className')}: {c.get('intent', c.get('responsibility', ''))}"
        for c in top_classes[:4]
        if c.get("intent") or c.get("responsibility")
    ]
    return (
        "You are a senior C++ architect. Write a module summary for a wiki knowledge base.\n"
        "Return ONLY a JSON object with one key:\n"
        '  "summary": 2-3 sentences describing the module\'s purpose, its role in the '
        "system, and the key design decisions it encapsulates. Be specific and informative.\n\n"
        f"Module: {module.get('name')}\n"
        f"Namespace: {module.get('namespace') or 'n/a'}\n"
        f"Classes ({len(class_names)} total): {', '.join(class_names[:10])}\n"
        f"Key class intents:\n" + "\n".join(f"  - {i}" for i in intents) + "\n"
        f"External dependencies: {', '.join(ext_deps) or 'none'}\n"
        f"Internal edges: {module.get('internalEdgeCount', 0)}\n\n"
        "Return ONLY the JSON object. No markdown, no explanation."
    )


def _llm_prompt_project(
    project_name: str,
    modules: list[dict],
    entry_points: list[dict],
    class_count: int,
) -> str:
    """Build a prompt for LLM project-level summary."""
    mod_names = [m.get("name", "") for m in modules[:10]]
    ep_names = [ep.get("className", "") for ep in entry_points[:5]]
    mod_summaries = [
        f"{m.get('name')}: {m.get('summary', '')}"
        for m in modules[:6]
        if m.get("summary")
    ]
    return (
        "You are a senior C++ architect. Write a project overview for a wiki knowledge base.\n"
        "Return ONLY a JSON object with one key:\n"
        '  "projectSummary": 2-3 sentences describing what this project does, '
        "its architectural style, and what problem it solves. "
        "Be specific — avoid generic descriptions.\n\n"
        f"Project: {project_name}\n"
        f"Total classes: {class_count}\n"
        f"Modules ({len(modules)} total): {', '.join(mod_names)}\n"
        f"Entry points: {', '.join(ep_names) or 'none detected'}\n"
        + (
            "Module summaries:\n" + "\n".join(f"  - {s}" for s in mod_summaries) + "\n"
            if mod_summaries else ""
        )
        + "\nReturn ONLY the JSON object. No markdown, no explanation."
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
    """Ensure LLM class response has the required fields with correct types."""
    if not isinstance(result, dict):
        return None
    if not isinstance(result.get("intent"), str) or not result["intent"].strip():
        return None
    if result.get("changeRisk") not in ("high", "medium", "low"):
        return None
    if not isinstance(result.get("tradeoffs"), list):
        return None
    return result


def _validate_module_result(result: Any) -> str | None:
    """Ensure LLM module response has a non-empty summary string."""
    if not isinstance(result, dict):
        return None
    s = result.get("summary", "")
    return s.strip() if isinstance(s, str) and s.strip() else None


def _validate_project_result(result: Any) -> str | None:
    """Ensure LLM project response has a non-empty projectSummary string."""
    if not isinstance(result, dict):
        return None
    s = result.get("projectSummary", "")
    return s.strip() if isinstance(s, str) and s.strip() else None


def _call_llm(prompt: str, anthropic_api_key: str | None, gemini_api_key: str | None) -> dict | None:
    """Try Anthropic then Gemini; return parsed dict or None."""
    result = None
    if anthropic_api_key:
        result = _call_claude(prompt, anthropic_api_key)
    if result is None and gemini_api_key:
        result = _call_gemini(prompt, gemini_api_key)
    return result


def _module_hash(module: dict) -> str:
    """Stable hash for a module (keyed on structure, not summary)."""
    key = {
        "name": module.get("name", ""),
        "classNames": sorted(module.get("classNames", [])),
        "externalDeps": sorted(d.get("target", "") for d in module.get("externalDeps", [])),
    }
    payload = json.dumps(key, sort_keys=True, ensure_ascii=False)
    return "mod:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _project_hash(modules: list[dict], entry_points: list[dict]) -> str:
    """Stable hash for the project-level summary."""
    key = {
        "modules": sorted(m.get("name", "") for m in modules),
        "entryPoints": sorted(ep.get("className", "") for ep in entry_points),
    }
    payload = json.dumps(key, sort_keys=True, ensure_ascii=False)
    return "proj:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def enrich_modules_llm(
    modules: list[dict],
    classes: list[dict],
    cache: dict,
    anthropic_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> tuple[int, int]:
    """
    Generate LLM summaries for each module in-place.
    Returns (llm_called, cache_hit).
    """
    class_by_name = {c.get("className"): c for c in classes}
    llm_called = cache_hit = 0

    for module in modules:
        h = _module_hash(module)
        if h in cache and cache[h].get("summary"):
            module["summary"] = cache[h]["summary"]
            cache_hit += 1
            continue

        top_classes = [
            class_by_name[n]
            for n in module.get("classNames", [])
            if n in class_by_name
        ][:6]

        prompt = _llm_prompt_module(module, top_classes)
        raw = _call_llm(prompt, anthropic_api_key, gemini_api_key)
        summary = _validate_module_result(raw)

        if summary:
            module["summary"] = summary
            cache[h] = {"summary": summary}
        else:
            # Fallback: use summarySeed as prose
            module["summary"] = module.get("summarySeed", "")
            print(f"  [enricher] LLM failed for module {module.get('name')}, using seed fallback")

        llm_called += 1

    return llm_called, cache_hit


def enrich_project_llm(
    index: dict,
    cache: dict,
    anthropic_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> tuple[int, int]:
    """
    Generate LLM project-level summary in-place on the index dict.
    Returns (llm_called, cache_hit).
    """
    modules = index.get("modules", [])
    entry_points = index.get("entryPoints", [])
    classes = index.get("classes", [])
    project_name = index.get("projectName", "Unknown Project")

    h = _project_hash(modules, entry_points)
    if h in cache and cache[h].get("projectSummary"):
        index["projectSummary"] = cache[h]["projectSummary"]
        return 0, 1

    prompt = _llm_prompt_project(project_name, modules, entry_points, len(classes))
    raw = _call_llm(prompt, anthropic_api_key, gemini_api_key)
    summary = _validate_project_result(raw)

    if summary:
        index["projectSummary"] = summary
        cache[h] = {"projectSummary": summary}
        return 1, 0
    else:
        print("  [enricher] LLM failed for project summary, skipping")
        return 1, 0


def enrich_all_llm(
    entries: list[dict],
    reverse_deps: dict[str, list[str]],
    cache_path: str = ".blueprint_semantic_cache.json",
    anthropic_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> tuple[int, int, int]:
    """
    LLM enrichment of class entries with incremental cache.

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

        prompt = _llm_prompt(entry, heuristic)
        raw = _call_llm(prompt, anthropic_api_key, gemini_api_key)
        llm_result = _validate_llm_result(raw)

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


def enrich_index_llm(
    index: dict,
    reverse_deps: dict[str, list[str]],
    cache_path: str = ".blueprint_semantic_cache.json",
    anthropic_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> dict[str, int]:
    """
    Full LLM enrichment: class entries + module summaries + project summary.

    Mutates `index` in-place. Returns stats dict.
    """
    cache = _load_cache(cache_path)
    entries = index.get("classes", [])
    modules = index.get("modules", [])

    # 1. Class-level enrichment
    total, class_llm, class_cached = enrich_all_llm(
        entries, reverse_deps, cache_path, anthropic_api_key, gemini_api_key
    )
    # Reload cache (enrich_all_llm may have updated it)
    cache = _load_cache(cache_path)

    # 2. Module-level summaries
    mod_llm, mod_cached = enrich_modules_llm(
        modules, entries, cache, anthropic_api_key, gemini_api_key
    )

    # 3. Project-level summary
    proj_llm, proj_cached = enrich_project_llm(
        index, cache, anthropic_api_key, gemini_api_key
    )

    _save_cache(cache, cache_path)

    return {
        "classes_total": total,
        "classes_llm": class_llm,
        "classes_cached": class_cached,
        "modules_llm": mod_llm,
        "modules_cached": mod_cached,
        "project_llm": proj_llm,
        "project_cached": proj_cached,
    }
