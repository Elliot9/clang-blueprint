"""
bench_scan_performance.py — T-23: 效能驗收

在 10 萬行合成 C++ 程式碼下執行全量掃描，確認 ≤ 60 秒。
也驗證增量掃描（無變更）≤ 5 秒。

執行方式:
    pytest tests/bench_scan_performance.py -v -s
或直接執行:
    python tests/bench_scan_performance.py
"""

from __future__ import annotations

import sys
import time
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from scanner.ast_parser import parse_files
    from scanner.incremental import incremental_scan, _sha256_file
except ImportError as e:
    pytest.skip(f"scanner not available: {e}", allow_module_level=True)


# ── Synthetic project generator ───────────────────────────────────────────

CLASS_TEMPLATE = """\
// {filename} — auto-generated synthetic class

#include <memory>
#include <vector>
#include <string>

namespace synth {{

class Base{idx} {{
public:
    virtual void run() = 0;
    virtual ~Base{idx}() = default;
}};

/// {class_name}: synthetic class {idx} for performance benchmarking.
class {class_name} : public Base{idx} {{
    std::unique_ptr<Base{idx}>  child_;
    std::vector<int>            data_;
    std::string                 name_;
    int                         count_ = 0;

public:
    explicit {class_name}(std::string name);
    ~{class_name}() override = default;

    void run()      override;
    void process(int value);
    void reset();
    int  getCount() const {{ return count_; }}
    const std::string& getName() const {{ return name_; }}
    void setName(const std::string& n) {{ name_ = n; }}
    void addData(int v) {{ data_.push_back(v); }}
    void clearData() {{ data_.clear(); }}
    size_t dataSize() const {{ return data_.size(); }}
}};

}} // namespace synth
"""

# Each class = ~30 lines. For 100k lines: 100000/30 ≈ 3334 classes
LINES_PER_CLASS  = 30
TARGET_LOC       = 100_000
NUM_CLASSES      = TARGET_LOC // LINES_PER_CLASS   # 3333


@pytest.fixture(scope="module")
def synthetic_project(tmp_path_factory):
    """Generate a synthetic C++ project with ~100k LOC."""
    tmp = tmp_path_factory.mktemp("perf_bench")
    src = tmp / "src"
    src.mkdir()

    files = []
    for i in range(NUM_CLASSES):
        class_name = f"SynthClass{i:04d}"
        filename   = f"class_{i:04d}.h"
        content    = CLASS_TEMPLATE.format(
            idx=i,
            class_name=class_name,
            filename=filename,
        )
        p = src / filename
        p.write_text(content)
        files.append(str(p))

    # Count actual lines
    total_lines = sum(
        len(Path(f).read_text().splitlines()) for f in files
    )
    print(f"\n[bench] Generated {len(files)} files, {total_lines:,} lines of C++")
    return tmp, files, total_lines


# ── T-23: Full scan ≤ 60s ─────────────────────────────────────────────────

@pytest.mark.slow
def test_full_scan_within_60s(synthetic_project):
    """Full scan of ~100k LOC must complete within 60 seconds."""
    tmp, files, total_lines = synthetic_project
    print(f"\n[bench] Starting full scan of {total_lines:,} lines across {len(files)} files...")

    t0 = time.perf_counter()
    entries = parse_files(
        files,
        project_root=str(tmp),
        extra_args=["-std=c++14", "-x", "c++"],
    )
    elapsed = time.perf_counter() - t0

    print(f"[bench] Full scan: {elapsed:.2f}s → {len(entries)} entries")
    print(f"[bench] Throughput: {total_lines / elapsed:,.0f} LOC/s")

    assert elapsed <= 60.0, (
        f"Full scan took {elapsed:.1f}s — exceeds 60s target. "
        f"Consider adding -j parallelism or reducing AST depth."
    )
    assert len(entries) > 0, "No entries parsed"


# ── T-23: Incremental scan ≤ 5s (no changes) ─────────────────────────────

@pytest.mark.slow
def test_incremental_no_change_within_5s(synthetic_project):
    """Incremental scan with zero file changes must complete within 5 seconds."""
    tmp, files, total_lines = synthetic_project

    # Pre-warm the cache with a full incremental scan
    print(f"\n[bench] Pre-warming incremental cache ...")
    t_warm = time.perf_counter()
    incremental_scan(project_root=str(tmp))
    warm_elapsed = time.perf_counter() - t_warm
    print(f"[bench] Cache warm-up: {warm_elapsed:.2f}s")

    # Second run — nothing changed, should only hash files + read cache
    print("[bench] Running incremental scan (no changes) ...")
    t0 = time.perf_counter()
    entries = incremental_scan(project_root=str(tmp))
    elapsed = time.perf_counter() - t0

    print(f"[bench] Incremental (no change): {elapsed:.3f}s → {len(entries)} entries")

    assert elapsed <= 5.0, (
        f"Incremental scan took {elapsed:.2f}s — exceeds 5s target. "
        f"Check SHA256 hashing loop or cache I/O."
    )


@pytest.mark.slow
def test_incremental_single_change_fast(synthetic_project):
    """Incremental scan with ONE changed file should re-parse only that file."""
    tmp, files, _ = synthetic_project

    # Warm cache
    incremental_scan(project_root=str(tmp))

    # Modify one file
    changed = Path(files[0])
    original = changed.read_text()
    changed.write_text(original + "\n// benchmark modification\n")

    reparsed = []

    def counting_parse(source_files, **kwargs):
        reparsed.extend(source_files)
        return []

    with patch("scanner.incremental.parse_files", side_effect=counting_parse):
        incremental_scan(project_root=str(tmp))

    # Restore
    changed.write_text(original)

    assert len(reparsed) == 1, (
        f"Expected exactly 1 file re-parsed, got {len(reparsed)}: {reparsed}"
    )


# ── Standalone runner ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import os

    print("Generating synthetic project ...")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        files = []
        for i in range(NUM_CLASSES):
            class_name = f"SynthClass{i:04d}"
            p = src / f"class_{i:04d}.h"
            p.write_text(CLASS_TEMPLATE.format(
                idx=i, class_name=class_name, filename=p.name
            ))
            files.append(str(p))

        total = sum(len(Path(f).read_text().splitlines()) for f in files)
        print(f"Generated {len(files)} files, {total:,} lines")

        print("Running full scan ...")
        t0 = time.perf_counter()
        entries = parse_files(files, project_root=tmp,
                              extra_args=["-std=c++14", "-x", "c++"])
        elapsed = time.perf_counter() - t0

        status = "✓ PASS" if elapsed <= 60 else "✗ FAIL"
        print(f"\n{status}  Full scan: {elapsed:.2f}s ({total/elapsed:,.0f} LOC/s)")
        print(f"       Entries: {len(entries)}")
        sys.exit(0 if elapsed <= 60 else 1)
