import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


COLLECTION = "past_works"
MAX_DIM = 50000
DATA_DIR = Path.home() / ".autojurnal"


class WorkRecord:
    def __init__(
        self,
        work_id: str,
        theme: str,
        content: str,
        language: str,
        mode: str,
        provider: str,
        paper_titles: list[str],
        template_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ):
        self.work_id = work_id
        self.theme = theme
        self.content = content
        self.language = language
        self.mode = mode
        self.provider = provider
        self.paper_titles = paper_titles
        self.template_id = template_id
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "work_id": self.work_id,
            "theme": self.theme,
            "content": self.content[:500],
            "language": self.language,
            "mode": self.mode,
            "provider": self.provider,
            "paper_titles": self.paper_titles,
            "template_id": self.template_id,
            "created_at": self.created_at,
        }

    def to_payload(self) -> dict:
        return {
            "work_id": self.work_id,
            "theme": self.theme,
            "content": self.content,
            "language": self.language,
            "mode": self.mode,
            "provider": self.provider,
            "paper_titles": json.dumps(self.paper_titles),
            "template_id": self.template_id or "",
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "WorkRecord":
        return cls(
            work_id=payload["work_id"],
            theme=payload["theme"],
            content=payload["content"],
            language=payload["language"],
            mode=payload["mode"],
            provider=payload["provider"],
            paper_titles=json.loads(payload.get("paper_titles", "[]")),
            template_id=payload.get("template_id") or None,
            created_at=payload.get("created_at"),
        )


class WorksStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(DATA_DIR / "qdrant"))
        self._vocab: Optional[dict[str, int]] = None
        self._vectors: Optional[np.ndarray] = None
        self._built = False
        self._ensure_collection()

    def _ensure_collection(self):
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=1, distance=Distance.COSINE),
            )
            print(f"[WorksStore] Created collection '{COLLECTION}' at {DATA_DIR / 'qdrant'}")

    # ---- TF-IDF helpers (same approach as ChunkStore) ----

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _rebuild(self):
        scroll = self.client.scroll(
            collection_name=COLLECTION,
            with_payload=True,
            with_vectors=False,
            limit=10000,
        )
        points = scroll[0]
        n = len(points)
        if n == 0:
            self._built = False
            self._vocab = None
            self._vectors = None
            return

        all_tokens: set[str] = set()
        tokenized: list[list[str]] = []
        for pt in points:
            text = (pt.payload.get("theme", "") + " " + pt.payload.get("content", ""))[:2000]
            tokens = self._tokenize(text)
            tokenized.append(tokens)
            all_tokens.update(tokens)

        df = Counter()
        for tokens in tokenized:
            df.update(set(tokens))

        vocab_list = sorted(t for t, f in df.items() if f >= 1)[:MAX_DIM]
        dim = len(vocab_list)
        if dim == 0:
            self._built = False
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

        self.client.delete_collection(COLLECTION)
        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        upsert_points = [
            PointStruct(id=i, vector=v.tolist(), payload=pt.payload)
            for i, (v, pt) in enumerate(zip(vectors, points))
        ]
        for i in range(0, len(upsert_points), 100):
            batch = upsert_points[i:i + 100]
            self.client.upsert(collection_name=COLLECTION, points=batch)
        self._built = True

    def _get_current_dim(self) -> int:
        try:
            info = self.client.get_collection(COLLECTION)
            if info and info.config and info.config.params and info.config.params.vectors:
                return info.config.params.vectors.size
        except Exception:
            pass
        return 1

    def save_work(self, work: WorkRecord):
        dim = self._get_current_dim()
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=abs(hash(work.work_id)) % (2**63),
                vector=[0.0] * dim,
                payload=work.to_payload(),
            )],
        )
        self._built = False
        print(f"[WorksStore] Saved work '{work.theme}' ({work.work_id[:8]})")

    def search_similar(self, theme: str, top_k: int = 3, min_score: float = 0.05) -> list[WorkRecord]:
        self._rebuild()
        if not self._built or self._vocab is None:
            return []

        query_tokens = self._tokenize(theme)
        if not query_tokens:
            return []

        dim = len(self._vocab)
        qv = np.zeros(dim, dtype=np.float32)
        q_tf = Counter(query_tokens)
        for t, count in q_tf.items():
            j = self._vocab.get(t)
            if j is not None:
                qv[j] = 1 + math.log10(count)

        q_norm = np.linalg.norm(qv)
        if q_norm > 0:
            qv = qv / q_norm

        results = self.client.query_points(
            collection_name=COLLECTION,
            query=qv.tolist(),
            limit=top_k,
        )
        filtered = [r for r in results.points if r.score >= min_score]
        if not filtered:
            return []

        return [WorkRecord.from_payload(r.payload) for r in filtered]

    def list_works(self, limit: int = 50, offset: int = 0) -> list[dict]:
        scroll = self.client.scroll(
            collection_name=COLLECTION,
            with_payload=True,
            with_vectors=False,
            limit=limit,
            offset=offset,
        )
        works = []
        for pt in scroll[0]:
            rec = WorkRecord.from_payload(pt.payload)
            works.append(rec.to_dict())
        works.sort(key=lambda w: w["created_at"], reverse=True)
        return works

    def delete_work(self, work_id: str) -> bool:
        scroll = self.client.scroll(
            collection_name=COLLECTION,
            with_payload=True,
            with_vectors=False,
            limit=10000,
        )
        for pt in scroll[0]:
            if pt.payload.get("work_id") == work_id:
                self.client.delete(
                    collection_name=COLLECTION,
                    points_selector=[pt.id],
                )
                self._built = False
                print(f"[WorksStore] Deleted work '{work_id[:8]}'")
                return True
        return False

    def count(self) -> int:
        return self.client.count(collection_name=COLLECTION).count


# ---- Librarian: format context for injection ----

def format_previous_works_context(works: list[WorkRecord]) -> str:
    if not works:
        return ""
    themes = "\n".join(f"  • {w.theme} ({w.mode}, {w.language}, {w.created_at[:10]})" for w in works)
    if works[0].language == "id":
        return (
            "⚠️ INSTRUKSI ORISINALITAS:\n"
            "Anda pernah menulis karya dengan tema serupa berikut:\n"
            f"{themes}\n\n"
            "PASTIKAN karya BARU ini BERBEDA SIGNIFIKAN — jangan ulang struktur, "
            "contoh, kalimat, atau argumen yang sama. Anggap ini sebagai proyek "
            "baru yang sepenuhnya terpisah.\n"
        )
    return (
        "⚠️ ORIGINALITY INSTRUCTION:\n"
        "You have previously written works on similar themes:\n"
        f"{themes}\n\n"
        "ENSURE the NEW work is SIGNIFICANTLY DIFFERENT — do not repeat the same "
        "structure, examples, sentences, or arguments. Treat this as a completely "
        "new, separate project.\n"
    )


# Shared singleton
store = WorksStore()
