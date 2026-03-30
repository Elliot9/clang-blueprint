"""
test_exclude.py — P6-06: Verify exclude path filtering in scanner.

Tests that:
- Files matching --exclude glob patterns are not parsed
- Simple directory name patterns work (e.g. "build")
- Glob wildcards work ("third_party/**", "src/gen/*.cpp")
- .blueprintignore is automatically read and merged
- incremental_scan respects exclude patterns and evicts matching cache entries
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.ast_parser import _is_excluded, load_blueprintignore, scan_directory
from scanner.incremental import incremental_scan


# ---------------------------------------------------------------------------
# _is_excluded unit tests
# ---------------------------------------------------------------------------

def test_simple_name_excludes_directory(tmp_path):
    """Simple name 'build' matches any path component named 'build'."""
    f = str(tmp_path / "build" / "src" / "foo.cpp")
    assert _is_excluded(f, str(tmp_path), ["build"])


def test_glob_double_star(tmp_path):
    """'third_party/**' matches files anywhere under third_party/."""
    f = str(tmp_path / "third_party" / "lib" / "deep" / "bar.h")
    assert _is_excluded(f, str(tmp_path), ["third_party/**"])


def test_glob_single_star(tmp_path):
    """'src/gen/*.cpp' matches only .cpp in src/gen/, not subdirs."""
    (tmp_path / "src" / "gen").mkdir(parents=True)
    f = str(tmp_path / "src" / "gen" / "proto.cpp")
    assert _is_excluded(f, str(tmp_path), ["src/gen/*.cpp"])
    # .h file should NOT be excluded
    h = str(tmp_path / "src" / "gen" / "proto.h")
    assert not _is_excluded(h, str(tmp_path), ["src/gen/*.cpp"])


def test_not_excluded_when_no_match(tmp_path):
    """File not matching any pattern is not excluded."""
    f = str(tmp_path / "src" / "core" / "manager.cpp")
    assert not _is_excluded(f, str(tmp_path), ["third_party/**", "build"])


def test_empty_patterns_never_exclude(tmp_path):
    """Empty pattern list never excludes anything."""
    f = str(tmp_path / "anything" / "file.cpp")
    assert not _is_excluded(f, str(tmp_path), [])


# ---------------------------------------------------------------------------
# .blueprintignore loading
# ---------------------------------------------------------------------------

def test_load_blueprintignore(tmp_path):
    ignore = tmp_path / ".blueprintignore"
    ignore.write_text("# comment\nbuild/**\n\nthird_party\n")
    patterns = load_blueprintignore(str(tmp_path))
    assert "build/**" in patterns
    assert "third_party" in patterns
    assert "" not in patterns          # blank lines stripped
    assert "# comment" not in patterns # comments stripped


def test_load_blueprintignore_missing(tmp_path):
    """No .blueprintignore → empty list, no error."""
    assert load_blueprintignore(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# scan_directory integration
# ---------------------------------------------------------------------------

# Minimal valid C++ snippet for scan_directory to process
_CPP_CLASS = """\
class Foo {
public:
    void doSomething();
};
"""

def _write_cpp(path: Path, content: str = _CPP_CLASS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.mark.skipif(
    "clang" not in sys.modules and not _try_import_clang(),
    reason="libclang not available"
)
def test_scan_directory_excludes_pattern(tmp_path):
    """Files under excluded directory do not appear in output."""
    _write_cpp(tmp_path / "src" / "core.cpp")
    _write_cpp(tmp_path / "third_party" / "lib" / "extern.cpp")

    entries = scan_directory(
        str(tmp_path),
        exclude_patterns=["third_party/**"],
    )
    class_names = {e["className"] for e in entries}
    # Foo from core.cpp may or may not appear (depends on libclang parse),
    # but nothing from third_party should be present.
    # We verify by checking fileLocation fields.
    locs = [e["fileLocation"] for e in entries]
    assert not any("third_party" in loc for loc in locs), (
        f"third_party entry slipped through: {locs}"
    )


@pytest.mark.skipif(
    "clang" not in sys.modules and not _try_import_clang(),
    reason="libclang not available"
)
def test_scan_directory_reads_blueprintignore(tmp_path):
    """scan_directory auto-merges .blueprintignore patterns."""
    _write_cpp(tmp_path / "generated" / "proto.cpp")
    _write_cpp(tmp_path / "src" / "real.cpp")
    (tmp_path / ".blueprintignore").write_text("generated/**\n")

    entries = scan_directory(str(tmp_path), exclude_patterns=[])
    locs = [e["fileLocation"] for e in entries]
    assert not any("generated" in loc for loc in locs)


# ---------------------------------------------------------------------------
# Incremental scan integration
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    "clang" not in sys.modules and not _try_import_clang(),
    reason="libclang not available"
)
def test_incremental_scan_excludes_pattern(tmp_path):
    """incremental_scan respects exclude_patterns."""
    _write_cpp(tmp_path / "src" / "good.cpp")
    _write_cpp(tmp_path / "build" / "bad.cpp")

    entries = incremental_scan(
        str(tmp_path),
        cache_path=str(tmp_path / ".cache.json"),
        exclude_patterns=["build"],
    )
    locs = [e["fileLocation"] for e in entries]
    assert not any("build" in loc for loc in locs)


@pytest.mark.skipif(
    "clang" not in sys.modules and not _try_import_clang(),
    reason="libclang not available"
)
def test_incremental_scan_evicts_newly_excluded(tmp_path):
    """
    P6-03: If a file was cached but now matches an exclude pattern,
    it should be evicted from the cache on the next incremental run.
    """
    src = tmp_path / "vendor" / "lib.cpp"
    _write_cpp(src)
    cache_path = str(tmp_path / ".cache.json")

    # First scan: no excludes, vendor/lib.cpp gets cached
    incremental_scan(str(tmp_path), cache_path=cache_path, exclude_patterns=[])

    # Check it was cached
    import json as _json
    with open(cache_path) as f:
        cache = _json.load(f)
    assert any("lib.cpp" in fp for fp in cache.get("files", {}))

    # Second scan: now exclude vendor/**
    entries = incremental_scan(
        str(tmp_path),
        cache_path=cache_path,
        exclude_patterns=["vendor/**"],
    )
    # Entry should not appear in output
    locs = [e["fileLocation"] for e in entries]
    assert not any("vendor" in loc for loc in locs)

    # Cache entry should have been evicted
    with open(cache_path) as f:
        cache2 = _json.load(f)
    vendor_keys = [fp for fp in cache2.get("files", {}) if "vendor" in fp]
    assert vendor_keys == [], f"Cache still has vendor entries: {vendor_keys}"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _try_import_clang() -> bool:
    try:
        import clang.cindex  # noqa: F401
        return True
    except ImportError:
        return False
