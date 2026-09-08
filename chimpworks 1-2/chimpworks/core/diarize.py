"""Optional speaker diarization via pyannote.audio.

Lazy import + cached pipeline (v1 reloaded it every job). ``assign_speakers`` is
the same max-overlap heuristic as v1 ``_assign_speakers`` - good enough for a
v1-2 and it keeps the dependency surface small.
"""
from __future__ import annotations

from pathlib import Path

from ..log import Progress, noop_progress
from ..models import Segment, SpeakerTurn

_PIPELINE_CACHE: dict[str, object] = {}


class DiarizationUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import pyannote.audio  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def load_pipeline(model: str, hf_token: str | None = None):
    if model in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[model]
    try:
        from pyannote.audio import Pipeline
    except Exception as exc:  # noqa: BLE001
        raise DiarizationUnavailable(
            "pyannote.audio is not installed (`pip install \"chimpworks[diarize]\"`)."
        ) from exc
    if Path(model).exists():
        pipeline = Pipeline.from_pretrained(model)
    elif hf_token:
        pipeline = Pipeline.from_pretrained(model, use_auth_token=hf_token)
    else:
        pipeline = Pipeline.from_pretrained(model)
    _PIPELINE_CACHE[model] = pipeline
    return pipeline


def clear_cache() -> None:
    _PIPELINE_CACHE.clear()


def diarize(
    wav_path: str | Path,
    *,
    model: str,
    hf_token: str | None = None,
    progress: Progress = noop_progress,
) -> list[SpeakerTurn]:
    progress("diarize", None)
    pipeline = load_pipeline(model, hf_token)
    annotation = pipeline(str(wav_path))
    turns = [
        SpeakerTurn(start=float(turn.start), end=float(turn.end), speaker=str(speaker))
        for turn, _track, speaker in annotation.itertracks(yield_label=True)
    ]
    progress("diarize", 1.0)
    return turns


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    if not turns:
        return segments
    labelled: list[Segment] = []
    for seg in segments:
        best_speaker, best_overlap = None, 0.0
        for turn in turns:
            overlap = max(0.0, min(seg.end, turn.end) - max(seg.start, turn.start))
            if overlap > best_overlap:
                best_overlap, best_speaker = overlap, turn.speaker
        labelled.append(Segment(
            start=seg.start, end=seg.end, text=seg.text, words=seg.words,
            speaker=best_speaker or "Speaker ?",
        ))
    return labelled
