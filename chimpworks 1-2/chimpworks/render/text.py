"""Plain-text renders: joined text, paragraphized transcript, speaker-labelled.

Ported from v1 ``app/formatters.py`` (``segments_to_text``, ``paragraphize_*``)
and ``app/transcribe.py`` (``_labeled_transcript``).
"""
from __future__ import annotations

import re

from ..models import Segment, Transcript

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def joined_text(segments: list[Segment]) -> str:
    return _norm(" ".join(s.text.strip() for s in segments if s.text.strip()))


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(_norm(text)) if s.strip()]


def paragraphize(text: str, *, per_paragraph: int = 4) -> str:
    sents = sentences(text)
    if not sents:
        return ""
    paras, buf = [], []
    for sent in sents:
        buf.append(sent)
        if len(buf) >= per_paragraph:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)


def clean_transcript(transcript: Transcript) -> str:
    return paragraphize(joined_text(transcript.segments)) + "\n"


def speaker_transcript(transcript: Transcript) -> str:
    """One block per speaker turn; consecutive same-speaker segments merged."""
    lines: list[str] = []
    current: str | None = None
    buf: list[str] = []
    for seg in transcript.segments:
        text = _norm(seg.text)
        if not text:
            continue
        speaker = seg.speaker or "Speaker ?"
        if current is None:
            current = speaker
        if speaker != current and buf:
            lines.append(f"{current}: " + " ".join(buf))
            lines.append("")
            buf, current = [], speaker
        buf.append(text)
    if buf and current:
        lines.append(f"{current}: " + " ".join(buf))
    return "\n".join(lines).strip() + "\n"
