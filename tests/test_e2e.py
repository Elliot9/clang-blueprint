"""
test_e2e.py — T-54: End-to-end integration test

Pipeline:
  C++ source → ast_parser → blueprint_index.json → indexer → /query API

Uses the examples/storage_engine fixture as the test project.
Requires: libclang, scikit-learn, fastapi/httpx
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from scanner.ast_parser import parse_files
    from ai_api.indexer import BlueprintIndexer
    from fastapi.testclient import TestClient
    from ai_api.server import app, state
except ImportError as e:
    pytest.skip(f"Required dependency not available: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Inline C++ fixture (so test doesn't depend on examples/ directory)
# ---------------------------------------------------------------------------

STORAGE_ENGINE_CPP = """\
#include <memory>
#include <vector>

class IoBase {
public:
    virtual void open()  = 0;
    virtual void close() = 0;
};

class NVMeDriver {
public:
    void init();
    void shutdown();
};

class BufferPool {
public:
    char* allocate(int size);
    void  release(char* ptr);
};

/// Handles low-level disk I/O and partitioning
class DiskManager : public IoBase {
    std::unique_ptr<NVMeDriver>  driver_;
    std::shared_ptr<BufferPool>  buf_pool_;
    std::vector<int>             lba_map_;

public:
    void open()  override;
    void close() override;
    void readBlock(int lba, char* buf);
    void writeBlock(int lba, const char* buf);
};

class NVMeController {
    NVMeDriver* drv_;
public:
    void submitIO();
    void pollCompletion();
};
"""


# ---------------------------------------------------------------------------
# T-54: Full pipeline test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline_output(tmp_path_factory):
    """
    Run the full scan → index → query pipeline on an inline C++ fixture.
    Returns (blueprint_entries, indexer, test_client).
    """
    tmp = tmp_path_factory.mktemp("e2e")
    cpp_file = tmp / "storage_engine.cpp"
    cpp_file.write_text(STORAGE_ENGINE_CPP)

    # ── Step 1: Parse C++ → blueprint entries ─────────────────────────────
    entries = parse_files(
        [str(cpp_file)],
        project_root=str(tmp),
        extra_args=["-std=c++14", "-x", "c++"],
    )
    assert entries, "ast_parser returned no entries"

    # ── Step 2: Write blueprint_index.json ────────────────────────────────
    index_file = tmp / "blueprint_index.json"
    index_file.write_text(json.dumps(entries, indent=2))

    # ── Step 3: Build TF-IDF index ────────────────────────────────────────
    pkl_path = str(tmp / ".tfidf.pkl")
    indexer = BlueprintIndexer(
        blueprint_path=str(index_file),
        index_path=pkl_path,
    )
    indexer.build(entries)
    assert indexer.is_built

    # ── Step 4: Wire into FastAPI test client ─────────────────────────────
    state.indexer = indexer
    state.rebuild_in_progress = False
    os.environ["BLUEPRINT_INDEX_PATH"] = str(index_file)

    client = TestClient(app, raise_server_exceptions=True)
    return entries, indexer, client


# ── Assertions ────────────────────────────────────────────────────────────

def test_e2e_classes_parsed(pipeline_output):
    entries, _, _ = pipeline_output
    class_names = [e["className"] for e in entries]
    assert "DiskManager"    in class_names, f"DiskManager missing: {class_names}"
    assert "NVMeController" in class_names, f"NVMeController missing: {class_names}"
    assert "NVMeDriver"     in class_names, f"NVMeDriver missing: {class_names}"
    assert "BufferPool"     in class_names, f"BufferPool missing: {class_names}"


def test_e2e_disk_manager_has_composition(pipeline_output):
    entries, _, _ = pipeline_output
    dm = next(e for e in entries if e["className"] == "DiskManager")
    dep_types = {d["target"]: d["type"] for d in dm["dependencies"]}
    assert dep_types.get("NVMeDriver") == "composition", f"deps: {dep_types}"


def test_e2e_disk_manager_has_aggregation(pipeline_output):
    entries, _, _ = pipeline_output
    dm = next(e for e in entries if e["className"] == "DiskManager")
    dep_types = {d["target"]: d["type"] for d in dm["dependencies"]}
    assert dep_types.get("BufferPool") == "aggregation", f"deps: {dep_types}"


def test_e2e_disk_manager_inherits_iobase(pipeline_output):
    entries, _, _ = pipeline_output
    dm = next(e for e in entries if e["className"] == "DiskManager")
    assert "IoBase" in dm["baseClasses"], f"baseClasses: {dm['baseClasses']}"


def test_e2e_interfaces_extracted(pipeline_output):
    entries, _, _ = pipeline_output
    dm = next(e for e in entries if e["className"] == "DiskManager")
    assert any("readBlock"  in sig for sig in dm["interfaces"])
    assert any("writeBlock" in sig for sig in dm["interfaces"])


def test_e2e_index_queryable(pipeline_output):
    _, indexer, _ = pipeline_output
    results = indexer.query("disk I/O read write block", top_k=3)
    assert results, "Index returned no results"
    assert results[0]["entry"]["className"] == "DiskManager", (
        f"Expected DiskManager as top-1, got {results[0]['entry']['className']}"
    )


def test_e2e_api_health(pipeline_output):
    _, _, client = pipeline_output
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index_built"] is True
    assert data["num_docs"] >= 4


def test_e2e_api_query_disk_io(pipeline_output):
    _, _, client = pipeline_output
    resp = client.post("/query", json={"query": "disk block read write", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"], "API /query returned empty results"
    assert data["results"][0]["className"] == "DiskManager"


def test_e2e_api_query_nvme(pipeline_output):
    _, _, client = pipeline_output
    resp = client.post("/query", json={"query": "NVMe submit IO poll", "top_k": 5})
    assert resp.status_code == 200
    results = resp.json()["results"]
    top_names = [r["className"] for r in results[:3]]
    assert "NVMeController" in top_names or "NVMeDriver" in top_names, (
        f"NVMe-related class not in top-3: {top_names}"
    )


def test_e2e_result_has_file_location(pipeline_output):
    _, _, client = pipeline_output
    resp = client.post("/query", json={"query": "disk", "top_k": 1})
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["fileLocation"], "fileLocation should not be empty"
    assert result["lineNumber"] > 0, "lineNumber should be > 0"


def test_e2e_blueprint_json_written(pipeline_output, tmp_path):
    entries, _, _ = pipeline_output
    out = tmp_path / "blueprint_index.json"
    out.write_text(json.dumps(entries, indent=2))
    loaded = json.loads(out.read_text())
    assert len(loaded) == len(entries)
    required_fields = ["className", "responsibility", "dependencies",
                       "attributes", "interfaces", "fileLocation", "lineNumber",
                       "namespace", "baseClasses", "templateParams"]
    for entry in loaded:
        for f in required_fields:
            assert f in entry, f"Missing field '{f}' in {entry.get('className')}"
