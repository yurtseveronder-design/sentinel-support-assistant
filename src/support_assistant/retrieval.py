"""Dependency-free BM25 retrieval over markdown sections."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_WORD = re.compile(r"[a-z0-9£.]+")
_STOP = set("a an the of to is are was were be for and or in on at by with it this that as from do does can i we you my our what how when who which if not no".split())


def tokenize(text: str) -> list[str]:
    words = [w.strip(".") for w in _WORD.findall(text.lower())]
    return [w[:6] if w.isalpha() else w for w in words if w and w not in _STOP]  # crude stemmer: first 6 letters


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    source: str  # relative file path
    heading: str
    text: str
    kind: str  # "handbook" or "ticket"


def load_chunks(root: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for kind in ("handbook", "tickets"):
        for path in sorted((root / kind).glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            m = re.search(r"^Doc ID:\s*(\S+)", raw, re.M)
            doc_id = m.group(1) if m else path.stem
            parts = re.split(r"^## ", raw, flags=re.M)
            for part in parts[1:]:
                heading, _, body = part.partition("\n")
                body = body.strip()
                if body:
                    chunks.append(Chunk(doc_id, f"{kind}/{path.name}", heading.strip(), body, "ticket" if kind == "tickets" else "handbook"))
    return chunks


class Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [tokenize(c.doc_id + " " + c.heading + " " + c.text) for c in chunks]
        self.avg = sum(len(d) for d in self.docs) / max(len(self.docs), 1)
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def coverage(self, query: str, chunk: "Chunk") -> float:
        """Share of query terms that appear in the chunk (used to decide when to abstain)."""
        q = set(tokenize(query))
        d = set(tokenize(chunk.doc_id + " " + chunk.heading + " " + chunk.text))
        return len(q & d) / len(q) if q else 0.0

    def search(self, query: str, k: int = 4) -> list[tuple[float, Chunk]]:
        q = tokenize(query)
        scored = []
        for chunk, doc in zip(self.chunks, self.docs):
            score = 0.0
            for t in q:
                tf = doc.count(t)
                if tf:
                    score += self.idf.get(t, 0) * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * len(doc) / self.avg))
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]
