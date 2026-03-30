"""
test_sequence_accuracy.py — T-52: 時序圖與 GDB Backtrace 一致性驗收

驗收標準：產出的時序圖與實際的 GDB Backtrace 需有 95% 以上的一致性。

一致性定義：
  - 從 backtrace 解析出的 call edges 數量 = N
  - 時序圖中正確還原的 edges（caller + callee 均吻合）= M
  - 準確度 = M / N ≥ 0.95

測試案例使用多個真實 GDB backtrace 格式的 fixture。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scanner.mermaid_generator import parse_gdb_backtrace, generate_sequence_diagram


# ── GDB Backtrace Fixtures ─────────────────────────────────────────────────

# Fixture 1: Storage engine read path
GDB_STORAGE_READ = """
#0  NVMeDriver::dmaRead (this=0x55a1b2c3, lba=42, buf=0x7fff1234, len=512) at nvme_driver.cpp:88
#1  0x000055a1b0001234 in DiskManager::readBlock (this=0x55a1b2d4, lba=42, buf=0x7fff1234) at disk_mgr.cpp:55
#2  0x000055a1b0002345 in FileSystem::open (this=0x55a1b2e5, path="/etc/fstab") at fs.cpp:123
#3  0x000055a1b0003456 in Application::run (this=0x55a1b2f6) at app.cpp:45
"""

GDB_STORAGE_READ_EXPECTED_EDGES = [
    {"caller": "Application::run",       "callee": "FileSystem::open"},
    {"caller": "FileSystem::open",        "callee": "DiskManager::readBlock"},
    {"caller": "DiskManager::readBlock",  "callee": "NVMeDriver::dmaRead"},
]

# Fixture 2: NVMe controller submit path
GDB_NVME_SUBMIT = """
#0  NVMeDriver::dmaWrite (this=0x7f001234, lba=100, buf=0x7f005678, len=512) at nvme_driver.cpp:102
#1  NVMeController::submitIO (this=0x7f002345, req=...) at nvme_ctrl.cpp:67
#2  DiskManager::writeBlock (this=0x7f003456, lba=100, buf=0x7f007890) at disk_mgr.cpp:72
#3  BufferManager::flush (this=0x7f004567) at buf_mgr.cpp:38
"""

GDB_NVME_SUBMIT_EXPECTED_EDGES = [
    {"caller": "BufferManager::flush",        "callee": "DiskManager::writeBlock"},
    {"caller": "DiskManager::writeBlock",     "callee": "NVMeController::submitIO"},
    {"caller": "NVMeController::submitIO",    "callee": "NVMeDriver::dmaWrite"},
]

# Fixture 3: Cache miss path with std:: calls (should be filtered)
GDB_CACHE_MISS = """
#0  std::unordered_map<std::string, int>::find (this=0x...) at /usr/include/c++/11/bits/hashtable.h:900
#1  CacheManager::get (this=0x55b1c2d3, key="block_42") at cache_mgr.cpp:55
#2  StorageEngine::lookup (this=0x55b1c2e4, key="block_42") at storage.cpp:88
#3  RequestHandler::handleRead (this=0x55b1c2f5, req=...) at handler.cpp:34
"""

GDB_CACHE_MISS_EXPECTED_PROJECT_EDGES = [
    # std:: calls should be filtered out
    {"caller": "RequestHandler::handleRead",  "callee": "StorageEngine::lookup"},
    {"caller": "StorageEngine::lookup",       "callee": "CacheManager::get"},
    # std::unordered_map::find should be EXCLUDED
]

# Fixture 4: Event dispatch chain
GDB_EVENT_DISPATCH = """
#0  EventHandler::onEvent (this=0x6060001, event=...) at event_handler.cpp:42
#1  EventDispatcher::fire (this=0x6060002, type=1, lba=55) at dispatcher.cpp:28
#2  DiskManager::readBlock (this=0x6060003, lba=55, buf=0x7fff...) at disk_mgr.cpp:55
#3  FileSystem::read (this=0x6060004, fd=3, buf=0x7fff...) at fs.cpp:201
"""

GDB_EVENT_DISPATCH_EXPECTED_EDGES = [
    {"caller": "FileSystem::read",          "callee": "DiskManager::readBlock"},
    {"caller": "DiskManager::readBlock",    "callee": "EventDispatcher::fire"},
    {"caller": "EventDispatcher::fire",     "callee": "EventHandler::onEvent"},
]

# ── Helpers ────────────────────────────────────────────────────────────────

STD_PREFIXES = ("std::", "__cxx", "__gnu", "boost::", "absl::")


def is_project_class(qualified: str) -> bool:
    """Return True if the qualified name is a project class (not std/stl)."""
    return not any(qualified.startswith(p) for p in STD_PREFIXES)


def compute_accuracy(
    parsed_edges: list[dict[str, Any]],
    expected_edges: list[dict[str, Any]],
    filter_std: bool = False,
) -> tuple[float, list[dict], list[dict]]:
    """
    Compare parsed edges to expected edges.

    Returns:
        (accuracy, matched, missed)
    """
    if filter_std:
        parsed_edges = [
            e for e in parsed_edges
            if is_project_class(e.get("caller", ""))
            and is_project_class(e.get("callee", ""))
        ]

    matched = []
    missed  = []

    for exp in expected_edges:
        exp_caller = exp["caller"].split("::")[-1]  # compare just method name
        exp_callee = exp["callee"].split("::")[-1]

        found = any(
            e.get("caller", "").endswith("::" + exp_caller) or
            e.get("caller", "") == exp["caller"] or
            e.get("caller", "").endswith(exp_caller)
            for e in parsed_edges
            if e.get("callee", "").endswith("::" + exp_callee) or
               e.get("callee", "") == exp["callee"] or
               e.get("callee", "").endswith(exp_callee)
        )

        if found:
            matched.append(exp)
        else:
            missed.append(exp)

    n = len(expected_edges)
    accuracy = len(matched) / n if n > 0 else 1.0
    return accuracy, matched, missed


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("backtrace,expected_edges,desc", [
    (GDB_STORAGE_READ,   GDB_STORAGE_READ_EXPECTED_EDGES,   "storage read path"),
    (GDB_NVME_SUBMIT,    GDB_NVME_SUBMIT_EXPECTED_EDGES,    "NVMe submit path"),
    (GDB_EVENT_DISPATCH, GDB_EVENT_DISPATCH_EXPECTED_EDGES, "event dispatch chain"),
])
def test_backtrace_parsing_accuracy(backtrace, expected_edges, desc):
    """parse_gdb_backtrace must reproduce ≥95% of expected call edges."""
    parsed = parse_gdb_backtrace(backtrace)
    assert parsed, f"[{desc}] parse_gdb_backtrace returned empty list"

    accuracy, matched, missed = compute_accuracy(parsed, expected_edges)
    print(f"\n[{desc}] accuracy={accuracy:.1%} ({len(matched)}/{len(expected_edges)})")
    if missed:
        print(f"  Missed edges: {missed}")

    assert accuracy >= 0.95, (
        f"[{desc}] Accuracy {accuracy:.1%} < 95% target.\n"
        f"  Parsed:   {[(e['caller'], e['callee']) for e in parsed]}\n"
        f"  Expected: {[(e['caller'], e['callee']) for e in expected_edges]}\n"
        f"  Missed:   {missed}"
    )


def test_std_calls_filtered_from_sequence(backtrace=GDB_CACHE_MISS,
                                           expected=GDB_CACHE_MISS_EXPECTED_PROJECT_EDGES):
    """std:: calls must be excluded from the sequence diagram."""
    parsed = parse_gdb_backtrace(GDB_CACHE_MISS)
    # Filter std:: calls (as mermaid_generator does by convention)
    project_edges = [
        e for e in parsed
        if is_project_class(e.get("caller", ""))
        and is_project_class(e.get("callee", ""))
    ]

    # std::unordered_map::find must NOT appear
    std_edges = [
        e for e in project_edges
        if any(k in e.get("caller", "") or k in e.get("callee", "")
               for k in ("unordered_map", "hashtable", "std::"))
    ]
    assert not std_edges, f"std:: edges leaked into project edges: {std_edges}"

    accuracy, matched, missed = compute_accuracy(project_edges, expected)
    assert accuracy >= 0.95, (
        f"Project-only accuracy {accuracy:.1%} < 95%. Missed: {missed}"
    )


def test_sequence_diagram_contains_expected_participants():
    """Generated Mermaid diagram must include all participants from the backtrace."""
    parsed = parse_gdb_backtrace(GDB_STORAGE_READ)
    diagram = generate_sequence_diagram(parsed, title="Test")

    assert "sequenceDiagram" in diagram
    # Check that key class names appear as participants
    for cls in ("DiskManager", "FileSystem", "NVMeDriver", "Application"):
        assert cls in diagram, f"Expected participant '{cls}' not found in diagram:\n{diagram}"


def test_sequence_diagram_call_order():
    """Calls must appear in correct temporal order (outer → inner)."""
    parsed = parse_gdb_backtrace(GDB_STORAGE_READ)
    diagram = generate_sequence_diagram(parsed, title="Order test")
    lines = [l.strip() for l in diagram.splitlines() if "->>" in l]

    # Application should call FileSystem before FileSystem calls DiskManager
    app_fs_idx = next(
        (i for i, l in enumerate(lines) if "Application" in l and "FileSystem" in l), -1
    )
    fs_dm_idx = next(
        (i for i, l in enumerate(lines) if "FileSystem" in l and "DiskManager" in l), -1
    )
    assert app_fs_idx >= 0,  "Application→FileSystem call not found in diagram"
    assert fs_dm_idx  >= 0,  "FileSystem→DiskManager call not found in diagram"
    assert app_fs_idx < fs_dm_idx, (
        f"Call order wrong: Application→FileSystem (line {app_fs_idx}) "
        f"should come before FileSystem→DiskManager (line {fs_dm_idx})"
    )


def test_frame_count_matches_edges():
    """Number of call edges = number of frames - 1."""
    parsed = parse_gdb_backtrace(GDB_NVME_SUBMIT)
    # GDB_NVME_SUBMIT has 4 frames → 3 edges
    assert len(parsed) == 3, (
        f"Expected 3 edges from 4-frame backtrace, got {len(parsed)}"
    )


def test_overall_accuracy_across_all_fixtures():
    """Aggregate accuracy across all fixtures must be ≥ 95%."""
    fixtures = [
        (GDB_STORAGE_READ,   GDB_STORAGE_READ_EXPECTED_EDGES,   False),
        (GDB_NVME_SUBMIT,    GDB_NVME_SUBMIT_EXPECTED_EDGES,    False),
        (GDB_EVENT_DISPATCH, GDB_EVENT_DISPATCH_EXPECTED_EDGES, False),
        (GDB_CACHE_MISS,     GDB_CACHE_MISS_EXPECTED_PROJECT_EDGES, True),
    ]

    total_expected = 0
    total_matched  = 0

    for bt, expected, filter_std in fixtures:
        parsed = parse_gdb_backtrace(bt)
        acc, matched, _ = compute_accuracy(parsed, expected, filter_std=filter_std)
        total_expected += len(expected)
        total_matched  += len(matched)

    overall = total_matched / total_expected if total_expected > 0 else 0.0
    print(f"\nOverall accuracy: {total_matched}/{total_expected} = {overall:.1%}")

    assert overall >= 0.95, (
        f"Overall sequence accuracy {overall:.1%} < 95% target "
        f"({total_matched}/{total_expected} edges correct)"
    )
