"""
incremental.py — Hash-based incremental scan cache for clang-blueprint.

Maintains a `.blueprint_cache.json` file that stores a SHA256 hash and
last-scan timestamp per source file. Only files whose hash has changed
since the last run are re-parsed; unchanged entries are read from the cache.
All writes to the cache file are atomic (write-then-rename) to avoid
corruption on interruption.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from scanner.ast_parser import parse_files, scan_directory, _is_excluded, load_blueprintignore

DEFAULT_CACHE_NAME = ".blueprint_cache.json"


# ---------------------------------------------------------------------------
# Cache schema
# {
#   "version": 1,
#   "files": {
#     "/abs/path/to/file.cpp": {
#       "hash": "<sha256hex>",
#       "last_scanned": <unix_timestamp_float>,
#       "entries": [ <blueprint_index entries> ]
#     }
#   }
# }
# ---------------------------------------------------------------------------

CACHE_VERSION = 1


def _sha256_file(path: str) -> str:
    """Compute SHA256 of a file's content."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError as e:
        print(f"[incremental] WARNING: cannot read {path}: {e}", file=sys.stderr)
        return ""
    return h.hexdigest()


def _atomic_write_json(path: str, data: Any) -> None:
    """Write JSON to `path` atomically by writing to a temp file then renaming."""
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # On Windows, the target must not exist before rename
        if sys.platform == "win32" and os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_cache(cache_path: str) -> dict[str, Any]:
    """Load the cache file, returning an empty structure if missing or corrupt."""
    empty: dict[str, Any] = {"version": CACHE_VERSION, "files": {}}
    p = Path(cache_path)
    if not p.exists():
        return empty
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
            print(
                f"[incremental] Cache version mismatch or corrupt; starting fresh.",
                file=sys.stderr,
            )
            return empty
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[incremental] WARNING: Cannot load cache {cache_path}: {e}", file=sys.stderr)
        return empty


def save_cache(cache_path: str, cache: dict[str, Any]) -> None:
    """Atomically persist the cache to disk."""
    _atomic_write_json(cache_path, cache)


def incremental_scan(
    project_root: str,
    compile_commands_path: Optional[str] = None,
    cache_path: Optional[str] = None,
    extensions: tuple[str, ...] = (".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx"),
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """
    Perform an incremental scan of `project_root`.

    - Files whose SHA256 hash matches the cache are **not** re-parsed.
    - Changed or new files are parsed via ast_parser.parse_files().
    - Files present in the cache but no longer on disk are evicted.
    - The cache is atomically updated after parsing.

    Returns:
        Merged list of blueprint_index entry dicts (cached + newly parsed).
    """
    _DEFAULT_EXCLUDES = ["third_party", "vendor", "extern", "build", ".git"]

    root = Path(project_root).resolve()
    if cache_path is None:
        cache_path = str(root / DEFAULT_CACHE_NAME)

    # P6-03/04: build final exclude pattern list (CLI + .blueprintignore + defaults)
    if exclude_patterns is None:
        patterns = _DEFAULT_EXCLUDES + load_blueprintignore(str(root))
    else:
        patterns = list(exclude_patterns) + load_blueprintignore(str(root))

    print(
        f"[blueprint] Active exclude patterns ({len(patterns)}): "
        f"{', '.join(patterns[:8])}{'…' if len(patterns) > 8 else ''}",
        file=sys.stderr,
    )

    cache = load_cache(cache_path)
    file_cache: dict[str, Any] = cache.get("files", {})

    # Discover all current source files
    all_source_files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if _is_excluded(str(path), str(root), patterns):
            continue
        all_source_files.append(str(path.resolve()))

    # P6-03: also evict cached entries that now match exclude patterns
    excluded_from_cache = [fp for fp in file_cache if _is_excluded(fp, str(root), patterns)]
    for fp in excluded_from_cache:
        del file_cache[fp]
        print(f"[incremental] Evicted excluded path from cache: {fp}", file=sys.stderr)

    current_files_set = set(all_source_files)

    # Evict deleted files from cache
    deleted = [fp for fp in file_cache if fp not in current_files_set]
    for fp in deleted:
        del file_cache[fp]
        print(f"[incremental] Evicted deleted file from cache: {fp}", file=sys.stderr)

    # Determine which files need re-parsing
    changed_files: list[str] = []
    unchanged_files: list[str] = []

    for fp in all_source_files:
        current_hash = _sha256_file(fp)
        if not current_hash:
            continue
        cached = file_cache.get(fp)
        if cached and cached.get("hash") == current_hash:
            unchanged_files.append(fp)
        else:
            changed_files.append(fp)

    print(
        f"[incremental] {len(unchanged_files)} unchanged, "
        f"{len(changed_files)} changed/new files.",
        file=sys.stderr,
    )

    # Re-parse only changed files
    newly_parsed_entries: list[dict[str, Any]] = []
    if changed_files:
        newly_parsed_entries = parse_files(
            changed_files,
            project_root=str(root),
            compile_commands_path=compile_commands_path,
            exclude_patterns=patterns,
        )

        # Group newly parsed entries back by source file for cache storage.
        # We do a best-effort mapping: an entry's fileLocation tells us which
        # file it came from.
        entries_by_file: dict[str, list[dict[str, Any]]] = {fp: [] for fp in changed_files}
        for entry in newly_parsed_entries:
            file_loc = entry.get("fileLocation", "")
            if not file_loc:
                continue
            # fileLocation is relative to project_root
            abs_loc = str((root / file_loc).resolve())
            if abs_loc in entries_by_file:
                entries_by_file[abs_loc].append(entry)
            else:
                # Try a softer match — last path component
                for fp in changed_files:
                    if fp.endswith(file_loc):
                        entries_by_file[fp].append(entry)
                        break

        # Update cache for changed files
        for fp in changed_files:
            current_hash = _sha256_file(fp)
            file_cache[fp] = {
                "hash": current_hash,
                "last_scanned": time.time(),
                "entries": entries_by_file.get(fp, []),
            }

    # Collect all entries: cached (unchanged) + newly parsed
    merged_entries: list[dict[str, Any]] = []

    for fp in unchanged_files:
        merged_entries.extend(file_cache[fp].get("entries", []))

    merged_entries.extend(newly_parsed_entries)

    # Deduplicate by className (last writer wins for same-named classes)
    seen: dict[str, dict[str, Any]] = {}
    for entry in merged_entries:
        key = f"{entry.get('namespace', '')}::{entry.get('className', '')}"
        seen[key] = entry
    deduped = list(seen.values())

    # Persist updated cache
    cache["files"] = file_cache
    save_cache(cache_path, cache)

    print(
        f"[incremental] Total entries after merge: {len(deduped)}",
        file=sys.stderr,
    )
    return deduped


def invalidate_cache(cache_path: str) -> None:
    """Remove the cache file entirely, forcing a full re-scan on next run."""
    p = Path(cache_path)
    if p.exists():
        p.unlink()
        print(f"[incremental] Cache invalidated: {cache_path}", file=sys.stderr)


def get_cache_stats(cache_path: str) -> dict[str, Any]:
    """Return statistics about the current cache state."""
    cache = load_cache(cache_path)
    file_cache = cache.get("files", {})
    total_entries = sum(
        len(v.get("entries", [])) for v in file_cache.values()
    )
    return {
        "cached_files": len(file_cache),
        "total_entries": total_entries,
        "cache_path": cache_path,
        "version": cache.get("version"),
    }
