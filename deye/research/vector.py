"""A small, local, dependency-free vector index.

Stores embedding vectors alongside a payload (an evidence row) and answers
top-k nearest-neighbour queries by exact cosine similarity. Exact (brute-force)
search, not an approximate index: at local evidence scale this is fast, simple,
and gives correct nearest neighbours with zero external dependencies.

It persists to a plain JSON file so an index can be rebuilt offline and shared
across runs. Heavier FOSS vector stores (sqlite-vec, hnswlib, faiss-cpu) can be
dropped in behind the same ``add`` / ``search`` shape as an optional extra; the
default here needs nothing but the standard library.

Public surface:
    VectorIndex(dim)
        .add(key, vector, payload)
        .add_row(embedder, row, *, text_fields=(...))
        .build(embedder, rows)              -> self
        .search(query_vector, k=5)          -> [(score, payload)]
        .search_text(embedder, query, k=5)  -> [(score, payload)]
        .save(path) / VectorIndex.load(path)
        len(index)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from deye.research.embeddings import Embedder, cosine


@dataclass
class _Entry:
    key: str
    vector: list[float]
    payload: dict


@dataclass
class VectorIndex:
    dim: int
    entries: list[_Entry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, key: str, vector: list[float], payload: dict) -> None:
        if len(vector) != self.dim:
            raise ValueError(f"vector dim {len(vector)} != index dim {self.dim}")
        self.entries.append(_Entry(key=key, vector=list(vector), payload=dict(payload)))

    def add_row(self, embedder: Embedder, row: dict, *,
                text_fields: tuple[str, ...] = ("title", "excerpt")) -> None:
        text = "\n".join(str(row.get(f, "") or "") for f in text_fields)
        key = row.get("url") or row.get("content_hash") or str(len(self.entries))
        self.add(key, embedder.embed(text), row)

    def build(self, embedder: Embedder, rows: list[dict], *,
              text_fields: tuple[str, ...] = ("title", "excerpt")) -> "VectorIndex":
        self.entries.clear()
        for row in rows:
            self.add_row(embedder, row, text_fields=text_fields)
        return self

    def search(self, query_vector: list[float], k: int = 5) -> list[tuple[float, dict]]:
        scored = [(cosine(query_vector, e.vector), e.payload) for e in self.entries]
        scored.sort(key=lambda t: -t[0])
        return scored[:k]

    def search_text(self, embedder: Embedder, query: str,
                    k: int = 5) -> list[tuple[float, dict]]:
        return self.search(embedder.embed(query), k=k)

    # -- persistence --------------------------------------------------------

    def to_dict(self) -> dict:
        return {"dim": self.dim,
                "entries": [{"key": e.key, "vector": e.vector, "payload": e.payload}
                            for e in self.entries]}

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "VectorIndex":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        idx = cls(dim=int(data["dim"]))
        for e in data.get("entries", []):
            idx.entries.append(_Entry(key=e["key"], vector=list(e["vector"]),
                                      payload=dict(e["payload"])))
        return idx
