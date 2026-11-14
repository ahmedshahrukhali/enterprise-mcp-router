"""
Real 384-dim dense sentence bi-encoder provider using BAAI/bge-small-en-v1.5.

Supports two modes cleanly:
1. Fast precomputed cache lookup (`src/registry/bge_cache.json`) for deterministic,
   zero-weight-download CI and unit testing over the tool catalog and eval suite.
2. Live local inference with `BAAI/bge-small-en-v1.5` via HuggingFace `transformers`
   for novel queries at runtime when `torch` and `transformers` are installed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence

BGE_MODEL_ID = "BAAI/bge-small-en-v1.5"
BGE_DIMENSION = 384
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent / "bge_cache.json"


def format_tool_document(name: str, domain: str, description: str) -> str:
    """Formats an MCP tool specification into its canonical bi-encoder document string."""
    return f"{name} ({domain}): {description}"


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Computes clamped cosine similarity [0, 1] between normalized vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return max(0.0, min(1.0, float(dot)))


def _l2_normalize(vec: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(float(v) / norm, 5) for v in vec]


class BGEEmbeddingProvider:
    """Lazy loader and precomputed cache reader for BAAI/bge-small-en-v1.5 embeddings."""

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self._tool_vectors: Dict[str, List[float]] = {}
        self._query_vectors: Dict[str, List[float]] = {}
        self._cache_loaded = False
        self._tokenizer = None
        self._model = None
        self._model_load_failed = False

    def _ensure_cache_loaded(self) -> None:
        if self._cache_loaded:
            return
        self._cache_loaded = True
        if not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self._tool_vectors = payload.get("tools", {})
            self._query_vectors = payload.get("queries", {})
        except Exception:
            self._tool_vectors = {}
            self._query_vectors = {}

    def _ensure_live_model(self) -> bool:
        if self._model is not None and self._tokenizer is not None:
            return True
        if self._model_load_failed:
            return False
        try:
            # Guard against torchvision C++ op mismatch on mixed Windows CUDA/CPU builds
            sys.modules.setdefault("torchvision", None)  # type: ignore[arg-type]
            import torch
            from transformers import AutoModel, AutoTokenizer

            try:
                self._tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL_ID, local_files_only=True)
                self._model = AutoModel.from_pretrained(BGE_MODEL_ID, local_files_only=True)
            except Exception:
                self._tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL_ID)
                self._model = AutoModel.from_pretrained(BGE_MODEL_ID)
            self._model.eval()
            self._torch = torch
            return True
        except Exception:
            self._model_load_failed = True
            return False

    def encode_live_texts(self, texts: Sequence[str], is_query: bool = False) -> Optional[List[List[float]]]:
        """Encodes arbitrary strings into L2-normalized 384-dim CLS vectors via BAAI/bge-small-en-v1.5."""
        if not texts or not self._ensure_live_model():
            return None
        formatted = [
            f"{BGE_QUERY_INSTRUCTION}{t}" if is_query else t
            for t in texts
        ]
        torch = self._torch
        with torch.no_grad():
            inputs = self._tokenizer(
                formatted,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            outputs = self._model(**inputs)
            cls_emb = outputs.last_hidden_state[:, 0]
            normalized = torch.nn.functional.normalize(cls_emb, p=2, dim=-1)
            return [[round(float(x), 5) for x in row] for row in normalized.cpu().tolist()]

    def embed_tool(self, name: str, domain: str, description: str) -> Optional[List[float]]:
        """Returns 384-dim BGE embedding for a tool from cache or live encoder."""
        self._ensure_cache_loaded()
        cached = self._tool_vectors.get(name)
        if cached is not None:
            return cached
        vecs = self.encode_live_texts([format_tool_document(name, domain, description)], is_query=False)
        if vecs:
            self._tool_vectors[name] = vecs[0]
            return vecs[0]
        return None

    def embed_query(self, query: str) -> Optional[List[float]]:
        """Returns 384-dim BGE embedding for a query from cache or live encoder."""
        self._ensure_cache_loaded()
        cached = self._query_vectors.get(query)
        if cached is not None:
            return cached
        vecs = self.encode_live_texts([query], is_query=True)
        if vecs:
            self._query_vectors[query] = vecs[0]
            return vecs[0]
        return None

    def is_available_for_query(self, query: str) -> bool:
        """Returns True if BGE vectors exist in cache for this query or live model loads."""
        self._ensure_cache_loaded()
        return query in self._query_vectors or self._ensure_live_model()

    def build_and_save_cache(
        self,
        tool_entries: Sequence[Dict[str, str]],
        queries: Sequence[str],
        output_path: Optional[Path] = None,
    ) -> Dict[str, object]:
        """Encodes all tool documents and evaluation queries live and writes compact JSON cache."""
        target = output_path or self.cache_path
        tool_texts = [format_tool_document(t["name"], t["domain"], t["description"]) for t in tool_entries]
        tool_vecs = self.encode_live_texts(tool_texts, is_query=False)
        query_vecs = self.encode_live_texts(list(queries), is_query=True)
        if tool_vecs is None or query_vecs is None:
            raise RuntimeError("BAAI/bge-small-en-v1.5 model could not be loaded to build embedding cache.")

        payload = {
            "model_id": BGE_MODEL_ID,
            "dimension": len(tool_vecs[0]) if tool_vecs else BGE_DIMENSION,
            "query_instruction": BGE_QUERY_INSTRUCTION,
            "tools": {t["name"]: _l2_normalize(vec) for t, vec in zip(tool_entries, tool_vecs)},
            "queries": {q: _l2_normalize(vec) for q, vec in zip(queries, query_vecs)},
        }
        target.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        self._tool_vectors = payload["tools"]  # type: ignore[assignment]
        self._query_vectors = payload["queries"]  # type: ignore[assignment]
        self._cache_loaded = True
        return {
            "path": str(target),
            "model_id": BGE_MODEL_ID,
            "dimension": payload["dimension"],
            "tool_count": len(self._tool_vectors),
            "query_count": len(self._query_vectors),
        }


DEFAULT_BGE_PROVIDER = BGEEmbeddingProvider()
