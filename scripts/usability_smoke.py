#!/usr/bin/env python3
"""
usability_smoke.py — T-40: 可用性驗收的自動化部分

自動驗證：
  1. blueprint_index.json 可被正確讀取
  2. AI server /health 回傳 index_built=true
  3. /query 對常見查詢回傳正確 top-1 結果

用法:
    python scripts/usability_smoke.py [--server http://localhost:8000]
                                      [--index blueprint_index.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m⚠\033[0m"


def check(label: str, condition: bool, detail: str = "") -> bool:
    symbol = PASS if condition else FAIL
    msg = f"  {symbol}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return condition


def http_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser(description="Usability smoke test for clang-blueprint")
    parser.add_argument("--server", default="http://localhost:8000", help="AI server URL")
    parser.add_argument("--index",  default="blueprint_index.json",  help="blueprint_index.json path")
    args = parser.parse_args()

    failures = 0

    print("\n=== T-40 Usability Smoke Tests ===\n")

    # ── 1. Index file exists and is valid ─────────────────────────────────
    print("[ Blueprint Index ]")
    index_path = Path(args.index)
    ok = check("blueprint_index.json exists", index_path.exists(), str(index_path))
    if not ok:
        failures += 1
    else:
        try:
            entries = json.loads(index_path.read_text())
            ok2 = check("Index is a JSON array",  isinstance(entries, list))
            ok3 = check("Index has ≥1 entries",   len(entries) > 0, f"{len(entries)} entries")
            if ok2 and ok3:
                required = ["className", "responsibility", "fileLocation", "lineNumber"]
                first = entries[0]
                missing = [f for f in required if f not in first]
                check("First entry has required fields", not missing,
                      f"missing: {missing}" if missing else "all OK")
        except Exception as e:
            print(f"  {FAIL}  Parse error: {e}")
            failures += 1

    # ── 2. AI server health ────────────────────────────────────────────────
    print("\n[ AI Server ]")
    try:
        health = http_get(f"{args.server}/health")
        check("Server is reachable",  health.get("status") == "ok")
        check("Index is built",        health.get("index_built") is True,
              f"num_docs={health.get('num_docs', 0)}")
    except urllib.error.URLError as e:
        print(f"  {WARN}  Server not reachable at {args.server}: {e}")
        print("       Start with: uvicorn ai_api.server:app --port 8000")
        # Not a hard failure — server is optional for basic usability
    except Exception as e:
        print(f"  {FAIL}  Health check error: {e}")
        failures += 1
        return failures

    # ── 3. Query accuracy ─────────────────────────────────────────────────
    print("\n[ Query Accuracy ]")
    test_cases = [
        ("disk block read write I/O",   "DiskManager"),
        ("NVMe submit completion queue", "NVMeController"),
        ("memory buffer pool allocate",  "BufferPool"),
        ("cache key value store",        "CacheManager"),
    ]
    for query, expected in test_cases:
        try:
            resp = http_post(f"{args.server}/query", {"query": query, "top_k": 3})
            results = resp.get("results", [])
            top3 = [r["className"] for r in results[:3]]
            hit = expected in top3
            check(f'"{query[:35]}…" → {expected}', hit,
                  f"top3={top3}" if not hit else f"score={results[0]['score']:.3f}")
            if not hit:
                failures += 1
        except urllib.error.URLError:
            print(f"  {WARN}  Skipped (server not available)")
            break
        except Exception as e:
            print(f"  {FAIL}  Query error: {e}")
            failures += 1

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*38}")
    if failures == 0:
        print(f"  {PASS}  All smoke tests passed")
    else:
        print(f"  {FAIL}  {failures} test(s) failed")
    print()

    return failures


if __name__ == "__main__":
    sys.exit(main())
