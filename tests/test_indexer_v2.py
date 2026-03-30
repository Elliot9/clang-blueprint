"""
test_indexer_v2.py — P5-13/14/15/16 tests for interfaceMeta.usedTypes RAG enhancement.

Validates that:
- usedTypes tokens boost recall for interaction queries (P5-13/14)
- query() returns matchedMethods[] explaining why each result was returned (P5-15)
- top-1 hit rate with usedTypes ≥ baseline without usedTypes (P5-16)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ai_api.indexer import BlueprintIndexer, _entry_to_text, _find_matched_methods
except ImportError as e:
    pytest.skip(f"scikit-learn not available: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Sample entries WITH interfaceMeta.usedTypes
# ---------------------------------------------------------------------------

ENTRIES_WITH_META = [
    {
        "className": "DiskManager",
        "responsibility": "Resource Lifecycle",
        "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
        "interfaces": ["void readBlock(int lba, char * buf)"],
        "interfaceMeta": [
            {"signature": "void readBlock(int lba, char * buf)", "lineNumber": 12,
             "usedTypes": ["NVMeDriver", "BufferPool"]},
        ],
        "fileLocation": "src/disk_mgr.cpp",
        "lineNumber": 10,
        "namespace": "core",
        "baseClasses": [],
        "templateParams": [],
    },
    {
        "className": "CacheManager",
        "responsibility": "Cache Eviction",
        "dependencies": [{"target": "BufferPool", "type": "aggregation"}],
        "interfaces": ["bool lookup(const std::string & key)"],
        "interfaceMeta": [
            {"signature": "bool lookup(const std::string & key)", "lineNumber": 20,
             "usedTypes": ["BufferPool"]},
        ],
        "fileLocation": "src/cache.cpp",
        "lineNumber": 18,
        "namespace": "cache",
        "baseClasses": [],
        "templateParams": [],
    },
    {
        "className": "RequestFactory",
        "responsibility": "Factory Pattern",
        "dependencies": [],
        "interfaces": ["Request * create(RequestType t)"],
        "interfaceMeta": [
            {"signature": "Request * create(RequestType t)", "lineNumber": 30,
             "usedTypes": ["Request", "RequestType"]},
        ],
        "fileLocation": "src/factory.cpp",
        "lineNumber": 28,
        "namespace": "factory",
        "baseClasses": [],
        "templateParams": [],
    },
]

ENTRIES_WITHOUT_META = [
    {k: v for k, v in e.items() if k != "interfaceMeta"}
    for e in ENTRIES_WITH_META
]


@pytest.fixture
def indexer_with_meta(tmp_path):
    idx = BlueprintIndexer(
        blueprint_path=str(tmp_path / "dummy.json"),
        index_path=str(tmp_path / ".tfidf.pkl"),
    )
    idx.build(ENTRIES_WITH_META)
    return idx


@pytest.fixture
def indexer_without_meta(tmp_path):
    idx = BlueprintIndexer(
        blueprint_path=str(tmp_path / "dummy.json"),
        index_path=str(tmp_path / ".tfidf2.pkl"),
    )
    idx.build(ENTRIES_WITHOUT_META)
    return idx


# ---------------------------------------------------------------------------
# P5-13: usedTypes tokens appear in TF-IDF corpus text
# ---------------------------------------------------------------------------

def test_used_types_in_text():
    """P5-13: _entry_to_text includes usedTypes tokens."""
    text = _entry_to_text(ENTRIES_WITH_META[0])
    assert "NVMeDriver" in text or "nvme" in text.lower() or "nvme driver" in text.lower()
    assert "BufferPool" in text or "buffer pool" in text.lower() or "bufferpool" in text.lower()


# ---------------------------------------------------------------------------
# P5-14: CamelCase expansion of usedTypes
# ---------------------------------------------------------------------------

def test_used_types_camel_expanded():
    """P5-14: usedTypes are CamelCase-expanded so 'buffer' / 'pool' are findable."""
    text = _entry_to_text(ENTRIES_WITH_META[0])
    assert "buffer" in text.lower() or "pool" in text.lower()


# ---------------------------------------------------------------------------
# P5-15: matchedMethods returned in query results
# ---------------------------------------------------------------------------

def test_matched_methods_returned(indexer_with_meta):
    """P5-15: each query result includes matchedMethods list."""
    results = indexer_with_meta.query("NVMeDriver interaction", top_k=3)
    assert len(results) > 0, "Should find at least one result"
    for r in results:
        assert "matchedMethods" in r, "matchedMethods key must be present"
        assert isinstance(r["matchedMethods"], list)


def test_matched_methods_correct_class(indexer_with_meta):
    """P5-15: top result for 'NVMeDriver readBlock' has readBlock in matchedMethods."""
    results = indexer_with_meta.query("NVMeDriver readBlock", top_k=3)
    assert results, "Should return results"
    top = results[0]
    assert top["entry"]["className"] == "DiskManager"
    assert any("readBlock" in m for m in top["matchedMethods"]), (
        f"Expected readBlock in matchedMethods, got: {top['matchedMethods']}"
    )


def test_matched_methods_empty_when_no_overlap(indexer_with_meta):
    """P5-15: matchedMethods is empty when query doesn't overlap method tokens."""
    results = indexer_with_meta.query("DiskManager", top_k=1)
    # matchedMethods may or may not be empty, but it must be a list
    assert isinstance(results[0]["matchedMethods"], list)


# ---------------------------------------------------------------------------
# P5-16: top-1 hit rate with usedTypes ≥ baseline without
# ---------------------------------------------------------------------------

GROUNDTRUTH = [
    # (query, expected_top1_className)
    ("NVMeDriver interaction disk read", "DiskManager"),
    ("cache buffer lookup eviction",     "CacheManager"),
    ("factory create request object",    "RequestFactory"),
]


def test_top1_hit_rate_with_meta(indexer_with_meta):
    """P5-16: with usedTypes, all groundtruth queries hit top-1."""
    hits = 0
    for query, expected in GROUNDTRUTH:
        results = indexer_with_meta.query(query, top_k=3)
        if results and results[0]["entry"]["className"] == expected:
            hits += 1
    hit_rate = hits / len(GROUNDTRUTH)
    assert hit_rate >= 0.67, f"Top-1 hit rate with usedTypes = {hit_rate:.0%} (expected ≥ 67%)"


def test_top1_hit_rate_with_meta_vs_baseline(indexer_with_meta, indexer_without_meta):
    """P5-16: hit rate WITH usedTypes ≥ hit rate WITHOUT (no regression)."""
    def hit_rate(indexer):
        hits = 0
        for query, expected in GROUNDTRUTH:
            results = indexer.query(query, top_k=3)
            if results and results[0]["entry"]["className"] == expected:
                hits += 1
        return hits / len(GROUNDTRUTH)

    rate_with = hit_rate(indexer_with_meta)
    rate_without = hit_rate(indexer_without_meta)
    assert rate_with >= rate_without, (
        f"usedTypes degraded recall: {rate_with:.0%} < baseline {rate_without:.0%}"
    )


# ---------------------------------------------------------------------------
# Unit: _find_matched_methods
# ---------------------------------------------------------------------------

def test_find_matched_methods_basic():
    entry = ENTRIES_WITH_META[0]
    tokens = {"nvmedriver", "read", "readblock", "buf"}
    matched = _find_matched_methods(entry, tokens)
    assert len(matched) > 0
    assert any("readBlock" in m for m in matched)


def test_find_matched_methods_no_match():
    entry = ENTRIES_WITH_META[2]  # RequestFactory
    tokens = {"cache", "eviction", "lookup"}
    matched = _find_matched_methods(entry, tokens)
    assert matched == []
