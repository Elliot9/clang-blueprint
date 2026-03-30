"""
test_indexer.py — Tests for ai_api/indexer.py (T-44)

Validates TF-IDF index build, query, serialization, and top-1 accuracy.
"""

from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ai_api.indexer import BlueprintIndexer, _entry_to_text
except ImportError as e:
    pytest.skip(f"scikit-learn not available: {e}", allow_module_level=True)


@pytest.fixture
def built_indexer(tmp_path):
    """A BlueprintIndexer pre-built with SAMPLE_ENTRIES, using a real temp dir."""
    indexer = BlueprintIndexer(
        blueprint_path=str(tmp_path / "dummy.json"),
        index_path=str(tmp_path / ".tfidf.pkl"),
    )
    indexer.build(SAMPLE_ENTRIES)
    return indexer


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ENTRIES = [
    {
        "className": "DiskManager",
        "responsibility": "Resource Lifecycle",
        "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
        "interfaces": ["void readBlock(int lba, char * buf)", "void writeBlock(int lba, const char * buf)"],
        "fileLocation": "src/core/disk_mgr.cpp",
        "lineNumber": 10,
        "namespace": "core",
        "baseClasses": ["IoBase"],
        "templateParams": [],
    },
    {
        "className": "NVMeController",
        "responsibility": "Orchestration",
        "dependencies": [],
        "interfaces": ["void submitIO()", "void pollCompletion()"],
        "fileLocation": "src/nvme/controller.cpp",
        "lineNumber": 5,
        "namespace": "nvme",
        "baseClasses": [],
        "templateParams": [],
    },
    {
        "className": "BufferPool",
        "responsibility": "Resource Pooling",
        "dependencies": [],
        "interfaces": ["char * allocate(int size)", "void release(char * ptr)"],
        "fileLocation": "src/mem/buffer_pool.cpp",
        "lineNumber": 20,
        "namespace": "mem",
        "baseClasses": [],
        "templateParams": [],
    },
    {
        "className": "CacheManager",
        "responsibility": "Data Caching",
        "dependencies": [],
        "interfaces": ["void put(const K & key, const V & val)", "V get(const K & key)"],
        "fileLocation": "src/cache/cache_mgr.cpp",
        "lineNumber": 1,
        "namespace": "cache",
        "baseClasses": [],
        "templateParams": ["K", "V"],
    },
    {
        "className": "EventHandler",
        "responsibility": "Event Processing",
        "dependencies": [],
        "interfaces": ["void onEvent(Event e)", "void subscribe(EventType t)"],
        "fileLocation": "src/event/handler.cpp",
        "lineNumber": 8,
        "namespace": "event",
        "baseClasses": [],
        "templateParams": [],
    },
]


# ---------------------------------------------------------------------------
# Tests: _entry_to_text
# ---------------------------------------------------------------------------

def test_entry_to_text_includes_classname():
    entry = SAMPLE_ENTRIES[0]
    text = _entry_to_text(entry)
    assert "DiskManager" in text


def test_entry_to_text_includes_responsibility():
    entry = SAMPLE_ENTRIES[0]
    text = _entry_to_text(entry)
    assert "Resource" in text or "Lifecycle" in text


def test_entry_to_text_includes_interfaces():
    entry = SAMPLE_ENTRIES[0]
    text = _entry_to_text(entry)
    assert "readBlock" in text or "writeBlock" in text


def test_entry_to_text_includes_attributes():
    entry = {
        **SAMPLE_ENTRIES[0],
        "attributes": ["-std::unique_ptr<NVMeDriver> driver_"],
    }
    text = _entry_to_text(entry)
    assert "driver_" in text and "NVMeDriver" in text


def test_entry_to_text_camelcase_expanded():
    entry = {"className": "DiskManager", "responsibility": "", "dependencies": [],
             "interfaces": [], "baseClasses": [], "templateParams": [], "namespace": ""}
    text = _entry_to_text(entry)
    # CamelCase expanded: "Disk Manager"
    assert "Disk" in text and "Manager" in text


# ---------------------------------------------------------------------------
# Tests: build & query
# ---------------------------------------------------------------------------

def test_build_creates_index(built_indexer):
    assert built_indexer.is_built
    assert built_indexer.num_docs == len(SAMPLE_ENTRIES)


def test_query_returns_results(built_indexer):
    results = built_indexer.query("disk I/O manager", top_k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all("score" in r and "entry" in r for r in results)


def test_query_top1_disk_io(built_indexer):
    """DiskManager should rank first for a disk I/O query."""
    results = built_indexer.query("disk block read write I/O", top_k=5)
    assert results, "No results returned"
    assert results[0]["entry"]["className"] == "DiskManager", (
        f"Expected DiskManager as top-1, got {results[0]['entry']['className']}"
    )


def test_query_top1_nvme_submission(built_indexer):
    """NVMeController should rank first for NVMe submission queue queries."""
    results = built_indexer.query("NVMe submit IO completion poll", top_k=5)
    assert results
    assert results[0]["entry"]["className"] == "NVMeController", (
        f"Expected NVMeController as top-1, got {results[0]['entry']['className']}"
    )


def test_query_top1_cache(built_indexer):
    """CacheManager should rank first for cache queries."""
    results = built_indexer.query("cache key value store get put", top_k=5)
    assert results
    assert results[0]["entry"]["className"] == "CacheManager", (
        f"Expected CacheManager as top-1, got {results[0]['entry']['className']}"
    )


def test_query_results_sorted_descending(built_indexer):
    """Results must be sorted by descending score."""
    results = built_indexer.query("buffer memory allocation", top_k=5)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"


def test_query_empty_string_returns_empty(built_indexer):
    results = built_indexer.query("   ", top_k=5)
    assert results == []


def test_query_top_k_limit(built_indexer):
    results = built_indexer.query("manager", top_k=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Tests: serialization (T-43)
# ---------------------------------------------------------------------------

def test_save_and_load_index(tmp_path):
    index_path = str(tmp_path / ".blueprint_tfidf.pkl")
    indexer = BlueprintIndexer(blueprint_path="/dev/null", index_path=index_path)
    indexer.build(SAMPLE_ENTRIES)

    # Load in a fresh instance
    indexer2 = BlueprintIndexer(blueprint_path="/dev/null", index_path=index_path)
    loaded = indexer2.load()
    assert loaded, "load() returned False"
    assert indexer2.num_docs == len(SAMPLE_ENTRIES)

    # Queries should work on loaded index
    results = indexer2.query("disk I/O", top_k=3)
    assert results


def test_load_missing_index_returns_false(tmp_path):
    indexer = BlueprintIndexer(
        blueprint_path="/dev/null",
        index_path=str(tmp_path / "nonexistent.pkl")
    )
    assert not indexer.load()


def test_atomic_write_no_tmp_file(tmp_path):
    index_path = str(tmp_path / ".blueprint_tfidf.pkl")
    indexer = BlueprintIndexer(blueprint_path="/dev/null", index_path=index_path)
    indexer.build(SAMPLE_ENTRIES)
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Temp file(s) left behind: {tmp_files}"


# ---------------------------------------------------------------------------
# Tests: query_batch
# ---------------------------------------------------------------------------

def test_query_batch(built_indexer):
    queries = ["disk I/O", "event handling", "memory buffer"]
    results = built_indexer.query_batch(queries, top_k=3)
    assert len(results) == 3
    for r in results:
        assert isinstance(r, list)


# ---------------------------------------------------------------------------
# Tests: top_terms introspection
# ---------------------------------------------------------------------------

def test_top_terms_returns_list(built_indexer):
    terms = built_indexer.top_terms("DiskManager", n=5)
    assert isinstance(terms, list)
    assert len(terms) <= 5


def test_top_terms_unknown_class_returns_empty(built_indexer):
    terms = built_indexer.top_terms("NonExistentClass")
    assert terms == []
