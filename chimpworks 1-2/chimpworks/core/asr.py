"""faster-whisper wrapper.

Improvements over v1 ``_transcribe`` / ``_load_model``:
 * the model is cached across jobs (a batch of 20 lectures loads it once)
 * word-level timestamps are on by default
 * progress is reported from ``segment.end / info.duration``
faster-whisper is imported lazily so the rest of the package (and its tests)
work without it installed.
"""
from __future__ import annotations

from pathlib import Path

from ..log import Progress, noop_progress
from ..models import Segment, Word

_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


class AsrUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def load_model(model_size: str, *, device: str = "auto", compute_type: str = "auto"):
    key = (model_size, device, compute_type)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # noqa: BLE001
        raise AsrUnavailable(
            "faster-whisper is not installed (`pip install faster-whisper`)."
        ) from exc
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "cuda" in msg or "cublas" in msg or "cudnn" in msg:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
        else:
            raise
    _MODEL_CACHE[key] = model
    return model


def clear_cache() -> None:
    _MODEL_CACHE.clear()


def transcribe(
    wav_path: str | Path,
    *,
    model_size: str,
    language: str = "auto",
    word_timestamps: bool = True,
    vad_filter: bool = True,
    device: str = "auto",
    compute_type: str = "auto",
    progress: Progress = noop_progress,
) -> tuple[list[Segment], str]:
    """Return (segments, detected_language)."""
    model = load_model(model_size, device=device, compute_type=compute_type)
    lang = None if not language or language.lower() == "auto" else language
    try:
        raw_segments, info = model.transcribe(
            str(wav_path), language=lang, vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "cuda" in msg or "cublas" in msg:
            model = load_model(model_size, device="cpu", compute_type="int8")
            raw_segments, info = model.transcribe(
                str(wav_path), language=lang, vad_filter=vad_filter,
                word_timestamps=word_timestamps,
            )
        else:
            raise

    total = float(getattr(info, "duration", 0.0) or 0.0)
    detected = getattr(info, "language", "") or (lang or "")
    out: list[Segment] = []
    for seg in raw_segments:
        words = [
            Word(start=float(w.start), end=float(w.end), word=w.word,
                 probability=getattr(w, "probability", None))
            for w in (getattr(seg, "words", None) or [])
        ]
        out.append(Segment(start=float(seg.start), end=float(seg.end),
                            text=seg.text, words=words))
        if total:
            progress("transcribe", min(1.0, float(seg.end) / total))
    progress("transcribe", 1.0)
    return out, detected
