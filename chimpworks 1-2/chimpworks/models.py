"""The canonical artifact.

Everything the pipeline produces is a ``Transcript``; every rendered file (SRT,
VTT, clean text, article, citations) is a *view* of one. Persisting it as
``transcript.json`` means re-rendering, re-summarising or re-citing never needs
another pass over the audio.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "chimpworks/transcript@1"


@dataclass
class Word:
    start: float
    end: float
    word: str
    probability: float | None = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    speaker: str | None = None

    def clean_text(self) -> str:
        return " ".join(self.text.split())


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass
class SourceMeta:
    kind: str = "file"          # "youtube" | "file"
    url: str = ""
    path: str = ""
    title: str = ""
    author: str = ""            # uploader / channel / speaker
    date: str = ""              # YYYYMMDD when known
    year: str = "n.d."
    duration: float | None = None
    video_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def display_name(self) -> str:
        return self.title or Path(self.path).stem or self.video_id or "source"


@dataclass
class Transcript:
    meta: SourceMeta
    language: str = ""
    model: str = ""
    segments: list[Segment] = field(default_factory=list)
    speakers: list[SpeakerTurn] = field(default_factory=list)
    created_utc: int = field(default_factory=lambda: int(time.time()))
    schema: str = SCHEMA

    # --- convenience ----------------------------------------------------
    def text(self) -> str:
        return " ".join(s.clean_text() for s in self.segments if s.text.strip()).strip()

    def duration(self) -> float:
        if self.meta.duration:
            return float(self.meta.duration)
        return self.segments[-1].end if self.segments else 0.0

    def has_speakers(self) -> bool:
        return any(s.speaker for s in self.segments)

    def word_count(self) -> int:
        return sum(len(s.clean_text().split()) for s in self.segments)

    # --- serialisation ------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transcript":
        meta = SourceMeta(**{k: v for k, v in (data.get("meta") or {}).items()
                             if k in SourceMeta.__dataclass_fields__})
        segments = []
        for raw in data.get("segments") or []:
            words = [Word(**{k: v for k, v in w.items() if k in Word.__dataclass_fields__})
                     for w in raw.get("words") or []]
            segments.append(Segment(
                start=float(raw["start"]), end=float(raw["end"]), text=raw.get("text", ""),
                words=words, speaker=raw.get("speaker"),
            ))
        speakers = [SpeakerTurn(**{k: v for k, v in t.items() if k in SpeakerTurn.__dataclass_fields__})
                    for t in data.get("speakers") or []]
        return cls(
            meta=meta,
            language=data.get("language", ""),
            model=data.get("model", ""),
            segments=segments,
            speakers=speakers,
            created_utc=int(data.get("created_utc") or time.time()),
            schema=data.get("schema", SCHEMA),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Transcript":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
