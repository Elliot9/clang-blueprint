"""
test_rag_accuracy.py — T-51: RAG top-1 hit rate evaluation

Loads the 20-query groundtruth set from rag_groundtruth.json,
builds a TF-IDF index over the examples/storage_engine blueprint,
and measures top-1 / top-3 accuracy.

Target: top-1 hit rate ≥ 80% (16/20 queries).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from ai_api.indexer import BlueprintIndexer
except ImportError as e:
    pytest.skip(f"scikit-learn not available: {e}", allow_module_level=True)

GROUNDTRUTH_PATH = Path(__file__).parent / "rag_groundtruth.json"
BLUEPRINT_PATH   = ROOT / "examples" / "storage_engine" / "blueprint_index.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def indexer():
    if not BLUEPRINT_PATH.exists():
        pytest.skip(
            f"Example blueprint not found at {BLUEPRINT_PATH}. "
            "Run: python -m scanner.main scan --project-root examples/storage_engine"
        )
    idx = BlueprintIndexer(
        blueprint_path=str(BLUEPRINT_PATH),
        index_path=str(ROOT / ".blueprint_tfidf_test.pkl"),
    )
    idx.build()
    return idx


@pytest.fixture(scope="module")
def groundtruth():
    with open(GROUNDTRUTH_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Accuracy tests (T-51)
# ---------------------------------------------------------------------------

def test_top1_hit_rate(indexer, groundtruth):
    """Top-1 accuracy must be ≥ 80% (16 / 20)."""
    hits = 0
    misses = []

    for gt in groundtruth:
        results = indexer.query(gt["query"], top_k=1)
        if results:
            top1 = results[0]["entry"]["className"]
            if top1 == gt["expected_top1"]:
                hits += 1
            else:
                misses.append({
                    "id":       gt["id"],
                    "query":    gt["query"],
                    "expected": gt["expected_top1"],
                    "got":      top1,
                    "score":    results[0]["score"],
                })
        else:
            misses.append({
                "id":       gt["id"],
                "query":    gt["query"],
                "expected": gt["expected_top1"],
                "got":      "(no results)",
                "score":    0.0,
            })

    hit_rate = hits / len(groundtruth)
    print(f"\nTop-1 hit rate: {hits}/{len(groundtruth)} = {hit_rate:.1%}")
    if misses:
        print("Misses:")
        for m in misses:
            print(f"  [{m['id']}] query='{m['query'][:40]}' "
                  f"expected={m['expected']} got={m['got']} score={m['score']:.3f}")

    assert hit_rate >= 0.80, (
        f"Top-1 hit rate {hit_rate:.1%} is below 80% target. "
        f"Misses: {[m['id'] for m in misses]}"
    )


def test_top3_hit_rate(indexer, groundtruth):
    """Top-3 accuracy must be ≥ 90% (18 / 20)."""
    hits = 0
    misses = []

    for gt in groundtruth:
        results = indexer.query(gt["query"], top_k=3)
        top3_names = [r["entry"]["className"] for r in results]
        expected_in_top3 = gt.get("expected_in_top3", [gt["expected_top1"]])

        if any(e in top3_names for e in expected_in_top3):
            hits += 1
        else:
            misses.append({
                "id":      gt["id"],
                "query":   gt["query"],
                "expected": expected_in_top3,
                "got":     top3_names,
            })

    hit_rate = hits / len(groundtruth)
    print(f"\nTop-3 hit rate: {hits}/{len(groundtruth)} = {hit_rate:.1%}")

    assert hit_rate >= 0.90, (
        f"Top-3 hit rate {hit_rate:.1%} is below 90% target. "
        f"Misses: {[m['id'] for m in misses]}"
    )


def test_all_queries_return_results(indexer, groundtruth):
    """Every query must return at least one result (index coverage check)."""
    empty = []
    for gt in groundtruth:
        results = indexer.query(gt["query"], top_k=1)
        if not results:
            empty.append(gt["id"])
    assert not empty, f"Queries returned no results: {empty}"


def test_scores_are_positive(indexer, groundtruth):
    """Top-1 result score must be > 0 for every query."""
    low_score = []
    for gt in groundtruth:
        results = indexer.query(gt["query"], top_k=1)
        if results and results[0]["score"] <= 0:
            low_score.append(gt["id"])
    assert not low_score, f"Queries had zero score: {low_score}"
