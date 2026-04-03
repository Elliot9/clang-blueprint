"""
tests/test_module_grouper.py — Tests for scanner/module_grouper.py and scanner/entry_detector.py.
"""

from __future__ import annotations

import pytest

from scanner.module_grouper import (
    group_into_modules,
    compute_module_edges,
    generate_summary_seeds,
    build_modules,
)
from scanner.entry_detector import detect_entry_points


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _entry(
    name: str,
    ns: str = "",
    file_loc: str = "",
    deps: list[dict] | None = None,
    responsibility: str = "",
    interfaces: list[str] | None = None,
) -> dict:
    """Shorthand to build a ClassEntry dict."""
    return {
        "className": name,
        "namespace": ns,
        "fileLocation": file_loc,
        "lineNumber": 1,
        "dependencies": deps or [],
        "responsibility": responsibility,
        "baseClasses": [],
        "templateParams": [],
        "interfaces": interfaces or [],
        "attributes": [],
    }


@pytest.fixture
def sample_entries():
    """A small set of classes spanning 3 namespaces + 1 directory-only group."""
    return [
        _entry("DiskManager", ns="core", file_loc="core/disk_mgr.cpp",
               deps=[{"target": "NVMeDriver", "type": "composition"},
                     {"target": "BufferPool", "type": "composition"}],
               responsibility="Resource Lifecycle"),
        _entry("BufferPool", ns="core", file_loc="core/buffer_pool.h",
               deps=[{"target": "PageCache", "type": "composition"}],
               responsibility="Memory Management"),
        _entry("NVMeDriver", ns="io", file_loc="io/nvme_driver.h",
               deps=[],
               responsibility="Device I/O"),
        _entry("SocketPool", ns="io", file_loc="io/socket_pool.h",
               deps=[{"target": "NVMeDriver", "type": "association"}],
               responsibility="Network I/O"),
        _entry("PageCache", ns="core", file_loc="core/page_cache.h",
               deps=[],
               responsibility="Memory Management"),
        _entry("Logger", ns="", file_loc="util/logger.h",
               deps=[],
               responsibility="Logging"),
        _entry("ConfigParser", ns="", file_loc="util/config.h",
               deps=[{"target": "Logger", "type": "dependency"}],
               responsibility="Configuration"),
        # Third-party — should be skipped by default
        _entry("basic_string", ns="std", file_loc="",
               deps=[], responsibility=""),
        _entry("json", ns="nlohmann::json_abi_v3_11_2", file_loc="3rd_party/json/json.hpp",
               deps=[], responsibility=""),
    ]


@pytest.fixture
def reverse_deps():
    return {
        "NVMeDriver": ["DiskManager", "SocketPool"],
        "BufferPool": ["DiskManager"],
        "PageCache": ["BufferPool"],
        "Logger": ["ConfigParser"],
    }


# ---------------------------------------------------------------------------
# group_into_modules
# ---------------------------------------------------------------------------

class TestGroupIntoModules:

    def test_namespace_based_grouping(self, sample_entries):
        modules = group_into_modules(sample_entries)
        names = {m["name"] for m in modules}
        assert "core" in names
        assert "io" in names

    def test_directory_based_fallback(self, sample_entries):
        modules = group_into_modules(sample_entries)
        names = {m["name"] for m in modules}
        # Logger and ConfigParser have no namespace but are in util/
        assert "util" in names

    def test_thirdparty_excluded_by_default(self, sample_entries):
        modules = group_into_modules(sample_entries)
        names = {m["name"] for m in modules}
        assert "std" not in names
        assert "nlohmann" not in names
        assert "_thirdparty" not in names

    def test_thirdparty_included_when_requested(self, sample_entries):
        modules = group_into_modules(sample_entries, include_thirdparty=True)
        names = {m["name"] for m in modules}
        assert "_thirdparty" in names

    def test_class_names_correct(self, sample_entries):
        modules = group_into_modules(sample_entries)
        core_mod = next(m for m in modules if m["name"] == "core")
        assert set(core_mod["classNames"]) == {"DiskManager", "BufferPool", "PageCache"}

    def test_internal_edge_count(self, sample_entries):
        modules = group_into_modules(sample_entries)
        core_mod = next(m for m in modules if m["name"] == "core")
        # DiskManager → BufferPool (internal), DiskManager → NVMeDriver (external)
        # BufferPool → PageCache (internal)
        assert core_mod["internalEdgeCount"] == 2

    def test_no_empty_modules(self, sample_entries):
        modules = group_into_modules(sample_entries)
        for m in modules:
            assert len(m["classNames"]) > 0


# ---------------------------------------------------------------------------
# compute_module_edges
# ---------------------------------------------------------------------------

class TestComputeModuleEdges:

    def test_cross_module_edges(self, sample_entries):
        modules = group_into_modules(sample_entries)
        edges = compute_module_edges(sample_entries, modules)
        # core → io (DiskManager depends on NVMeDriver)
        core_to_io = [e for e in edges if e["source"] == "core" and e["target"] == "io"]
        assert len(core_to_io) == 1
        assert core_to_io[0]["weight"] == 1

    def test_internal_edges_not_counted(self, sample_entries):
        modules = group_into_modules(sample_entries)
        edges = compute_module_edges(sample_entries, modules)
        # No edge from core to core
        self_edges = [e for e in edges if e["source"] == e["target"]]
        assert len(self_edges) == 0

    def test_external_deps_populated(self, sample_entries):
        modules = group_into_modules(sample_entries)
        compute_module_edges(sample_entries, modules)
        core_mod = next(m for m in modules if m["name"] == "core")
        ext_targets = {d["target"] for d in core_mod["externalDeps"]}
        assert "io" in ext_targets

    def test_dep_types_tracked(self, sample_entries):
        modules = group_into_modules(sample_entries)
        edges = compute_module_edges(sample_entries, modules)
        core_to_io = next(e for e in edges if e["source"] == "core" and e["target"] == "io")
        assert "composition" in core_to_io["depTypes"]


# ---------------------------------------------------------------------------
# generate_summary_seeds
# ---------------------------------------------------------------------------

class TestGenerateSummarySeeds:

    def test_seeds_not_empty(self, sample_entries, reverse_deps):
        modules = group_into_modules(sample_entries)
        compute_module_edges(sample_entries, modules)
        generate_summary_seeds(modules, sample_entries, reverse_deps=reverse_deps)
        for m in modules:
            assert m["summarySeed"], f"Empty seed for module {m['name']}"

    def test_seed_mentions_class_count(self, sample_entries, reverse_deps):
        modules = group_into_modules(sample_entries)
        generate_summary_seeds(modules, sample_entries, reverse_deps=reverse_deps)
        core_mod = next(m for m in modules if m["name"] == "core")
        assert "3 classes" in core_mod["summarySeed"]

    def test_seed_mentions_hub(self, sample_entries, reverse_deps):
        modules = group_into_modules(sample_entries)
        generate_summary_seeds(modules, sample_entries, reverse_deps=reverse_deps)
        # NVMeDriver has 2 dependents and is in module "io"
        io_mod = next(m for m in modules if m["name"] == "io")
        assert "NVMeDriver" in io_mod["summarySeed"]


# ---------------------------------------------------------------------------
# detect_entry_points
# ---------------------------------------------------------------------------

class TestDetectEntryPoints:

    def test_main_detection(self):
        entries = [
            _entry("main_entry", interfaces=["int main(int argc, char * argv[])"]),
            _entry("Helper"),
        ]
        eps = detect_entry_points(entries)
        main_eps = [ep for ep in eps if ep["kind"] == "main"]
        assert len(main_eps) == 1
        assert main_eps[0]["className"] == "main_entry"

    def test_server_name_pattern(self):
        entries = [
            _entry("GraidServer"),
            _entry("AppController"),
            _entry("Helper"),
        ]
        eps = detect_entry_points(entries)
        server_eps = [ep for ep in eps if ep["kind"] == "server"]
        names = {ep["className"] for ep in server_eps}
        assert "GraidServer" in names
        assert "AppController" in names
        assert "Helper" not in names

    def test_root_detection(self):
        entries = [
            _entry("TopLevel", deps=[
                {"target": "Inner", "type": "composition"},
                {"target": "Helper", "type": "association"},
            ]),
            _entry("Inner"),
            _entry("Helper"),
        ]
        # TopLevel has out-degree 2, in-degree 0 → root
        eps = detect_entry_points(entries, reverse_deps={"Inner": ["TopLevel"], "Helper": ["TopLevel"]})
        root_eps = [ep for ep in eps if ep["kind"] == "root"]
        assert any(ep["className"] == "TopLevel" for ep in root_eps)

    def test_hub_detection(self):
        entries = [_entry("SharedLib"), _entry("A"), _entry("B"), _entry("C")]
        rdeps = {"SharedLib": ["A", "B", "C"]}
        eps = detect_entry_points(entries, reverse_deps=rdeps, hub_top_n=3)
        hub_eps = [ep for ep in eps if ep["kind"] == "hub"]
        assert any(ep["className"] == "SharedLib" for ep in hub_eps)

    def test_no_duplicate_kinds(self):
        entries = [
            _entry("MainServer", interfaces=["int main(int argc, char * argv[])"]),
        ]
        eps = detect_entry_points(entries)
        # Should appear as 'main', not duplicated as 'server'
        assert sum(1 for ep in eps if ep["className"] == "MainServer") == 1


# ---------------------------------------------------------------------------
# build_modules (integration)
# ---------------------------------------------------------------------------

class TestBuildModules:

    def test_full_pipeline(self, sample_entries, reverse_deps):
        modules, edges = build_modules(
            sample_entries, reverse_deps=reverse_deps
        )
        assert len(modules) >= 3  # core, io, util
        assert len(edges) >= 1  # at least core → io
        for m in modules:
            assert m["summarySeed"]  # all have seeds
            assert m["classNames"]   # all non-empty

    def test_full_pipeline_with_entry_points(self, sample_entries, reverse_deps):
        eps = detect_entry_points(sample_entries, reverse_deps=reverse_deps)
        modules, edges = build_modules(
            sample_entries, entry_points=eps, reverse_deps=reverse_deps
        )
        # Should still produce valid modules
        assert len(modules) >= 3
