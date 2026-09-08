from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Optional

YOUTUBE_RE = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)[^\s]*)",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text, re.IGNORECASE)


def find_first_youtube_url(text: str) -> Optional[str]:
    match = YOUTUBE_RE.search(text)
    return match.group(1) if match else None


def _run_yt_dlp(cmd_args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["yt-dlp", *cmd_args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        # Fall back to module invocation if the executable isn't on PATH.
        mod_cmd = [sys.executable, "-m", "yt_dlp", *cmd_args]
        return subprocess.run(mod_cmd, capture_output=True, text=True)


def extract_metadata(url: str) -> dict:
    result = _run_yt_dlp(["-j", "--no-playlist", url])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp metadata failed")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return {}
    return json.loads(lines[-1])


def download_audio(url: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    template = os.path.join(out_dir, "%(id)s.%(ext)s")
    result = _run_yt_dlp(
        [
            "-f",
            "bestaudio",
            "-o",
            template,
            "--no-playlist",
            "--print",
            "after_move:filepath",
            url,
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp download failed")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    path = lines[-1] if lines else ""
    if path and os.path.exists(path):
        return path

    files = [os.path.join(out_dir, f) for f in os.listdir(out_dir)]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise RuntimeError("yt-dlp did not produce a file")
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]
