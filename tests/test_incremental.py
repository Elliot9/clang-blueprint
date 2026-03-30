"""
test_incremental.py — Tests for scanner/incremental.py (T-18)

Validates that:
  1. Unchanged files are NOT re-parsed (parse_files not called for them)
  2. Changed files ARE re-parsed
  3. Deleted files are evicted from cache
  4. Cache is written atomically
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.incremental import (
    _sha256_file,
    incremental_scan,
    load_cache,
    save_cache,
    get_cache_stats,
    invalidate_cache,
    CACHE_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ENTRY = {
    "className": "DiskManager",
    "responsibility": "Resource Lifecycle",
    "dependencies": [{"target": "NVMeDriver", "type": "composition"}],
    "interfaces": ["void readBlock(int lba, char * buf)"],
    "fileLocation": "src/disk_mgr.cpp",
    "lineNumber": 10,
    "namespace": "",
    "baseClasses": [],
    "templateParams": [],
}

CPP_CONTENT_V1 = b"class Foo { public: void bar(); };\n"
CPP_CONTENT_V2 = b"class Foo { public: void baz(); };\n"  # changed


@pytest.fixture
def project(tmp_path):
    """Create a minimal project directory with one .cpp file."""
    src = tmp_path / "src"
    src.mkdir()
    cpp_file = src / "foo.cpp"
    cpp_file.write_bytes(CPP_CONTENT_V1)
    return tmp_path, cpp_file


# ---------------------------------------------------------------------------
# Unit tests: cache I/O
# ---------------------------------------------------------------------------

def test_sha256_file_deterministic(tmp_path):
    f = tmp_path / "a.cpp"
    f.write_bytes(CPP_CONTENT_V1)
    h1 = _sha256_file(str(f))
    h2 = _sha256_file(str(f))
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex digest length


def test_sha256_changes_on_content_change(tmp_path):
    f = tmp_path / "a.cpp"
    f.write_bytes(CPP_CONTENT_V1)
    h1 = _sha256_file(str(f))
    f.write_bytes(CPP_CONTENT_V2)
    h2 = _sha256_file(str(f))
    assert h1 != h2


def test_load_cache_missing_file(tmp_path):
    cache = load_cache(str(tmp_path / ".blueprint_cache.json"))
    assert cache["version"] == CACHE_VERSION
    assert cache["files"] == {}


def test_save_and_load_cache(tmp_path):
    cache_path = str(tmp_path / ".blueprint_cache.json")
    data = {
        "version": CACHE_VERSION,
        "files": {
            "/fake/path.cpp": {
                "hash": "abc123",
                "last_scanned": time.time(),
                "entries": [SAMPLE_ENTRY],
            }
        },
    }
    save_cache(cache_path, data)
    loaded = load_cache(cache_path)
    assert loaded["version"] == CACHE_VERSION
    assert "/fake/path.cpp" in loaded["files"]
    assert loaded["files"]["/fake/path.cpp"]["hash"] == "abc123"


def test_load_cache_corrupt_json(tmp_path):
    cache_path = tmp_path / ".blueprint_cache.json"
    cache_path.write_text("NOT VALID JSON")
    result = load_cache(str(cache_path))
    assert result["files"] == {}


def test_load_cache_version_mismatch(tmp_path):
    cache_path = tmp_path / ".blueprint_cache.json"
    cache_path.write_text(json.dumps({"version": 999, "files": {"x": {}}}))
    result = load_cache(str(cache_path))
    assert result["files"] == {}  # discarded due to version mismatch


def test_atomic_write_no_partial_file(tmp_path):
    """Cache must not leave a .tmp file behind on success."""
    cache_path = str(tmp_path / ".blueprint_cache.json")
    data = {"version": CACHE_VERSION, "files": {}}
    save_cache(cache_path, data)
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Temp files left behind: {tmp_files}"


# ---------------------------------------------------------------------------
# T-18: unchanged files must NOT be re-parsed
# ---------------------------------------------------------------------------

def test_unchanged_files_not_reparsed(project):
    """If a file's hash matches the cache, parse_files must not be called for it."""
    tmp_path, cpp_file = project
    cpp_abs = str(cpp_file.resolve())

    # Pre-populate cache with the current hash
    current_hash = _sha256_file(cpp_abs)
    cache_path = str(tmp_path / ".blueprint_cache.json")
    save_cache(cache_path, {
        "version": CACHE_VERSION,
        "files": {
            cpp_abs: {
                "hash": current_hash,
                "last_scanned": time.time(),
                "entries": [SAMPLE_ENTRY],
            }
        },
    })

    call_count = {"n": 0}
    original_parse = None

    def mock_parse_files(source_files, **kwargs):
        call_count["n"] += len(source_files)
        return []

    with patch("scanner.incremental.parse_files", side_effect=mock_parse_files):
        result = incremental_scan(
            project_root=str(tmp_path),
            cache_path=cache_path,
        )

    assert call_count["n"] == 0, (
        f"parse_files was called for {call_count['n']} file(s) "
        "even though nothing changed."
    )
    # The cached entry should be returned
    assert any(e["className"] == "DiskManager" for e in result)


def test_changed_file_is_reparsed(project):
    """After a file is modified, it must be included in parse_files call."""
    tmp_path, cpp_file = project
    cpp_abs = str(cpp_file.resolve())

    # Cache with an OLD hash
    cache_path = str(tmp_path / ".blueprint_cache.json")
    save_cache(cache_path, {
        "version": CACHE_VERSION,
        "files": {
            cpp_abs: {
                "hash": "0" * 64,  # wrong hash → will trigger re-parse
                "last_scanned": time.time() - 3600,
                "entries": [SAMPLE_ENTRY],
            }
        },
    })

    reparsed_files = []

    def mock_parse_files(source_files, **kwargs):
        reparsed_files.extend(source_files)
        return []

    with patch("scanner.incremental.parse_files", side_effect=mock_parse_files):
        incremental_scan(
            project_root=str(tmp_path),
            cache_path=cache_path,
        )

    assert cpp_abs in reparsed_files, (
        f"{cpp_abs} was not re-parsed after hash change.\n"
        f"Re-parsed: {reparsed_files}"
    )


def test_deleted_file_evicted_from_cache(tmp_path):
    """Files removed from disk must be evicted from the cache."""
    ghost_path = str((tmp_path / "ghost.cpp").resolve())

    cache_path = str(tmp_path / ".blueprint_cache.json")
    save_cache(cache_path, {
        "version": CACHE_VERSION,
        "files": {
            ghost_path: {
                "hash": "abc",
                "last_scanned": time.time(),
                "entries": [SAMPLE_ENTRY],
            }
        },
    })

    with patch("scanner.incremental.parse_files", return_value=[]):
        incremental_scan(project_root=str(tmp_path), cache_path=cache_path)

    updated_cache = load_cache(cache_path)
    assert ghost_path not in updated_cache["files"], (
        f"Ghost entry {ghost_path} was not evicted from cache."
    )


# ---------------------------------------------------------------------------
# get_cache_stats / invalidate_cache
# ---------------------------------------------------------------------------

def test_get_cache_stats(tmp_path):
    cache_path = str(tmp_path / ".blueprint_cache.json")
    save_cache(cache_path, {
        "version": CACHE_VERSION,
        "files": {
            "/a.cpp": {"hash": "x", "last_scanned": 0, "entries": [SAMPLE_ENTRY, SAMPLE_ENTRY]},
        },
    })
    stats = get_cache_stats(cache_path)
    assert stats["cached_files"] == 1
    assert stats["total_entries"] == 2
    assert stats["version"] == CACHE_VERSION


def test_invalidate_cache(tmp_path):
    cache_path = tmp_path / ".blueprint_cache.json"
    cache_path.write_text(json.dumps({"version": CACHE_VERSION, "files": {}}))
    assert cache_path.exists()
    invalidate_cache(str(cache_path))
    assert not cache_path.exists()
