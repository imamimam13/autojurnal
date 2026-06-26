import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


COLLECTION_PREFIX = "papers_"
MAX_DIM = 50000
DATA_DIR = Path.home() / ".autojurnal"


def _collection_name(hash_str: str) -> str:
    return f"{COLLECTION_PREFIX}{hash_str}"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class ChunkStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(DATA_DIR / "qdrant_rag"))
        self.chunks: list[dict[str, Any]] = []
        self._built = False
        self.paper_hash: Optional[str] = None
        self._generation_count = 0

        self._embed_model = None
        self._use_fastembed = False

        # TF-IDF state (only used when FastEmbed unavailable)
        self._vocab: Optional[dict[str, int]] = None
        self._vectors: Optional[np.ndarray] = None

        self._try_init_fastembed()
        self._load_hash()

    # ---- Persistence helpers ----

    def _hash_path(self) -> Path:
        return DATA_DIR / "rag_paper_hash.json"

    def _save_hash(self):
        data = {"paper_hash": self.paper_hash}
        self._hash_path().write_text(json.dumps(data))
        print(f"[RAG] Saved paper_hash: {self.paper_hash[:12] if self.paper_hash else 'None'}...")

    def _load_hash(self):
        path = self._hash_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                h = data.get("paper_hash")
                if h:
                    col = _collection_name(h)
                    if self.client.collection_exists(col):
                        self.paper_hash = h
                        print(f"[RAG] Restored paper_hash: {h[:12]}... (collection exists)")
                        # Rebuild in-memory chunks
                        self._restore_from_collection(col)
                    else:
                        print(f"[RAG] Stored paper_hash {h[:12]}... but collection not found, starting fresh")
            except Exception as e:
                print(f"[RAG] Error loading hash: {e}")

    def _restore_from_collection(self, col: str):
        scroll = self.client.scroll(
            collection_name=col,
            with_payload=True,
            with_vectors=False,
            limit=10000,
        )
        self.chunks = [pt.payload for pt in scroll[0]]
        print(f"[RAG] Restored {len(self.chunks)} chunks from {col}")

    def restore_if_exists(self, hash_str: str) -> bool:
        """Check if a collection exists for the given hash and restore it.
        Returns True if restored, False if not found."""
        col = _collection_name(hash_str)
        if self.client.collection_exists(col):
            self._restore_from_collection(col)
            self.paper_hash = hash_str
            self._save_hash()
            print(f"[RAG] Restored existing collection for hash {hash_str[:12]}...")
            return True
        return False

    def _current_collection(self) -> Optional[str]:
        if self.paper_hash:
            return _collection_name(self.paper_hash)
        return None

    def add_chunks(self, paper_index: int, chunks: list[str], metadata: dict | None = None):
        for i, text in enumerate(chunks):
            self.chunks.append({
                "paper_index": paper_index,
                "chunk_index": i,
                "text": text,
                **(metadata or {}),
            })
        self._built = False

    def clear(self):
        self.chunks.clear()
        self._vocab = None
        self._vectors = None
        self._built = False
        self.paper_hash = None
        self._save_hash()
        print("[RAG] In-memory state cleared (disk data preserved)")

    def set_paper_hash(self, hash_str: str):
        self.paper_hash = hash_str
        self._save_hash()

    def __len__(self) -> int:
        return len(self.chunks)

    # ---- TF-IDF helpers ----

    def _build_tfidf(self):
        n = len(self.chunks)
        if n == 0:
            return

        col = self._current_collection()
        if not col:
            print("[TF-IDF] No collection name (no paper_hash)")
            return

        self._vocab = None
        self._vectors = None
        self._built = False

        all_tokens = set()
        tokenized = []
        for chunk in self.chunks:
            tokens = _tokenize(chunk["text"])
            tokenized.append(tokens)
            all_tokens.update(tokens)

        df = Counter()
        for tokens in tokenized:
            df.update(set(tokens))

        vocab_list = sorted(t for t, f in df.items() if f >= 1)[:MAX_DIM]
        dim = len(vocab_list)

        if dim == 0:
            print(f"[TF-IDF] Empty vocab! all_tokens={len(all_tokens)} chunks={n}")
            return

        self._vocab = {t: i for i, t in enumerate(vocab_list)}

        idf = np.zeros(dim)
        for t, i in self._vocab.items():
            idf[i] = math.log10((n + 1) / (df[t] + 1)) + 1

        vectors = np.zeros((n, dim), dtype=np.float32)
        for i, tokens in enumerate(tokenized):
            tf = Counter(tokens)
            for t, count in tf.items():
                j = self._vocab.get(t)
                if j is not None:
                    vectors[i, j] = (1 + math.log10(count)) * idf[j]

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vectors = vectors / norms

        self._vectors = vectors

        if self.client.collection_exists(col):
            self.client.delete_collection(col)
        self.client.create_collection(
            collection_name=col,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        points = [
            PointStruct(id=i, vector=v.tolist(), payload=self.chunks[i])
            for i, v in enumerate(vectors)
        ]
        self.client.upsert(collection_name=col, points=points)
        self._built = True
        print(f"[TF-IDF] Built: dim={dim}, chunks={n} in '{col}'")

    def _search_tfidf(self, query: str, top_k: int, min_score: float) -> list[dict]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        col = self._current_collection()
        if not col:
            return []

        dim = len(self._vocab)
        qv = np.zeros(dim, dtype=np.float32)
        q_tf = Counter(query_tokens)
        matched = 0
        for t, count in q_tf.items():
            j = self._vocab.get(t)
            if j is not None:
                qv[j] = 1 + math.log10(count)
                matched += 1

        q_norm = np.linalg.norm(qv)
        if q_norm > 0:
            qv = qv / q_norm

        results = self.client.query_points(
            collection_name=col,
            query=qv.tolist(),
            limit=top_k,
        )
        filtered = [r for r in results.points if r.score >= min_score]
        if len(filtered) == 0 and len(results.points) > 0:
            scores = [round(r.score, 4) for r in results.points]
            print(f"[TF-IDF] vocab={dim} query_matched={matched}/{len(q_tf)} top_scores={scores}")
        return [r.payload for r in filtered]

    # ---- FastEmbed helpers ----

    def _try_init_fastembed(self):
        try:
            from fastembed import TextEmbedding
            self._embed_model = TextEmbedding()
            self._use_fastembed = True
            print("[RAG] Using FastEmbed for embeddings")
        except Exception as e:
            print(f"[RAG] FastEmbed unavailable ({e}), falling back to TF-IDF")

    def _build_fastembed(self):
        n = len(self.chunks)
        if n == 0:
            return

        col = self._current_collection()
        if not col:
            return

        self._built = False

        texts = [c["text"] for c in self.chunks]
        embeddings = list(self._embed_model.embed(texts))
        dim = len(embeddings[0])

        if self.client.collection_exists(col):
            self.client.delete_collection(col)
        self.client.create_collection(
            collection_name=col,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        points = [
            PointStruct(id=i, vector=v.tolist(), payload=self.chunks[i])
            for i, v in enumerate(embeddings)
        ]
        self.client.upsert(collection_name=col, points=points)
        self._built = True
        print(f"[FastEmbed] Built: dim={dim}, chunks={n} in '{col}'")

    def _search_fastembed(self, query: str, top_k: int, min_score: float) -> list[dict]:
        col = self._current_collection()
        if not col:
            return []

        query_vec = list(self._embed_model.embed([query]))[0]
        results = self.client.query_points(
            collection_name=col,
            query=query_vec.tolist(),
            limit=top_k,
        )
        filtered = [r for r in results.points if r.score >= min_score]
        return [r.payload for r in filtered]

    # ---- Public API ----

    def _build_embeddings(self):
        if self._use_fastembed:
            self._build_fastembed()
        else:
            self._build_tfidf()

    def search(self, query: str, top_k: int = 10, min_score: float = 0.2) -> list[dict[str, Any]]:
        trigger_rebuild = (
            not self.chunks
            or (self._use_fastembed and not self._built)
            or (not self._use_fastembed and self._vocab is None)
        )
        if trigger_rebuild:
            try:
                self._build_embeddings()
            except Exception as e:
                print(f"[RAG] Build failed: {e}")
                return []

        if not self._built:
            mode = "FastEmbed" if self._use_fastembed else "TF-IDF"
            print(f"[RAG] {mode} not built (chunks={len(self.chunks)})")
            return []

        if self._use_fastembed:
            return self._search_fastembed(query, top_k, min_score)
        return self._search_tfidf(query, top_k, min_score)

    def format_context(self, results: list[dict], papers: list) -> str:
        if not results:
            return ""
        parts = []
        seen_idx = set()
        for r in results:
            pi = r["paper_index"]
            if pi in seen_idx:
                continue
            seen_idx.add(pi)
            p = papers[pi]
            title = getattr(p, "title", "") or p.get("title", "")
            authors = getattr(p, "authors", []) or p.get("authors", [])
            year = getattr(p, "year", "") or p.get("year", "")
            author_str = authors[0] if authors else "Unknown"
            header = f"[{pi + 1}] {author_str} ({year}). {title}."
            parts.append(f"{header}\n{r['text']}")
        return "\n\n---\n\n".join(parts)


store = ChunkStore()
