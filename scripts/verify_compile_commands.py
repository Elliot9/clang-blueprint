#!/usr/bin/env python3
"""
verify_compile_commands.py — T-02: 驗證 compile_commands.json 格式正確性

用法:
    python scripts/verify_compile_commands.py --project-root <cmake_build_dir>
    python scripts/verify_compile_commands.py --file path/to/compile_commands.json

產生步驟（CMake 專案）:
    cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    python scripts/verify_compile_commands.py --project-root build/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REQUIRED_FIELDS = {"file", "directory", "command"}   # or "arguments" instead of "command"


def verify(compile_commands_path: str) -> bool:
    p = Path(compile_commands_path)
    if not p.exists():
        print(f"✗ File not found: {compile_commands_path}", file=sys.stderr)
        return False

    try:
        with open(p, encoding="utf-8") as f:
            entries = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}", file=sys.stderr)
        return False

    if not isinstance(entries, list):
        print("✗ compile_commands.json must be a JSON array", file=sys.stderr)
        return False

    if not entries:
        print("⚠ compile_commands.json is empty — did CMake find any source files?")
        return False

    errors = []
    cpp_files = []

    for i, entry in enumerate(entries):
        # Must have "file" and "directory"
        if "file" not in entry:
            errors.append(f"  Entry {i}: missing 'file'")
            continue
        if "directory" not in entry:
            errors.append(f"  Entry {i}: missing 'directory'")
            continue
        # Must have either "command" or "arguments"
        if "command" not in entry and "arguments" not in entry:
            errors.append(f"  Entry {i} ({entry['file']}): missing 'command' or 'arguments'")
            continue

        abs_file = Path(entry["directory"]) / entry["file"]
        cpp_files.append(str(abs_file))

    if errors:
        print(f"✗ {len(errors)} validation error(s):")
        for e in errors[:10]:
            print(e)
        return False

    # Check that at least some source files actually exist
    missing = [f for f in cpp_files[:20] if not Path(f).exists()]
    if missing:
        print(f"⚠ {len(missing)} source file(s) referenced but not found on disk:")
        for m in missing[:5]:
            print(f"  {m}")
        print("  (This may be normal if files are generated during build)")

    print(f"✓ compile_commands.json is valid")
    print(f"  Entries : {len(entries)}")
    print(f"  Example : {entries[0]['file']}")

    # Check libclang can open it
    try:
        import clang.cindex as cindex
        db_dir = str(p.parent)
        db = cindex.CompilationDatabase.fromDirectory(db_dir)
        # Try loading commands for the first file
        first_file = entries[0]["file"]
        if not os.path.isabs(first_file):
            first_file = str(Path(entries[0]["directory"]) / first_file)
        cmds = db.getCompileCommands(first_file)
        if cmds:
            args = list(cmds[0].arguments)
            print(f"✓ libclang can read compile_commands.json ({len(args)} args for first entry)")
        else:
            print(f"⚠ libclang found no commands for {entries[0]['file']}")
    except ImportError:
        print("⚠ libclang not installed — skipping libclang validation")
    except Exception as e:
        print(f"⚠ libclang validation error: {e}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify compile_commands.json for clang-blueprint compatibility"
    )
    parser.add_argument(
        "--project-root", "-p",
        help="CMake build directory containing compile_commands.json",
    )
    parser.add_argument(
        "--file", "-f",
        help="Direct path to compile_commands.json",
    )
    args = parser.parse_args()

    if args.file:
        path = args.file
    elif args.project_root:
        candidates = [
            os.path.join(args.project_root, "compile_commands.json"),
            os.path.join(args.project_root, "build", "compile_commands.json"),
        ]
        path = next((c for c in candidates if os.path.exists(c)), candidates[0])
    else:
        # Auto-detect
        candidates = ["compile_commands.json", "build/compile_commands.json"]
        path = next((c for c in candidates if os.path.exists(c)), "compile_commands.json")

    print(f"Verifying: {path}")
    ok = verify(path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
