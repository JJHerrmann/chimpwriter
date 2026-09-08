"""Citations. v1 did APA7 only; academia isn't all APA, so MLA 9 and Chicago
(notes-bibliography) are here too, plus BibTeX for Zotero import.

Local-file author/title still falls back to parsing ``"Author - Title"`` from the
filename (from v1 ``parse_local_author_title``) - but that's a last resort; the
CLI can pass ``--author``/``--title`` and they land in ``SourceMeta``.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..models import SourceMeta

_STYLES = ("apa", "mla", "chicago")


def parse_local_author_title(path: str) -> tuple[str, str]:
    stem = Path(path).stem
    for sep in (" - ", " – ", " — ", "_"):
        if sep in stem:
            parts = [p.strip() for p in stem.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], " ".join(parts[1:])
    return "Unknown speaker", stem


def _media_kind(path: str) -> str:
    ext = Path(path).suffix.lower()
    return "Video" if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"} else "Audio"


def _long_date(meta: SourceMeta) -> str:
    if meta.date and len(meta.date) == 8:
        try:
            dt = datetime.strptime(meta.date, "%Y%m%d")
            return f"{dt.year}, {dt:%B} {dt.day}"
        except ValueError:
            pass
    return "n.d."


def _year(meta: SourceMeta) -> str:
    return meta.year if meta.year and meta.year != "" else "n.d."


def _title(meta: SourceMeta) -> str:
    return " ".join((meta.title or "Untitled").split())


def apa7(meta: SourceMeta) -> str:
    author = meta.author or "Unknown uploader"
    if meta.kind == "youtube":
        return f"{author}. ({_long_date(meta)}). {_title(meta)} [Video]. YouTube. {meta.url}"
    author = meta.author or parse_local_author_title(meta.path)[0]
    accessed = datetime.now().strftime("%Y-%m-%d")
    return f"{author}. (n.d.). {_title(meta)} [{_media_kind(meta.path)} file]. Personal collection. Accessed {accessed}."


def mla9(meta: SourceMeta) -> str:
    title = f'"{_title(meta)}."'
    if meta.kind == "youtube":
        author = meta.author or "Unknown uploader"
        date = ""
        if meta.date and len(meta.date) == 8:
            try:
                dt = datetime.strptime(meta.date, "%Y%m%d")
                date = f"{dt.day} {dt:%b %Y}"  # no %-d: that flag is not portable to Windows
            except ValueError:
                date = ""
        tail = f" {date}," if date else ""
        return f"{author}. {title} YouTube,{tail} {meta.url}."
    author = meta.author or parse_local_author_title(meta.path)[0]
    return f"{author}. {title} {datetime.now().year}. {_media_kind(meta.path)} recording, personal collection."


def chicago(meta: SourceMeta) -> str:
    if meta.kind == "youtube":
        author = meta.author or "Unknown uploader"
        y = _year(meta)
        return f'{author}. {y}. "{_title(meta)}." YouTube video. {meta.url}.'
    author = meta.author or parse_local_author_title(meta.path)[0]
    return f'{author}. n.d. "{_title(meta)}." {_media_kind(meta.path)} recording. Personal collection.'


def reference(meta: SourceMeta, style: str = "apa") -> str:
    return {"apa": apa7, "mla": mla9, "chicago": chicago}.get(style, apa7)(meta)


def in_text(meta: SourceMeta, style: str = "apa") -> str:
    author = meta.author or (parse_local_author_title(meta.path)[0] if meta.path else "Unknown")
    if style == "apa":
        y = _year(meta)
        return f"Parenthetical: ({author}, {y})\nNarrative: {author} ({y})"
    if style == "mla":
        return f"Parenthetical: ({author})\nNarrative: {author}"
    y = _year(meta)
    return f"Note: {author} ({y}).\nShort note: {author}."


def bibtex(meta: SourceMeta) -> str:
    key = re.sub(r"[^a-z0-9]", "", (meta.author or meta.display_name()).lower())[:20] or "source"
    key += _year(meta).replace("n.d.", "nd")
    fields = {
        "title": _title(meta),
        "author": meta.author or "Unknown",
        "year": _year(meta).replace("n.d.", ""),
        "howpublished": meta.url or "personal collection",
        "note": "YouTube video" if meta.kind == "youtube" else "Audio/video recording",
    }
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items() if v)
    return f"@misc{{{key},\n{body}\n}}\n"


def render_all(meta: SourceMeta, style: str = "apa") -> dict[str, str]:
    return {
        "reference": reference(meta, style),
        "in_text": in_text(meta, style),
        "bibtex": bibtex(meta),
    }
