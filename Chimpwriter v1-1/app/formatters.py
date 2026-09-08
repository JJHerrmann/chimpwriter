from __future__ import annotations

import re

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
FILLERS = {"um", "uh", "erm", "hmm", "mm", "mmm"}


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def segments_to_text(segments: list[dict]) -> str:
    text = " ".join(seg["text"].strip() for seg in segments if seg.get("text"))
    return _normalize_space(text)


def sentences_from_text(text: str) -> list[str]:
    text = _normalize_space(text)
    return [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]


def paragraphize_text(text: str, target_sentences: int = 4) -> str:
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return ""
    paragraphs = []
    buf = []
    for sentence in sentences:
        buf.append(sentence)
        if len(buf) >= target_sentences:
            paragraphs.append(" ".join(buf))
            buf = []
    if buf:
        paragraphs.append(" ".join(buf))
    return "\n\n".join(paragraphs)


def paragraphize_segments(segments: list[dict]) -> str:
    return paragraphize_text(segments_to_text(segments))


def _is_filler(sentence: str) -> bool:
    cleaned = re.sub(r"[^a-zA-Z]", "", sentence).lower()
    return cleaned in FILLERS


def article_from_segments(segments: list[dict]) -> str:
    paragraphs = []
    buf = []
    sentence_count = 0
    last_end = None
    for seg in segments:
        text = _normalize_space(seg.get("text", ""))
        if not text:
            continue
        if last_end is not None and seg.get("start") is not None:
            gap = max(0.0, float(seg["start"]) - float(last_end))
            if gap > 1.5 and buf:
                paragraphs.append(" ".join(buf))
                buf = []
                sentence_count = 0
        last_end = seg.get("end")

        sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
        for sentence in sentences:
            if _is_filler(sentence):
                continue
            buf.append(sentence)
            sentence_count += 1
            if sentence_count >= 4:
                paragraphs.append(" ".join(buf))
                buf = []
                sentence_count = 0

    if buf:
        paragraphs.append(" ".join(buf))

    return "\n\n".join(paragraphs)


def summary_bullets(text: str, count: int = 5) -> list[str]:
    sentences = sentences_from_text(text)
    bullets = []
    for sentence in sentences:
        if len(sentence) < 25:
            continue
        bullets.append(sentence)
        if len(bullets) >= count:
            return bullets
    for sentence in sentences:
        if sentence not in bullets:
            bullets.append(sentence)
        if len(bullets) >= count:
            break
    return bullets


def quote_candidates(segments: list[dict], count: int = 3) -> list[dict]:
    scored = []
    for seg in segments:
        text = _normalize_space(seg.get("text", ""))
        if len(text) < 30:
            continue
        scored.append((len(text), seg))
    scored.sort(key=lambda item: item[0], reverse=True)
    picks = []
    for _score, seg in scored[:count]:
        picks.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": _normalize_space(seg["text"]),
            }
        )
    return picks


def format_hhmmss(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours = ms // 3600000
    ms -= hours * 3600000
    minutes = ms // 60000
    ms -= minutes * 60000
    secs = ms // 1000
    ms -= secs * 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours = ms // 3600000
    ms -= hours * 3600000
    minutes = ms // 60000
    ms -= minutes * 60000
    secs = ms // 1000
    ms -= secs * 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    lines = []
    for idx, seg in enumerate(segments, 1):
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(seg['start'])} --> {_format_srt_timestamp(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{_format_vtt_timestamp(seg['start'])} --> {_format_vtt_timestamp(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"
