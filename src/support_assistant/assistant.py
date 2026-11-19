from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .guard import Guard, GuardUnavailable, NoGuard
from .llm import ExtractiveModel, Model
from .retrieval import Index, load_chunks

IDK = "I don't know. This is not covered in the handbook; please ask a team lead."
REFUSED = "I can't help with that request."
UNAVAILABLE = "The safety check is unavailable, so I can't answer right now."
MIN_COVERAGE = 0.3


@dataclass
class Answer:
    text: str
    status: str  # answered | abstained | blocked_input | blocked_output | guard_unavailable
    sources: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)  # doc ids dropped by the guard


class Assistant:
    def __init__(self, root: Path, guard: Guard | None = None, model: Model | None = None, min_coverage: float = MIN_COVERAGE):
        self.index = Index(load_chunks(Path(root)))
        self.guard = guard or NoGuard()
        self.model = model or ExtractiveModel()
        self.min_coverage = min_coverage

    def ask(self, question: str) -> Answer:
        try:
            ok, _ = self.guard.check_input(question)
            if not ok:
                return Answer(REFUSED, "blocked_input")
            hits = self.index.search(question, k=8)
            ids = re.findall(r"\bT-\d{4}\b", question, re.I)
            if ids:  # an explicit ticket id: that ticket first, then policy
                want = {i.upper() for i in ids}
                named = [h for h in self.index.search(" ".join(ids), k=20) if h[1].doc_id in want]
                hits = named + [h for h in hits if h[1].doc_id not in want and h[1].kind == "handbook"]
            elif not re.search(r"\bticket\b", question, re.I):
                hits = [h for h in hits if h[1].kind == "handbook"]  # tickets only when asked about
            hits = hits[:4]
            explicit = bool(ids) and bool(hits)
            quarantined, kept = [], []
            for score, chunk in hits:
                ok, _ = self.guard.scan_chunk(chunk.text)
                if ok:
                    kept.append((score, chunk))
                else:
                    quarantined.append(chunk.doc_id)
            if not kept or (not explicit and self.index.coverage(question, kept[0][1]) < self.min_coverage):
                return Answer(IDK, "abstained", quarantined=quarantined)
            ctx = [(c.doc_id, c.text) for _, c in kept]
            raw = self.model.answer(question, ctx)
            text, blocked = self.guard.redact_output(raw)
            if blocked:
                return Answer(REFUSED, "blocked_output", quarantined=quarantined)
            return Answer(text, "answered", sources=[c.doc_id for _, c in kept], quarantined=quarantined)
        except GuardUnavailable:
            return Answer(UNAVAILABLE, "guard_unavailable")
