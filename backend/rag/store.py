import re
import math
import numpy as np
from collections import Counter
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


COLLECTION_NAME = "papers"
MAX_DIM = 50000


class ChunkStore:
    def __init__(self):
        self.client = QdrantClient(":memory:")
        self.chunks: list[dict[str, Any]] = []
        self._built = False
        self.paper_hash: str | None = None
        self._generation_count = 0

        self._embed_model = None
        self._use_fastembed = False

        # TF-IDF state (only used when FastEmbed unavailable)
        self._vocab: dict[str, int] | None = None
        self._vectors: np.ndarray | None = None

        self._try_init_fastembed()

    def _try_init_fastembed(self):
        try:
            from fastembed import TextEmbedding
            self._embed_model = TextEmbedding()
            self._use_fastembed = True
            print("[RAG] Using FastEmbed for embeddings")
        except Exception as e:
            print(f"[RAG] FastEmbed unavailable ({e}), falling back to TF-IDF")

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
        self.client.delete_collection(COLLECTION_NAME)
        self.chunks.clear()
        self._vocab = None
        self._vectors = None
        self._built = False
        self.paper_hash = None

    def __len__(self) -> int:
        return len(self.chunks)

    # ---- TF-IDF helpers ----

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _build_tfidf(self):
        n = len(self.chunks)
        if n == 0:
            return

        self._vocab = None
        self._vectors = None
        self._built = False

        all_tokens = set()
        tokenized = []
        for chunk in self.chunks:
            tokens = self._tokenize(chunk["text"])
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

        if self.client.collection_exists(COLLECTION_NAME):
            self.client.delete_collection(COLLECTION_NAME)
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        points = [
            PointStruct(id=i, vector=v.tolist(), payload=self.chunks[i])
            for i, v in enumerate(vectors)
        ]
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        self._built = True
        print(f"[TF-IDF] Built: dim={dim}, chunks={n}")

    def _search_tfidf(self, query: str, top_k: int, min_score: float) -> list[dict]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
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
            collection_name=COLLECTION_NAME,
            query=qv.tolist(),
            limit=top_k,
        )
        filtered = [r for r in results.points if r.score >= min_score]
        if len(filtered) == 0 and len(results.points) > 0:
            scores = [round(r.score, 4) for r in results.points]
            print(f"[TF-IDF] vocab={dim} query_matched={matched}/{len(q_tf)} top_scores={scores}")
        return [r.payload for r in filtered]

    # ---- FastEmbed helpers ----

    def _build_fastembed(self):
        n = len(self.chunks)
        if n == 0:
            return

        self._built = False

        texts = [c["text"] for c in self.chunks]
        embeddings = list(self._embed_model.embed(texts))
        dim = len(embeddings[0])

        if self.client.collection_exists(COLLECTION_NAME):
            self.client.delete_collection(COLLECTION_NAME)
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        points = [
            PointStruct(id=i, vector=v.tolist(), payload=self.chunks[i])
            for i, v in enumerate(embeddings)
        ]
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        self._built = True
        print(f"[FastEmbed] Built: dim={dim}, chunks={n}")

    def _search_fastembed(self, query: str, top_k: int, min_score: float) -> list[dict]:
        query_vec = list(self._embed_model.embed([query]))[0]
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
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
