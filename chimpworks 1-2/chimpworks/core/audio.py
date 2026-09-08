"""ffmpeg wrangling: locate the binary, decode anything to 16 kHz mono WAV.

v1 assumed ``ffmpeg`` was on PATH and failed opaquely otherwise. Here we look on
PATH, then fall back to the ``imageio-ffmpeg`` wheel if it happens to be
installed, and otherwise raise a message that says exactly what to do.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FfmpegMissing(RuntimeError):
    pass


class FfmpegError(RuntimeError):
    pass


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass
    raise FfmpegMissing(
        "ffmpeg was not found. Install it (e.g. `sudo pacman -S ffmpeg`, "
        "`brew install ffmpeg`, or winget) and make sure it is on PATH, "
        "or `pip install imageio-ffmpeg`."
    )


def to_wav(src: str | Path, dst: str | Path, *, sample_rate: int = 16000) -> Path:
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(), "-hide_banner", "-y", "-i", str(src),
        "-vn", "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FfmpegError(proc.stderr.strip() or "ffmpeg failed")
    return dst


def available() -> bool:
    try:
        ffmpeg_path()
        return True
    except FfmpegMissing:
        return False
