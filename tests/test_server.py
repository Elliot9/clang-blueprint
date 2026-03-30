"""
test_server.py — Integration tests for ai_api/server.py (T-47)

Uses httpx + pytest-asyncio to test all endpoints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
    from fastapi.testclient import TestClient
    from ai_api.server import app, state
    from ai_api.indexer import BlueprintIndexer
except ImportError as e:
    pytest.skip(f"FastAPI/httpx not available: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ENTRIES = [
    {
        "className": "DiskManager",
        "responsibility": "Resource Lifecycle",
        "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
        "interfaces": ["void readBlock(int lba, char * buf)"],
        "fileLocation": "src/core/disk_mgr.cpp",
        "lineNumber": 10,
        "namespace": "core",
        "baseClasses": [],
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
]


@pytest.fixture
def client_with_index(tmp_path):
    """TestClient with a pre-built in-memory index."""
    indexer = BlueprintIndexer(
        blueprint_path=str(tmp_path / "dummy.json"),
        index_path=str(tmp_path / ".tfidf.pkl"),
    )
    indexer.build(SAMPLE_ENTRIES)
    with TestClient(app, raise_server_exceptions=True) as client:
        # Override AFTER lifespan startup (lifespan resets state.indexer)
        import ai_api.server as _srv
        _srv.state.indexer = indexer
        _srv.state.rebuild_in_progress = False
        yield client


@pytest.fixture
def client_no_index():
    """TestClient with no index built (simulates cold start)."""
    with TestClient(app, raise_server_exceptions=False) as client:
        # Override after lifespan so a pre-existing .pkl on disk doesn't load
        import ai_api.server as _srv
        _srv.state.indexer = None
        _srv.state.rebuild_in_progress = False
        yield client


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_ok(client_with_index):
    resp = client_with_index.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["index_built"] is True
    assert data["num_docs"] == len(SAMPLE_ENTRIES)


def test_health_no_index(client_no_index):
    resp = client_no_index.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index_built"] is False
    assert data["num_docs"] == 0


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

def test_stats_returns_info(client_with_index):
    resp = client_with_index.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "num_docs" in data
    assert "index_built" in data
    assert data["index_built"] is True


# ---------------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------------

def test_query_returns_results(client_with_index):
    resp = client_with_index.post("/query", json={"query": "disk I/O read write", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0
    assert "elapsed_ms" in data
    assert "total_indexed" in data


def test_query_top1_disk_io(client_with_index):
    resp = client_with_index.post("/query", json={"query": "disk block read write", "top_k": 5})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results, "No results returned"
    assert results[0]["className"] == "DiskManager"


def test_query_result_fields(client_with_index):
    resp = client_with_index.post("/query", json={"query": "disk", "top_k": 1})
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    for field in ("score", "className", "responsibility", "fileLocation",
                  "lineNumber", "namespace", "attributes", "interfaces"):
        assert field in result, f"Missing field: {field}"


def test_query_respects_top_k(client_with_index):
    resp = client_with_index.post("/query", json={"query": "manager", "top_k": 1})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 1


def test_query_blank_returns_422(client_with_index):
    resp = client_with_index.post("/query", json={"query": "   ", "top_k": 5})
    assert resp.status_code == 422


def test_query_empty_string_returns_422(client_with_index):
    resp = client_with_index.post("/query", json={"query": "", "top_k": 5})
    assert resp.status_code == 422


def test_query_top_k_too_large_returns_422(client_with_index):
    resp = client_with_index.post("/query", json={"query": "disk", "top_k": 9999})
    assert resp.status_code == 422


def test_query_no_index_returns_503(client_no_index):
    resp = client_no_index.post("/query", json={"query": "disk", "top_k": 5})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /rebuild-index
# ---------------------------------------------------------------------------

def test_rebuild_index_success(tmp_path):
    """Rebuild from a real blueprint_index.json file."""
    index_file = tmp_path / "blueprint_index.json"
    index_file.write_text(json.dumps(SAMPLE_ENTRIES))

    import os
    os.environ["BLUEPRINT_INDEX_PATH"] = str(index_file)
    os.environ["TFIDF_INDEX_PATH"] = str(tmp_path / ".tfidf.pkl")

    # Reload server module to pick up new env vars
    import importlib
    import ai_api.server as server_mod
    importlib.reload(server_mod)

    from ai_api.server import app as reloaded_app
    reloaded_app.state = server_mod.state  # type: ignore
    server_mod.state.indexer = BlueprintIndexer(
        blueprint_path=str(index_file),
        index_path=str(tmp_path / ".tfidf.pkl"),
    )
    server_mod.state.rebuild_in_progress = False

    with TestClient(reloaded_app) as client:
        resp = client.post("/rebuild-index")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["num_entries"] == len(SAMPLE_ENTRIES)
    assert "elapsed_ms" in data


def test_rebuild_index_missing_file(tmp_path):
    """Should return 404 when blueprint_index.json does not exist."""
    import os
    os.environ["BLUEPRINT_INDEX_PATH"] = str(tmp_path / "nonexistent.json")

    import importlib
    import ai_api.server as server_mod
    importlib.reload(server_mod)
    server_mod.state.rebuild_in_progress = False

    with TestClient(server_mod.app, raise_server_exceptions=False) as client:
        resp = client.post("/rebuild-index")
    assert resp.status_code == 404


def test_rebuild_conflict_when_in_progress(client_with_index):
    """Should return 409 if a rebuild is already running."""
    import ai_api.server as _srv
    _srv.state.rebuild_in_progress = True
    try:
        resp = client_with_index.post("/rebuild-index")
        assert resp.status_code == 409
    finally:
        _srv.state.rebuild_in_progress = False
