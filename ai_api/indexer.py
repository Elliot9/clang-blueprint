"""
indexer.py — TF-IDF indexer over blueprint_index.json entries.

Builds a cosine-similarity search index from the text content of each
blueprint entry (className + responsibility + interfaces).  The fitted
vectorizer and matrix are persisted to `.blueprint_tfidf.pkl` so they
survive restarts without re-fitting.
"""

from __future__ import annotations

import json
import os
import pickle
import re
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_INDEX_PATH = ".blueprint_tfidf.pkl"
DEFAULT_BLUEPRINT_PATH = "blueprint_index.json"


# ---------------------------------------------------------------------------
# Text representation
# ---------------------------------------------------------------------------

# Chinese keyword aliases keyed by class-name suffix or specific name.
# Allows bilingual queries to match English class names.
_ZH_ALIASES: dict[str, str] = {
    # Specific class names — Chinese terms + English synonyms for better recall
    "DiskManager":     "磁碟 讀寫 I/O 讀取 寫入 磁碟管理 disk read write block lba storage io",
    "NVMeController":  "NVMe 提交 佇列 完成 控制 控制器 submit queue completion poll drive",
    "BufferPool":      "記憶體 緩衝區 分配 釋放 緩衝池 memory buffer allocate release dma pool",
    "CacheManager":    "快取 緩存 key value 存取 查詢 cache lookup store evict lru",
    "NVMeDriver":      "硬體 驅動程式 初始化 驅動 NVMe硬體 hardware driver init dma nvme device",
    "EventHandler":    "事件 通知 訂閱 處理 事件處理 event listener subscribe callback dispatch handler",
    "RequestFactory":  "工廠 物件 實例 產生 建立 請求 factory create instance new make request object",
    "TaskScheduler":   "任務 排程 優先 佇列 優先佇列 task schedule background priority queue scheduling",
    "DataSerializer":  "序列化 反序列化 資料結構 轉換 二進位 serialize deserialize binary format convert",
    "ResourceManager": "元件 生命週期 資源 釋放 資源管理 lifecycle resource release manage component",
    # Pattern suffixes (applied when specific name not found)
    "Manager":    "管理 管理器 管理類 manage lifecycle",
    "Handler":    "處理 處理器 handle event listener callback",
    "Factory":    "工廠 產生 實例 建立 create new instance make",
    "Scheduler":  "排程 排程器 schedule task background priority",
    "Driver":     "驅動 驅動程式 驅動器 hardware init driver device",
    "Serializer": "序列化 反序列化 serialize deserialize binary format",
    "Pool":       "緩衝池 儲存池 分配 allocate release buffer pool",
    "Controller": "控制 控制器 submit queue control",
    "Cache":      "快取 緩存 cache lookup key value",
}

_CAMEL_SPLIT = re.compile(r"([a-z])([A-Z])|([A-Z]+)([A-Z][a-z])")


def _expand_camel(s: str) -> str:
    """Split CamelCase identifier into lowercase space-separated tokens."""
    return _CAMEL_SPLIT.sub(r"\1\3 \2\4", s).lower()


def _entry_to_text(entry: dict[str, Any]) -> str:
    """
    Convert a blueprint entry to a single searchable text blob.

    We concatenate:
    - className (repeated 5× to boost weight) + CamelCase-expanded form
    - Chinese keyword aliases for bilingual queries
    - namespace, responsibility
    - interface signatures with CamelCase expansion of method names
    - base class names, dependency target names
    """
    parts: list[str] = []

    class_name = entry.get("className", "")
    if class_name:
        expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", class_name)
        parts.extend([class_name] * 5)  # weight className more heavily
        if expanded != class_name:
            parts.append(expanded)
        # Add Chinese aliases: specific name first, then suffix pattern
        # Also add character-level spacing so individual CJK chars are indexed
        _cjk_re = re.compile(r"([\u4e00-\u9fff\u3040-\u30ff])")
        zh_text = None
        if class_name in _ZH_ALIASES:
            zh_text = _ZH_ALIASES[class_name]
        else:
            for suffix, zh in _ZH_ALIASES.items():
                if class_name.endswith(suffix):
                    zh_text = zh
                    break
        if zh_text:
            parts.append(zh_text)
            # Also index each CJK character individually for substring matching
            char_spaced = _cjk_re.sub(r" \1 ", zh_text)
            parts.append(char_spaced)

    ns = entry.get("namespace", "")
    if ns:
        parts.append(ns.replace("::", " "))

    responsibility = entry.get("responsibility", "")
    if responsibility:
        parts.append(responsibility)

    for attr in entry.get("attributes", []):
        tokens = re.sub(r"[()<>,*&+\-#]", " ", str(attr))
        parts.append(tokens)

    for iface in entry.get("interfaces", []):
        # Strip special characters, then also expand CamelCase method names
        tokens = re.sub(r"[()<>,*&]", " ", iface)
        parts.append(tokens)
        # Extract and expand method name (last token before '(')
        m = re.match(r".*?(\w+)\s*\(", iface)
        if m:
            parts.append(_expand_camel(m.group(1)))

    # P5-13/14: interfaceMeta usedTypes — include type names + CamelCase-expanded forms
    for meta in entry.get("interfaceMeta", []):
        # Include full method signature text
        sig = meta.get("signature", "")
        if sig:
            tokens = re.sub(r"[()<>,*&]", " ", sig)
            parts.append(tokens)
        # Include each usedType with CamelCase expansion (P5-14)
        for used_type in meta.get("usedTypes", []):
            short = used_type.split("::")[-1]  # strip namespace
            parts.append(short)
            parts.append(_expand_camel(short))

    for base in entry.get("baseClasses", []):
        base_expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
        parts.append(base)
        parts.append(base_expanded)

    for dep in entry.get("dependencies", []):
        target = dep.get("target", "")
        if target:
            target_expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", target)
            parts.append(target)
            parts.append(target_expanded)
            parts.append(dep.get("type", ""))

    for tp in entry.get("templateParams", []):
        parts.append(tp)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# P5-15: Method attribution helper
# ---------------------------------------------------------------------------

def _find_matched_methods(entry: dict[str, Any], query_tokens: set[str]) -> list[str]:
    """
    Return the signatures of methods whose signature or usedTypes overlap
    with any query token.  Used to tell callers *why* an entry was returned.
    """
    matched: list[str] = []
    for meta in entry.get("interfaceMeta", []):
        sig = meta.get("signature", "")
        used = meta.get("usedTypes", [])
        # Tokenize the signature
        sig_tokens = set(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]|\b\w\w+\b", sig.lower()))
        # Tokenize usedTypes (short names + camel-expanded)
        type_tokens: set[str] = set()
        for t in used:
            short = t.split("::")[-1]
            type_tokens.update(re.findall(r"[a-z]+", _expand_camel(short)))
            type_tokens.add(short.lower())
        combined = sig_tokens | type_tokens
        if combined & query_tokens:
            matched.append(sig)
    return matched


# ---------------------------------------------------------------------------
# Indexer class
# ---------------------------------------------------------------------------

class BlueprintIndexer:
    """
    TF-IDF based search index over blueprint entries.

    Usage:
        indexer = BlueprintIndexer()
        indexer.build(entries)
        results = indexer.query("disk I/O manager", top_k=5)
    """

    def __init__(
        self,
        blueprint_path: str = DEFAULT_BLUEPRINT_PATH,
        index_path: str = DEFAULT_INDEX_PATH,
    ) -> None:
        self.blueprint_path = blueprint_path
        self.index_path = index_path

        self._entries: list[dict[str, Any]] = []
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix: Optional[np.ndarray] = None  # shape: (n_docs, n_features)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, entries: Optional[list[dict[str, Any]]] = None) -> None:
        """
        Build the TF-IDF index.

        Args:
            entries: If provided, use these directly.  Otherwise, load from
                     self.blueprint_path.
        """
        if entries is None:
            entries = self._load_blueprint_json()

        if not entries:
            raise ValueError(
                f"No entries to index.  "
                f"Run `blueprint scan` to generate {self.blueprint_path}."
            )

        self._entries = entries
        corpus = [_entry_to_text(e) for e in entries]

        self._vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),        # unigrams + bigrams
            sublinear_tf=True,         # log(1 + tf) scaling
            min_df=1,
            max_features=50_000,
            strip_accents=None,        # preserve Unicode (CJK)
            # Match: individual CJK characters OR ASCII words of 2+ chars
            token_pattern=r"(?u)[\u4e00-\u9fff\u3040-\u30ff]|\b\w\w+\b",
        )
        self._matrix = self._vectorizer.fit_transform(corpus)

        print(
            f"[indexer] Built TF-IDF index: {len(entries)} docs, "
            f"{self._matrix.shape[1]} features.",
            file=sys.stderr,
        )
        self._save()

    def _load_blueprint_json(self) -> list[dict[str, Any]]:
        p = Path(self.blueprint_path)
        if not p.exists():
            raise FileNotFoundError(
                f"Blueprint index not found: {self.blueprint_path}.  "
                "Run `blueprint scan` first."
            )
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist the fitted vectorizer, matrix, and entries to disk."""
        payload = {
            "version": 1,
            "entries": self._entries,
            "vectorizer": self._vectorizer,
            "matrix": self._matrix,
        }
        tmp_path = self.index_path + ".tmp"
        try:
            with open(tmp_path, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp_path, self.index_path)
            print(f"[indexer] Saved index to {self.index_path}", file=sys.stderr)
        except Exception as exc:
            print(f"[indexer] WARNING: Could not save index: {exc}", file=sys.stderr)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> bool:
        """
        Attempt to load a previously saved index.

        Returns:
            True if loaded successfully, False if the file is missing/corrupt.
        """
        p = Path(self.index_path)
        if not p.exists():
            return False
        try:
            with open(p, "rb") as f:
                payload = pickle.load(f)
            if payload.get("version") != 1:
                print("[indexer] Index version mismatch; will rebuild.", file=sys.stderr)
                return False
            self._entries = payload["entries"]
            self._vectorizer = payload["vectorizer"]
            self._matrix = payload["matrix"]
            print(
                f"[indexer] Loaded index: {len(self._entries)} docs from {self.index_path}",
                file=sys.stderr,
            )
            return True
        except (pickle.UnpicklingError, KeyError, EOFError, Exception) as exc:
            print(f"[indexer] WARNING: Cannot load index: {exc}", file=sys.stderr)
            return False

    def ensure_loaded(self) -> None:
        """Load from disk if not already in memory; build from scratch if needed."""
        if self._matrix is not None:
            return
        if not self.load():
            self.build()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        natural_language: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search the index for blueprint entries relevant to `natural_language`.

        Args:
            natural_language: Free-form English query.
            top_k: Number of top results to return.

        Returns:
            List of dicts: [{"score": float, "entry": <blueprint entry>}, ...]
            sorted by descending relevance score.
        """
        self.ensure_loaded()

        if self._vectorizer is None or self._matrix is None:
            raise RuntimeError("Index is empty.  Call build() first.")

        if not natural_language.strip():
            return []

        # Preprocess: split consecutive CJK characters with spaces so each
        # character becomes its own token (matching individual chars in corpus)
        processed = re.sub(
            r"([\u4e00-\u9fff\u3040-\u30ff])",
            r" \1 ",
            natural_language,
        ).strip()

        # Vectorize query
        query_vec = self._vectorizer.transform([processed])
        # Cosine similarities: shape (1, n_docs)
        sims = cosine_similarity(query_vec, self._matrix).flatten()

        # Get top_k indices (unsorted first, then sort)
        k = min(top_k, len(self._entries))
        top_indices = np.argpartition(sims, -k)[-k:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        # P5-15: tokenize query for matchedMethods attribution
        query_tokens = set(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]|\b\w\w+\b", processed.lower()))

        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score < 1e-9:
                continue  # Skip zero-score results
            entry = self._entries[idx]
            # Find which methods contributed (signature or usedTypes overlap with query)
            matched_methods = _find_matched_methods(entry, query_tokens)
            results.append({
                "score": round(score, 6),
                "entry": entry,
                "matchedMethods": matched_methods,
            })

        return results

    def query_batch(
        self,
        queries: list[str],
        top_k: int = 5,
    ) -> list[list[dict[str, Any]]]:
        """Run multiple queries at once (more efficient than sequential calls)."""
        self.ensure_loaded()
        if self._vectorizer is None or self._matrix is None:
            raise RuntimeError("Index is empty.  Call build() first.")

        query_vecs = self._vectorizer.transform(queries)
        sims_matrix = cosine_similarity(query_vecs, self._matrix)

        results = []
        for q, sims in zip(queries, sims_matrix):
            k = min(top_k, len(self._entries))
            top_indices = np.argpartition(sims, -k)[-k:]
            top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]
            q_tokens = set(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]|\b\w\w+\b", q.lower()))
            batch_result = []
            for idx in top_indices:
                score = float(sims[idx])
                if score < 1e-9:
                    continue
                entry = self._entries[idx]
                batch_result.append({
                    "score": round(score, 6),
                    "entry": entry,
                    "matchedMethods": _find_matched_methods(entry, q_tokens),
                })
            results.append(batch_result)

        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def num_docs(self) -> int:
        return len(self._entries)

    @property
    def is_built(self) -> bool:
        return self._matrix is not None

    def top_terms(self, class_name: str, n: int = 10) -> list[str]:
        """
        Return the top TF-IDF terms for a given className.
        Useful for debugging the index.
        """
        if self._vectorizer is None or self._matrix is None:
            return []
        for i, entry in enumerate(self._entries):
            if entry.get("className") == class_name:
                row = self._matrix[i]
                feature_names = self._vectorizer.get_feature_names_out()
                # row is a sparse matrix row
                arr = row.toarray().flatten()
                top_idx = np.argsort(arr)[::-1][:n]
                return [feature_names[j] for j in top_idx if arr[j] > 0]
        return []
