"""SRT / VTT rendering + timestamp helpers. Ported verbatim-ish from v1
``app/formatters.py`` and adapted to Segment objects.
"""
from __future__ import annotations

from ..models import Segment


def format_hhmmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _parts(seconds: float) -> tuple[int, int, int, int]:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def srt_timestamp(seconds: float) -> str:
    h, m, s, ms = _parts(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_timestamp(seconds: float) -> str:
    h, m, s, ms = _parts(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _cue_text(seg: Segment) -> str:
    body = seg.text.strip()
    if seg.speaker:
        return f"<v {seg.speaker}>{body}"
    return body


def to_srt(segments: list[Segment]) -> str:
    lines: list[str] = []
    for idx, seg in enumerate(segments, 1):
        lines.append(str(idx))
        lines.append(f"{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}")
        lines.append(_cue_text(seg))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def to_vtt(segments: list[Segment]) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{vtt_timestamp(seg.start)} --> {vtt_timestamp(seg.end)}")
        lines.append(_cue_text(seg))
        lines.append("")
    return "\n".join(lines).strip() + "\n"
