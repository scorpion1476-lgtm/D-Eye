"""Keyless, local, deterministic text embeddings - the FOSS default.

D-Eye's semantic layer must work with no API key, no account, and no network,
so the *default* embedder here is a dependency-free hashing embedding computed
entirely with the standard library:

  * the text is lowercased and split into word unigrams AND character 3-grams,
    so morphological variants ("airline" / "airlines" / "airfare") share many
    features even though an exact keyword index would treat them as unrelated;
  * every feature is hashed (BLAKE2b) into a fixed-width vector with a signed
    bucket - the well-known "feature hashing" / hashing-trick embedding used by
    scikit-learn's HashingVectorizer and many FOSS retrieval stacks;
  * term frequencies are dampened (sqrt) and the vector is L2-normalised, so a
    dot product between two vectors is their cosine similarity.

This is honestly a *lexical-semantic* embedding: it captures subword overlap,
word order insensitivity, and partial-match recall beyond an exact keyword
index. It does NOT model pure synonyms; a true neural model that does is an
OPTIONAL extra (``deye[embeddings]``) plugged in behind the same ``Embedder``
interface and is never required for the core to run.

Public surface:
    Embedder                      - protocol: dim + embed(text) -> list[float]
    HashingEmbedder(dim=512)      - the keyless default
    default_embedder()            - returns the configured default (hashing)
    load_embedder(name="hashing") - factory; "neural" needs the optional extra
    cosine(a, b)                  - cosine similarity of two vectors
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

_WORD = re.compile(r"[a-z0-9]+")


@runtime_checkable
class Embedder(Protocol):
    """Anything that turns text into a fixed-length, L2-normalised vector."""

    dim: int

    def embed(self, text: str) -> list[float]: ...


def _features(text: str) -> list[str]:
    """Word unigrams plus intra-word character 3-grams.

    The char 3-grams are what give the embedding subword/morphological recall:
    "airline" and "airlines" share the 3-grams air/irl/rli/lin/ine.
    """
    low = (text or "").lower()
    words = _WORD.findall(low)
    feats: list[str] = list(words)
    for w in words:
        if len(w) <= 3:
            feats.append("#" + w)
            continue
        padded = "^" + w + "$"
        for i in range(len(padded) - 2):
            feats.append("#" + padded[i:i + 3])
    return feats


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    """Map a feature to a (bucket_index, sign) pair, deterministically.

    Uses BLAKE2b rather than the built-in hash() so results are stable across
    processes and Python's hash randomisation does not perturb them.
    """
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    n = int.from_bytes(digest, "big")
    idx = n % dim
    sign = 1.0 if (n >> 63) & 1 else -1.0
    return idx, sign


class HashingEmbedder:
    """Deterministic, keyless hashing embedding (the FOSS default)."""

    name = "hashing"

    def __init__(self, dim: int = 512):
        if dim < 8:
            raise ValueError("dim must be >= 8")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        counts: dict[str, int] = {}
        for feat in _features(text):
            counts[feat] = counts.get(feat, 0) + 1
        for feat, c in counts.items():
            idx, sign = _bucket(feat, self.dim)
            vec[idx] += sign * math.sqrt(c)   # sqrt damping of term frequency
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Inputs need not be pre-normalised."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def default_embedder() -> Embedder:
    return HashingEmbedder()


def load_embedder(name: str = "hashing", *, dim: int = 512) -> Embedder:
    """Return an embedder by name.

    "hashing" (default) is keyless and stdlib-only. "neural" requires the
    optional ``deye[embeddings]`` extra; it is never imported unless asked for,
    so the core stays keyless and offline.
    """
    if name in ("", "hashing", "default"):
        return HashingEmbedder(dim=dim)
    if name in ("neural", "sentence-transformers", "fastembed"):
        try:
            from deye.research.neural_embeddings import NeuralEmbedder
        except Exception as exc:  # noqa: BLE001 - optional extra not installed
            raise RuntimeError(
                "neural embeddings need the optional extra: "
                "pip install 'deye[embeddings]'"
            ) from exc
        return NeuralEmbedder()
    raise ValueError(f"unknown embedder: {name!r}")
