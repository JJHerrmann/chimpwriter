"""Orchestration: input string -> Transcript.

This is the piece that was ~150 lines welded inside a Qt ``QThread`` in v1
(``app/transcribe.py::run_job``). Here it is a plain function with a progress
callback; the GUI worker and the CLI both call it.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..log import Progress, get_logger, noop_progress
from ..models import SourceMeta, Transcript
from . import asr, audio, diarize as diar
from .sources import fetch_audio, probe_metadata, resolve_source

log = get_logger(__name__)


@dataclass
class TranscribeOptions:
    model: str = "small"
    language: str = "auto"
    device: str = "auto"
    compute_type: str = "auto"
    word_timestamps: bool = True
    diarize: bool = False
    diarize_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: str = ""
    cookies_from_browser: str = ""


def build_transcript(
    inp: str,
    opts: TranscribeOptions,
    *,
    workdir: str | Path | None = None,
    progress: Progress = noop_progress,
) -> Transcript:
    ctx: tempfile.TemporaryDirectory | None = None
    if workdir is None:
        ctx = tempfile.TemporaryDirectory(prefix="chimpworks-")
        workdir = ctx.name
    workdir = Path(workdir)
    try:
        progress("resolve", None)
        src: SourceMeta = resolve_source(inp)
        src = probe_metadata(src, cookies_from_browser=opts.cookies_from_browser)

        progress("fetch-audio", None)
        media = fetch_audio(src, workdir, cookies_from_browser=opts.cookies_from_browser)

        progress("decode", None)
        wav = audio.to_wav(media, workdir / "audio.wav")

        segments, language = asr.transcribe(
            wav,
            model_size=opts.model,
            language=opts.language,
            word_timestamps=opts.word_timestamps,
            device=opts.device,
            compute_type=opts.compute_type,
            progress=progress,
        )

        turns = []
        if opts.diarize:
            try:
                turns = diar.diarize(
                    wav, model=opts.diarize_model, hf_token=opts.hf_token or None,
                    progress=progress,
                )
                segments = diar.assign_speakers(segments, turns)
            except Exception as exc:  # noqa: BLE001 - diarization is best-effort
                log.warning("diarization failed: %s", exc)

        if not src.duration and segments:
            src.duration = segments[-1].end

        progress("done", 1.0)
        return Transcript(
            meta=src, language=language, model=opts.model,
            segments=segments, speakers=turns,
        )
    finally:
        if ctx is not None:
            ctx.cleanup()
