"""Resolve an input string to a source, probe its metadata, fetch its audio.

Ported from v1 ``app/youtube.py`` with: retries + backoff around yt-dlp, an
optional ``--cookies-from-browser`` pass-through, a clearer bot-check message,
and playlist expansion for ``chimpworks batch``.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

from ..models import SourceMeta

YOUTUBE_RE = re.compile(
    r"(https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)[\w-]+|youtu\.be/[\w-]+)[^\s]*)",
    re.IGNORECASE,
)
_VIDEO_ID_RE = re.compile(r"(?:v=|be/|shorts/|live/)([\w-]{11})")

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}


class SourceError(RuntimeError):
    pass


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_RE.search(text or ""))


def first_youtube_url(text: str) -> str | None:
    m = YOUTUBE_RE.search(text or "")
    return m.group(1) if m else None


def _video_id(url: str) -> str:
    m = _VIDEO_ID_RE.search(url or "")
    return m.group(1) if m else ""


# --- yt-dlp plumbing --------------------------------------------------

def _yt_dlp(args: list[str], *, retries: int = 3) -> subprocess.CompletedProcess:
    base = ["yt-dlp"]
    last: subprocess.CompletedProcess | None = None
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run([*base, *args], capture_output=True, text=True)
        except FileNotFoundError:
            proc = subprocess.run([sys.executable, "-m", "yt_dlp", *args],
                                  capture_output=True, text=True)
        if proc.returncode == 0:
            return proc
        last = proc
        err = (proc.stderr or "").lower()
        if "sign in to confirm" in err or "not a bot" in err:
            raise SourceError(
                "YouTube is asking to confirm you're not a bot. Retry from a "
                "residential IP, or set `yt_cookies_from_browser` in config "
                "(e.g. \"firefox\") to pass --cookies-from-browser."
            )
        if attempt < retries:
            time.sleep(min(20.0, 2.0 * 2 ** (attempt - 1)) + random.uniform(0, 1))
    raise SourceError((last.stderr.strip() if last else "yt-dlp failed") or "yt-dlp failed")


def _cookie_args(cookies_from_browser: str) -> list[str]:
    return ["--cookies-from-browser", cookies_from_browser] if cookies_from_browser else []


# --- public API -----------------------------------------------------

def resolve_source(inp: str) -> SourceMeta:
    inp = inp.strip()
    if is_youtube_url(inp):
        url = first_youtube_url(inp) or inp
        return SourceMeta(kind="youtube", url=url, video_id=_video_id(url))
    p = Path(inp).expanduser()
    if not p.exists():
        raise SourceError(f"not a YouTube URL and not an existing file: {inp!r}")
    return SourceMeta(kind="file", path=str(p), title=p.stem)


def probe_metadata(src: SourceMeta, *, cookies_from_browser: str = "") -> SourceMeta:
    if src.kind != "youtube":
        # local files: filename is the only metadata we have here; author/title
        # get parsed later by the citation layer.
        if src.path:
            src.title = src.title or Path(src.path).stem
        return src
    proc = _yt_dlp(["-j", "--no-playlist", *_cookie_args(cookies_from_browser), src.url])
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    meta = json.loads(lines[-1]) if lines else {}
    src.title = " ".join((meta.get("title") or "").split()) or src.title
    src.author = meta.get("uploader") or meta.get("channel") or ""
    src.date = meta.get("upload_date") or ""
    src.year = src.date[:4] if len(src.date) >= 4 else "n.d."
    src.duration = float(meta["duration"]) if meta.get("duration") else None
    src.video_id = meta.get("id") or src.video_id
    src.extra = {k: meta.get(k) for k in ("channel_id", "webpage_url", "view_count") if meta.get(k)}
    return src


def fetch_audio(src: SourceMeta, workdir: str | Path, *, cookies_from_browser: str = "") -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if src.kind != "youtube":
        p = Path(src.path)
        if not p.exists():
            raise SourceError(f"input file not found: {p}")
        return p
    template = str(workdir / "%(id)s.%(ext)s")
    proc = _yt_dlp([
        "-f", "bestaudio", "-o", template, "--no-playlist",
        "--print", "after_move:filepath",
        *_cookie_args(cookies_from_browser), src.url,
    ])
    printed = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if printed and Path(printed[-1]).exists():
        return Path(printed[-1])
    files = sorted((f for f in workdir.iterdir() if f.is_file()),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise SourceError("yt-dlp did not produce an audio file")
    return files[0]


def expand_playlist(url: str, *, cookies_from_browser: str = "") -> list[str]:
    """Return the individual video URLs of a playlist/channel URL (order preserved)."""
    proc = _yt_dlp([
        "--flat-playlist", "--print", "%(url)s",
        *_cookie_args(cookies_from_browser), url,
    ])
    urls = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith("http")]
    return urls or [url]


def read_url_list(path: str | Path) -> list[str]:
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out
