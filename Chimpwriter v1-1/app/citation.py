from __future__ import annotations

import os
from datetime import datetime


def _parse_upload_date(upload_date: str | None) -> tuple[str, str]:
    if upload_date:
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d")
            day = dt.day
            return f"{dt.year}, {dt:%B} {day}", str(dt.year)
        except Exception:
            return "n.d.", "n.d."
    return "n.d.", "n.d."


def _clean_title(text: str) -> str:
    return " ".join(text.strip().split())


def youtube_author(meta: dict) -> str:
    return meta.get("uploader") or meta.get("channel") or "Unknown uploader"


def youtube_title(meta: dict) -> str:
    return _clean_title(meta.get("title") or "Untitled")


def youtube_date(meta: dict) -> tuple[str, str]:
    return _parse_upload_date(meta.get("upload_date"))


def parse_local_author_title(path: str) -> tuple[str, str]:
    base = os.path.basename(path)
    title = os.path.splitext(base)[0]
    for sep in (" - ", " – ", " — ", "_"):
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], " ".join(parts[1:])
    return "Unknown speaker", title


def local_media_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
        return "Video file"
    return "Audio file"


def apa7_from_youtube(meta: dict, url: str) -> str:
    author = youtube_author(meta)
    title = youtube_title(meta)
    date_str, _year = youtube_date(meta)
    return f"{author}. ({date_str}). {title} [Video]. YouTube. {url}"


def apa7_from_local_file(path: str) -> str:
    author, title = parse_local_author_title(path)
    kind = local_media_kind(path)
    accessed = datetime.now().strftime("%Y-%m-%d")
    return f"{author}. (n.d.). {title} [{kind}]. Personal file. Accessed {accessed}."


def apa7_in_text_examples(author: str, year: str) -> str:
    year_text = year if year else "n.d."
    return f"Parenthetical: ({author}, {year_text})\\nNarrative: {author} ({year_text})"
