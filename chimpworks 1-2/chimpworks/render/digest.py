"""Summary + highlight quotes.

v1 shipped ``summary_bullets`` ("first N long sentences") and ``quote_candidates``
("N longest segments") as if they were real features. Here the same heuristics
live behind a ``Digest`` protocol and are named honestly, so a local-LLM backend
can be dropped in later without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import Transcript
from .subtitles import format_hhmmss
from .text import joined_text, sentences


@dataclass
class Quote:
    start: float
    end: float
    text: str
    speaker: str | None = None

    def timecode(self) -> str:
        return f"[{format_hhmmss(self.start)} - {format_hhmmss(self.end)}]"


class Digest(Protocol):
    name: str

    def summary(self, transcript: Transcript, *, count: int = 5) -> list[str]: ...

    def highlights(self, transcript: Transcript, *, count: int = 3) -> list[Quote]: ...


class HeuristicDigest:
    """Length-based selection. Not a summary - a shortlist of long, dense lines."""

    name = "heuristic"

    def summary(self, transcript: Transcript, *, count: int = 5) -> list[str]:
        sents = sentences(joined_text(transcript.segments))
        picked = [s for s in sents if len(s) >= 25][:count]
        if len(picked) < count:
            picked += [s for s in sents if s not in picked][: count - len(picked)]
        return picked

    def highlights(self, transcript: Transcript, *, count: int = 3) -> list[Quote]:
        scored = sorted(
            (s for s in transcript.segments if len(s.clean_text()) >= 30),
            key=lambda s: len(s.clean_text()),
            reverse=True,
        )
        return [
            Quote(start=s.start, end=s.end, text=s.clean_text(), speaker=s.speaker)
            for s in scored[:count]
        ]


class NullDigest:
    name = "off"

    def summary(self, transcript: Transcript, *, count: int = 5) -> list[str]:  # noqa: ARG002
        return []

    def highlights(self, transcript: Transcript, *, count: int = 3) -> list[Quote]:  # noqa: ARG002
        return []


def get_digest(name: str) -> Digest:
    return {"heuristic": HeuristicDigest, "off": NullDigest}.get(name, HeuristicDigest)()
