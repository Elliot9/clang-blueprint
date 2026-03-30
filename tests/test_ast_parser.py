"""
test_ast_parser.py — Integration tests for scanner/ast_parser.py

Writes real C++ source to temp files and validates parsed output.
Requires libclang to be installed: pip install libclang
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import pytest

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scanner.ast_parser import _is_definition_in_project, parse_files
except ImportError as e:
    pytest.skip(f"libclang not available: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_cpp(tmp_path):
    """Helper: writes C++ code to a temp file and returns its path."""
    def _write(code: str, filename: str = "test.cpp") -> str:
        p = tmp_path / filename
        p.write_text(textwrap.dedent(code))
        return str(p)
    return _write


def find_entry(entries: list[dict], class_name: str) -> dict[str, Any]:
    for e in entries:
        if e["className"] == class_name:
            return e
    raise AssertionError(
        f"Class '{class_name}' not found in parsed entries.\n"
        f"Found: {[e['className'] for e in entries]}"
    )


def find_dep(entry: dict, target: str) -> dict[str, Any]:
    for d in entry["dependencies"]:
        if d["target"] == target:
            return d
    raise AssertionError(
        f"Dependency '{target}' not found in {entry['className']}.\n"
        f"Found: {[d['target'] for d in entry['dependencies']]}"
    )


# ---------------------------------------------------------------------------
# T-06: class / struct identification
# ---------------------------------------------------------------------------

def test_class_and_struct_identified(tmp_cpp):
    """Both class and struct keywords should be parsed."""
    path = tmp_cpp("""
        class MyClass { public: void foo(); };
        struct MyStruct { int x; };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    names = [e["className"] for e in entries]
    assert "MyClass" in names
    assert "MyStruct" in names


def test_forward_declaration_skipped(tmp_cpp):
    """Forward declarations without a body must not appear in the index."""
    path = tmp_cpp("""
        class ForwardOnly;
        class WithBody { public: void go(); };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    names = [e["className"] for e in entries]
    assert "ForwardOnly" not in names
    assert "WithBody" in names


# ---------------------------------------------------------------------------
# T-07: public method extraction
# ---------------------------------------------------------------------------

def test_member_attributes_extracted(tmp_cpp):
    """FIELD_DECL entries appear in attributes[] with visibility + type + name."""
    path = tmp_cpp("""
        class Widget {
        private:
            int count_;
            char* label_;
        protected:
            double scale_;
        public:
            void tick();
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "Widget")
    attrs = entry.get("attributes", [])
    assert any("count_" in a for a in attrs), attrs
    assert any("label_" in a for a in attrs), attrs
    assert any("scale_" in a for a in attrs), attrs
    assert any(a.startswith("-") for a in attrs)
    assert any(a.startswith("#") for a in attrs)


def test_public_methods_extracted(tmp_cpp):
    """Public methods appear in interfaces[], private do not."""
    path = tmp_cpp("""
        class DiskManager {
            void _internal();        // private by default
        public:
            void readBlock(int lba, char* buf);
            void writeBlock(int lba, const char* buf);
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "DiskManager")
    ifaces = entry["interfaces"]
    assert any("readBlock" in sig for sig in ifaces), f"readBlock missing from {ifaces}"
    assert any("writeBlock" in sig for sig in ifaces), f"writeBlock missing from {ifaces}"
    assert all("_internal" not in sig for sig in ifaces), "_internal should be private"


def test_pure_virtual_methods_included(tmp_cpp):
    """Pure virtual public methods should appear in interfaces."""
    path = tmp_cpp("""
        class IoBase {
        public:
            virtual void open()  = 0;
            virtual void close() = 0;
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "IoBase")
    ifaces = entry["interfaces"]
    assert any("open" in sig for sig in ifaces)
    assert any("close" in sig for sig in ifaces)


# ---------------------------------------------------------------------------
# T-08: composition / aggregation detection
# ---------------------------------------------------------------------------

def test_unique_ptr_is_composition(tmp_cpp):
    """std::unique_ptr<T> member → composition dependency on T."""
    path = tmp_cpp("""
        #include <memory>
        class NVMeDriver { public: void init(); };
        class DiskManager {
            std::unique_ptr<NVMeDriver> driver_;
        public:
            void readBlock();
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent),
                          extra_args=["-std=c++14", "-x", "c++"])
    entry = find_entry(entries, "DiskManager")
    dep = find_dep(entry, "NVMeDriver")
    assert dep["type"] == "composition", f"Expected composition, got {dep['type']}"


def test_shared_ptr_is_aggregation(tmp_cpp):
    """std::shared_ptr<T> member → aggregation dependency on T."""
    path = tmp_cpp("""
        #include <memory>
        class BufferPool { public: char* alloc(); };
        class DiskManager {
            std::shared_ptr<BufferPool> pool_;
        public:
            void flush();
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent),
                          extra_args=["-std=c++14", "-x", "c++"])
    entry = find_entry(entries, "DiskManager")
    dep = find_dep(entry, "BufferPool")
    assert dep["type"] == "aggregation", f"Expected aggregation, got {dep['type']}"


def test_raw_pointer_is_aggregation(tmp_cpp):
    """T* raw pointer member → aggregation dependency."""
    path = tmp_cpp("""
        class Logger { public: void log(); };
        class Engine {
            Logger* logger_;
        public:
            void run();
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "Engine")
    dep = find_dep(entry, "Logger")
    assert dep["type"] == "aggregation", f"Expected aggregation, got {dep['type']}"


# ---------------------------------------------------------------------------
# T-09: inheritance
# ---------------------------------------------------------------------------

def test_single_inheritance(tmp_cpp):
    """Single public base class → baseClasses[] + inheritance dependency."""
    path = tmp_cpp("""
        class IoBase { public: virtual void open() = 0; };
        class DiskManager : public IoBase {
        public:
            void open() override;
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "DiskManager")
    assert "IoBase" in entry["baseClasses"], f"baseClasses: {entry['baseClasses']}"
    dep = find_dep(entry, "IoBase")
    assert dep["type"] == "inheritance"


def test_multiple_inheritance(tmp_cpp):
    """Multiple base classes → all appear in baseClasses[]."""
    path = tmp_cpp("""
        class Serializable { public: virtual void serialize() = 0; };
        class Loggable     { public: virtual void log() = 0; };
        class StorageEngine : public Serializable, public Loggable {
        public:
            void serialize() override;
            void log() override;
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "StorageEngine")
    assert "Serializable" in entry["baseClasses"]
    assert "Loggable" in entry["baseClasses"]


# ---------------------------------------------------------------------------
# T-10: template parameters
# ---------------------------------------------------------------------------

def test_template_params_extracted(tmp_cpp):
    """Template type params appear in templateParams[]."""
    path = tmp_cpp("""
        template<typename K, typename V>
        class CacheManager {
        public:
            void put(const K& key, const V& val);
            V    get(const K& key);
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, "CacheManager")
    assert "K" in entry["templateParams"] or any("K" in p for p in entry["templateParams"])
    assert "V" in entry["templateParams"] or any("V" in p for p in entry["templateParams"])


# ---------------------------------------------------------------------------
# T-11: cardinality (vector / map)
# ---------------------------------------------------------------------------

def test_vector_member_has_cardinality(tmp_cpp):
    """std::vector<UserType> member → dependency with cardinality 1..*"""
    path = tmp_cpp("""
        #include <vector>
        class Partition { public: int id; };
        class RaidController {
            std::vector<Partition> partitions_;
        public:
            void sync();
        };
    """)
    entries = parse_files([path], project_root=str(Path(path).parent),
                          extra_args=["-std=c++14", "-x", "c++"])
    entry = find_entry(entries, "RaidController")
    # Should have a dep on Partition with cardinality
    dep = find_dep(entry, "Partition")
    assert dep.get("cardinality") == "1..*" or dep["type"] in ("association", "composition"), \
        f"dep: {dep}"


# ---------------------------------------------------------------------------
# T-12: responsibility labels
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("class_name,expected_label", [
    ("DiskManager",   "Resource Lifecycle"),
    ("EventHandler",  "Event Processing"),
    ("DataProvider",  "Data Supply"),
    ("WidgetFactory", "Object Creation"),
    ("NVMeDriver",    "Hardware Abstraction"),
    ("TaskScheduler", "Task Ordering"),
])
def test_responsibility_naming_convention(tmp_cpp, class_name, expected_label):
    """Naming-convention-based responsibility labels."""
    path = tmp_cpp(f"class {class_name} {{ public: void run(); }};")
    entries = parse_files([path], project_root=str(Path(path).parent))
    entry = find_entry(entries, class_name)
    assert entry["responsibility"] == expected_label, \
        f"{class_name}: expected '{expected_label}', got '{entry['responsibility']}'"


# ---------------------------------------------------------------------------
# Full fixture file test (uses tests/fixtures/basic.cpp)
# ---------------------------------------------------------------------------

def test_fixture_basic_cpp():
    """Parse the shared test fixture and validate key expectations."""
    fixture_path = Path(__file__).parent / "fixtures" / "basic.cpp"
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")

    entries = parse_files(
        [str(fixture_path)],
        project_root=str(fixture_path.parent.parent),
        extra_args=["-std=c++14", "-x", "c++"],
    )

    # DiskManager should be present
    entry = find_entry(entries, "DiskManager")

    # Public methods
    assert any("readBlock" in sig for sig in entry["interfaces"])
    assert any("writeBlock" in sig for sig in entry["interfaces"])

    # Inheritance
    assert "IoBase" in entry["baseClasses"]

    # NVMeDriver → composition (unique_ptr)
    dep = find_dep(entry, "NVMeDriver")
    assert dep["type"] == "composition"

    # BufferPool → aggregation (shared_ptr)
    dep2 = find_dep(entry, "BufferPool")
    assert dep2["type"] == "aggregation"

    # DriveController should exist with NVMeDriver aggregation (raw ptr)
    dc_entry = find_entry(entries, "DriveController")
    dc_dep = find_dep(dc_entry, "NVMeDriver")
    assert dc_dep["type"] == "aggregation"


def test_mermaid_method_label_strips_return_type():
    """Diagram labels must show ~dtor / method name, not bogus 'void' prefix for dtor."""
    from scanner.mermaid_generator import _format_method_label

    assert _format_method_label("void ~Entity()") == "~Entity()"
    assert _format_method_label("void learn_skill(const Skill & s)") == "learn_skill(const Skill & s)"


def test_is_definition_in_project_under_root_only():
    """Definitions outside project_root (e.g. SDK headers) must be excluded."""
    root = "/Users/foo/myproject"
    assert _is_definition_in_project("/Users/foo/myproject/src/a.cpp", root)
    assert _is_definition_in_project("/Users/foo/myproject", root)
    assert not _is_definition_in_project("/Users/foo/myproject_other/x.cpp", root)
    assert not _is_definition_in_project("/usr/include/stdlib.h", root)
