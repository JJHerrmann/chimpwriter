"""Turn a Transcript into the on-disk research packet.

Replaces the ~90-line inline write block in v1 ``run_job``. Key change:
``transcript.json`` is always written first as the source of truth, and every
other file is a render of it - so ``chimpworks render transcript.json`` can
regenerate or add formats later without re-transcribing.

Layout (unchanged from v1): ``<root>/Research/<Topic>/<Source name>/``
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..log import get_logger
from ..models import Transcript
from . import citation as cite
from .article import article
from .digest import get_digest
from .subtitles import to_srt, to_vtt
from .text import clean_transcript, joined_text, speaker_transcript

log = get_logger(__name__)

# formats that are always safe to emit; "json" is implicit and always written
KNOWN_FORMATS = {"txt", "srt", "vtt", "article", "summary", "quotes", "json"}


@dataclass
class PacketOptions:
    topic: str = "General"
    formats: list[str] = field(default_factory=lambda: ["txt", "srt", "vtt", "json"])
    make_article: bool = False
    make_citation: bool = True
    citation_style: str = "apa"
    digest: str = "heuristic"


def safe_name(value: str, fallback: str = "source") -> str:
    text = re.sub(r'[<>:"/\\|?*]+', " ", value or "")
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:80] or fallback)


def packet_dir(root: str | Path, topic: str, source_name: str) -> Path:
    return Path(root) / "Research" / safe_name(topic, "General") / safe_name(source_name, "Source")


def write_packet(transcript: Transcript, root: str | Path, opts: PacketOptions) -> list[Path]:
    formats = set(opts.formats) | {"json"}
    unknown = formats - KNOWN_FORMATS
    if unknown:
        log.warning("ignoring unknown formats: %s", ", ".join(sorted(unknown)))
    formats &= KNOWN_FORMATS

    name = transcript.meta.display_name()
    out_dir = packet_dir(root, opts.topic, name)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = safe_name(name, "source")
    written: list[Path] = []

    def emit(suffix: str, content: str) -> None:
        path = out_dir / f"{base}{suffix}"
        path.write_text(content, encoding="utf-8")
        written.append(path)

    # 1. source of truth
    tj = out_dir / f"{base}.transcript.json"
    transcript.save(tj)
    written.append(tj)

    # 2. plain renders
    if "txt" in formats:
        if transcript.has_speakers():
            emit("_transcript_speakers.txt", speaker_transcript(transcript))
        emit("_transcript_clean.txt", clean_transcript(transcript))
    if "srt" in formats:
        emit("_transcript.srt", to_srt(transcript.segments))
    if "vtt" in formats:
        emit("_transcript.vtt", to_vtt(transcript.segments))
    if opts.make_article or "article" in formats:
        emit("_article.txt", article(transcript.segments))

    # 3. digest
    digest = get_digest(opts.digest)
    if digest.name != "off":
        bullets = digest.summary(transcript, count=5)
        if bullets:
            emit("_summary.txt", "".join(f"- {b}\n" for b in bullets))
        quotes = digest.highlights(transcript, count=3)
        if quotes:
            emit(
                "_quotes.txt",
                "".join(f"- {q.timecode()} {q.text}\n" for q in quotes),
            )

    # 4. citations
    if opts.make_citation:
        parts = cite.render_all(transcript.meta, opts.citation_style)
        emit(f"_citation_{opts.citation_style}.txt", parts["reference"].strip() + "\n")
        emit("_citation_intext.txt", parts["in_text"].strip() + "\n")
        emit("_citation.bib", parts["bibtex"])

    return written
