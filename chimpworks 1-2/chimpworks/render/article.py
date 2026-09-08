"""The "make it readable (no grunts)" pass.

Ported from v1 ``article_from_segments``: drop standalone filler tokens, start a
new paragraph on a pause longer than ~1.5s, otherwise every 4 sentences. This is
a cheap cleanup, not rewriting - the LLM-backed version is a later phase and
slots in behind the same call site in ``digest.py``.
"""
from __future__ import annotations

import re

from ..models import Segment

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_FILLERS = {"um", "uh", "erm", "hmm", "mm", "mmm", "uhh", "umm", "ah", "er"}
_PARA_GAP_SECONDS = 1.5
_SENTENCES_PER_PARA = 4


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _is_filler(sentence: str) -> bool:
    return re.sub(r"[^a-z]", "", sentence.lower()) in _FILLERS


def article(segments: list[Segment]) -> str:
    paragraphs: list[str] = []
    buf: list[str] = []
    count = 0
    last_end: float | None = None

    for seg in segments:
        text = _norm(seg.text)
        if not text:
            continue
        if last_end is not None and (seg.start - last_end) > _PARA_GAP_SECONDS and buf:
            paragraphs.append(" ".join(buf))
            buf, count = [], 0
        last_end = seg.end

        for sentence in (s.strip() for s in _SENTENCE_RE.split(text) if s.strip()):
            if _is_filler(sentence):
                continue
            buf.append(sentence)
            count += 1
            if count >= _SENTENCES_PER_PARA:
                paragraphs.append(" ".join(buf))
                buf, count = [], 0

    if buf:
        paragraphs.append(" ".join(buf))
    return "\n\n".join(paragraphs) + ("\n" if paragraphs else "")
