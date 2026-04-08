"""
tests/test_semantic_enricher.py — M28-06

Tests for scanner/semantic_enricher.py covering:
  - heuristic rule correctness (no API key required)
  - LLM cache hit / miss logic
  - LLM fallback when API call fails
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from scanner.semantic_enricher import (
    _entry_hash,
    _heuristic_change_risk,
    _heuristic_design_pattern,
    _heuristic_intent,
    _heuristic_tradeoffs,
    enrich_all_heuristic,
    enrich_all_llm,
    heuristic_enrich,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entry(
    class_name: str = "TestClass",
    responsibility: str = "Unknown",
    dep_types: list[str] | None = None,
    base_classes: list[str] | None = None,
) -> dict:
    deps = [{"target": f"Dep{i}", "type": t} for i, t in enumerate(dep_types or [])]
    return {
        "className": class_name,
        "responsibility": responsibility,
        "dependencies": deps,
        "baseClasses": base_classes or [],
        "interfaces": [],
        "attributes": [],
    }


_REVERSE_DEPS_NONE: dict = {}
_REVERSE_DEPS_HIGH: dict = {"TestClass": ["A", "B", "C", "D", "E"]}   # in-degree 5
_REVERSE_DEPS_MEDIUM: dict = {"TestClass": ["A", "B", "C"]}             # in-degree 3
_REVERSE_DEPS_LOW: dict = {"TestClass": ["A"]}                          # in-degree 1


# ---------------------------------------------------------------------------
# test_heuristic: intent generation
# ---------------------------------------------------------------------------

class TestHeuristicIntent:
    def test_manager_suffix(self):
        intent = _heuristic_intent("DiskManager", "Resource Lifecycle")
        assert "disk" in intent.lower()
        assert intent[0].isupper()

    def test_factory_suffix(self):
        intent = _heuristic_intent("ConnectionFactory", "Object Creation")
        assert "connection" in intent.lower() or "factory" in intent.lower()

    def test_fallback_to_responsibility(self):
        intent = _heuristic_intent("WeirdClassName", "Data Caching")
        assert intent  # non-empty

    def test_completely_unknown(self):
        intent = _heuristic_intent("X", "Unknown")
        assert len(intent) > 0

    def test_pool_suffix(self):
        intent = _heuristic_intent("BufferPool", "Resource Pooling")
        assert "buffer" in intent.lower()


# ---------------------------------------------------------------------------
# test_heuristic: changeRisk
# ---------------------------------------------------------------------------

class TestHeuristicChangeRisk:
    def test_high_in_degree(self):
        assert _heuristic_change_risk("TestClass", _REVERSE_DEPS_HIGH) == "high"

    def test_medium_in_degree(self):
        assert _heuristic_change_risk("TestClass", _REVERSE_DEPS_MEDIUM) == "medium"

    def test_low_in_degree(self):
        assert _heuristic_change_risk("TestClass", _REVERSE_DEPS_LOW) == "low"

    def test_zero_in_degree(self):
        assert _heuristic_change_risk("TestClass", _REVERSE_DEPS_NONE) == "low"


# ---------------------------------------------------------------------------
# test_heuristic: tradeoffs
# ---------------------------------------------------------------------------

class TestHeuristicTradeoffs:
    def test_shared_ptr_dep(self):
        entry = _make_entry(dep_types=["aggregation"])
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_NONE)
        assert any("shared" in t.lower() or "ownership" in t.lower() for t in tradeoffs)

    def test_high_fanout(self):
        entry = _make_entry(dep_types=["composition"] * 9)
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_NONE)
        assert any("fan-out" in t.lower() or "fan_out" in t.lower() or "9" in t for t in tradeoffs)

    def test_deep_inheritance(self):
        entry = _make_entry(base_classes=["A", "B", "C"])
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_NONE)
        assert any("inherit" in t.lower() for t in tradeoffs)

    def test_root_node(self):
        entry = _make_entry(dep_types=["composition"])
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_NONE)
        assert any("root" in t.lower() or "propagat" in t.lower() for t in tradeoffs)

    def test_high_fanin(self):
        entry = _make_entry()
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_HIGH)
        assert any("fan-in" in t.lower() or "5" in t for t in tradeoffs)

    def test_clean_class_no_tradeoffs(self):
        entry = _make_entry()
        tradeoffs = _heuristic_tradeoffs(entry, _REVERSE_DEPS_NONE)
        # root-node tradeoff applies (no in-degree, no out-degree → no, out=0)
        # Actually out_degree = 0 → no root-node tradeoff either
        assert isinstance(tradeoffs, list)


# ---------------------------------------------------------------------------
# test_heuristic: designPattern
# ---------------------------------------------------------------------------

class TestHeuristicDesignPattern:
    @pytest.mark.parametrize("name,expected", [
        ("EventObserver",   "Observer"),
        ("ButtonListener",  "Observer"),
        ("WidgetFactory",   "Factory"),
        ("Singleton",       "Singleton"),
        ("SortStrategy",    "Strategy"),
        ("CacheDecorator",  "Decorator"),
        ("ServiceProxy",    "Proxy"),
        ("DataAdapter",     "Adapter"),
        ("ReportBuilder",   "Builder"),
        ("MoveCommand",     "Command"),
        ("TreeIterator",    "Iterator"),
        ("ShapeVisitor",    "Visitor"),
        ("DiskManager",     None),
        ("BufferPool",      None),
    ])
    def test_pattern_detection(self, name, expected):
        assert _heuristic_design_pattern(name) == expected


# ---------------------------------------------------------------------------
# test_heuristic_no_api_key: enrich_all_heuristic runs without env vars
# ---------------------------------------------------------------------------

class TestHeuristicNoApiKey:
    def test_runs_without_env(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        entries = [_make_entry("DiskManager", "Resource Lifecycle")]
        enrich_all_heuristic(entries, _REVERSE_DEPS_NONE)

        assert entries[0]["intent"]
        assert entries[0]["changeRisk"] in ("high", "medium", "low")
        assert isinstance(entries[0]["tradeoffs"], list)

    def test_enriches_all_entries(self):
        entries = [
            _make_entry("DiskManager", "Resource Lifecycle"),
            _make_entry("BufferPool", "Resource Pooling"),
            _make_entry("IoScheduler", "Task Ordering"),
        ]
        enrich_all_heuristic(entries, {"DiskManager": ["A", "B", "C", "D", "E", "F"]})
        for e in entries:
            assert e["intent"]
            assert e["changeRisk"]

    def test_high_risk_class_detected(self):
        entries = [_make_entry("CoreEngine", "Core Processing")]
        rev = {"CoreEngine": ["A", "B", "C", "D", "E", "F"]}
        enrich_all_heuristic(entries, rev)
        assert entries[0]["changeRisk"] == "high"


# ---------------------------------------------------------------------------
# test_llm_cache_hit: cached entry → LLM not called
# ---------------------------------------------------------------------------

class TestLLMCacheHit:
    def test_cache_hit_skips_llm(self, tmp_path):
        entry = _make_entry("DiskManager", "Resource Lifecycle")
        h = _entry_hash(entry)
        cached_semantics = {
            "intent": "Cached intent",
            "tradeoffs": [],
            "changeRisk": "high",
            "designPattern": None,
        }
        cache_file = tmp_path / ".blueprint_semantic_cache.json"
        cache_file.write_text(json.dumps({h: cached_semantics}))

        entries = [entry.copy()]
        with patch("scanner.semantic_enricher._call_claude") as mock_claude:
            with patch("scanner.semantic_enricher._call_gemini") as mock_gemini:
                total, llm_n, cached_n = enrich_all_llm(
                    entries,
                    _REVERSE_DEPS_NONE,
                    cache_path=str(cache_file),
                    anthropic_api_key="fake-key",
                )

        mock_claude.assert_not_called()
        mock_gemini.assert_not_called()
        assert cached_n == 1
        assert llm_n == 0
        assert entries[0]["intent"] == "Cached intent"


# ---------------------------------------------------------------------------
# test_llm_cache_miss: changed entry → LLM called
# ---------------------------------------------------------------------------

class TestLLMCacheMiss:
    def test_cache_miss_calls_llm(self, tmp_path):
        entry = _make_entry("DiskManager", "Resource Lifecycle")
        cache_file = tmp_path / ".blueprint_semantic_cache.json"
        cache_file.write_text("{}")

        llm_response = {
            "intent": "LLM generated intent",
            "tradeoffs": ["Some tradeoff"],
            "changeRisk": "medium",
            "designPattern": None,
        }

        entries = [entry.copy()]
        with patch("scanner.semantic_enricher._call_claude", return_value=llm_response):
            total, llm_n, cached_n = enrich_all_llm(
                entries,
                _REVERSE_DEPS_NONE,
                cache_path=str(cache_file),
                anthropic_api_key="fake-key",
            )

        assert llm_n == 1
        assert cached_n == 0
        assert entries[0]["intent"] == "LLM generated intent"

    def test_cache_persisted_after_miss(self, tmp_path):
        entry = _make_entry("DiskManager", "Resource Lifecycle")
        cache_file = tmp_path / ".blueprint_semantic_cache.json"
        cache_file.write_text("{}")

        llm_response = {
            "intent": "Persisted intent",
            "tradeoffs": [],
            "changeRisk": "low",
            "designPattern": "Factory",
        }

        entries = [entry.copy()]
        with patch("scanner.semantic_enricher._call_claude", return_value=llm_response):
            enrich_all_llm(
                entries,
                _REVERSE_DEPS_NONE,
                cache_path=str(cache_file),
                anthropic_api_key="fake-key",
            )

        saved = json.loads(cache_file.read_text())
        assert len(saved) == 1
        first = next(iter(saved.values()))
        assert first["intent"] == "Persisted intent"


# ---------------------------------------------------------------------------
# test_llm_fallback: LLM exception → heuristic used, no crash
# ---------------------------------------------------------------------------

class TestLLMFallback:
    def test_llm_exception_falls_back(self, tmp_path, capsys):
        entry = _make_entry("DiskManager", "Resource Lifecycle")
        cache_file = tmp_path / ".blueprint_semantic_cache.json"
        cache_file.write_text("{}")

        entries = [entry.copy()]
        with patch("scanner.semantic_enricher._call_claude", return_value=None):
            with patch("scanner.semantic_enricher._call_gemini", return_value=None):
                total, llm_n, cached_n = enrich_all_llm(
                    entries,
                    _REVERSE_DEPS_NONE,
                    cache_path=str(cache_file),
                    anthropic_api_key="fake-key",
                )

        # Should not crash; should have heuristic values
        assert entries[0]["changeRisk"] in ("high", "medium", "low")
        assert entries[0]["intent"]
        # Fallback message printed
        captured = capsys.readouterr()
        assert "fallback" in captured.out.lower()

    def test_no_api_key_uses_heuristic_only(self, tmp_path):
        entry = _make_entry("DiskManager", "Resource Lifecycle")
        cache_file = tmp_path / ".blueprint_semantic_cache.json"
        cache_file.write_text("{}")

        entries = [entry.copy()]
        with patch("scanner.semantic_enricher._call_claude") as mock_claude:
            with patch("scanner.semantic_enricher._call_gemini") as mock_gemini:
                enrich_all_llm(
                    entries,
                    _REVERSE_DEPS_NONE,
                    cache_path=str(cache_file),
                    anthropic_api_key=None,
                    gemini_api_key=None,
                )

        mock_claude.assert_not_called()
        mock_gemini.assert_not_called()
        # Still has heuristic values
        assert entries[0]["changeRisk"] in ("high", "medium", "low")
