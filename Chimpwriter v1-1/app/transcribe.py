from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass

from PySide6 import QtCore

from app.citation import (
    apa7_from_local_file,
    apa7_from_youtube,
    apa7_in_text_examples,
    parse_local_author_title,
    youtube_author,
    youtube_date,
    youtube_title,
)
from app.formatters import (
    article_from_segments,
    format_hhmmss,
    paragraphize_segments,
    quote_candidates,
    segments_to_text,
    segments_to_srt,
    segments_to_vtt,
    summary_bullets,
)
from app.youtube import download_audio, extract_metadata


class CancelledError(Exception):
    pass


@dataclass
class JobConfig:
    input_path: str
    youtube_url: str
    output_dir: str
    topic: str
    model_size: str
    language: str
    make_article: bool
    make_citation: bool
    diarize_enabled: bool
    diarize_model: str
    hf_token: str


class TranscriptionWorker(QtCore.QThread):
    status = QtCore.Signal(str)
    error = QtCore.Signal(str)
    finished = QtCore.Signal(dict)

    def __init__(self, config: JobConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        result = {"cancelled": False}
        try:
            outputs = run_job(self.config, self._cancel, self.status.emit)
            result["outputs"] = outputs
        except CancelledError:
            result["cancelled"] = True
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit(result)


def _run_ffmpeg(input_path: str, wav_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        wav_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg failed")


def _run_diarization(wav_path: str, model: str, hf_token: str | None, log) -> list[dict]:
    try:
        from pyannote.audio import Pipeline
    except Exception as exc:
        raise RuntimeError("pyannote.audio is not installed") from exc

    try:
        if os.path.exists(model):
            pipeline = Pipeline.from_pretrained(model)
        elif hf_token:
            pipeline = Pipeline.from_pretrained(model, use_auth_token=hf_token)
        else:
            pipeline = Pipeline.from_pretrained(model)
    except Exception as exc:
        raise RuntimeError(f"Failed to load diarization model: {exc}") from exc

    if log:
        log("Running speaker diarization...")
    diar = pipeline(wav_path)
    segments = []
    for turn, _track, speaker in diar.itertracks(yield_label=True):
        segments.append(
            {
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": str(speaker),
            }
        )
    return segments


def _assign_speakers(segments: list[dict], diarization: list[dict]) -> list[dict]:
    if not diarization:
        return segments
    labeled = []
    for seg in segments:
        best_speaker = None
        best_overlap = 0.0
        for diar in diarization:
            overlap = max(
                0.0,
                min(seg["end"], diar["end"]) - max(seg["start"], diar["start"]),
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = diar["speaker"]
        labeled_seg = dict(seg)
        labeled_seg["speaker"] = best_speaker or "Speaker ?"
        labeled.append(labeled_seg)
    return labeled


def _labeled_transcript(segments: list[dict]) -> str:
    lines = []
    current = None
    buffer = []
    for seg in segments:
        speaker = seg.get("speaker", "Speaker ?")
        text = seg.get("text", "").strip()
        if not text:
            continue
        if current is None:
            current = speaker
        if speaker != current and buffer:
            lines.append(f"{current}: " + " ".join(buffer))
            lines.append("")
            buffer = []
            current = speaker
        buffer.append(text)
    if buffer and current:
        lines.append(f"{current}: " + " ".join(buffer))
    return "\n".join(lines).strip() + "\n"


def _safe_name(value: str, fallback: str = "source") -> str:
    text = re.sub(r"[<>:\"/\\\\|?*]+", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" .")
    if not text:
        return fallback
    return text[:80]


def _build_output_dir(base_dir: str, topic: str, source_name: str) -> str:
    topic_name = _safe_name(topic, "General")
    source_folder = _safe_name(source_name, "Source")
    return os.path.join(base_dir, "Research", topic_name, source_folder)


def _load_model(
    model_size: str,
    log=None,
    device: str = "auto",
    compute_type: str = "auto",
):
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError("faster-whisper is not installed") from exc
    try:
        return WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:
        message = str(exc).lower()
        if "cublas" in message or "cuda" in message:
            if log:
                log("CUDA not available; falling back to CPU (int8).")
            return WhisperModel(model_size, device="cpu", compute_type="int8")
        raise


def _transcribe(
    wav_path: str,
    model_size: str,
    language: str,
    cancel_event: threading.Event,
    log,
):
    model = _load_model(model_size, log)
    lang = None if not language or language.lower() == "auto" else language
    try:
        segments, _info = model.transcribe(wav_path, language=lang, vad_filter=True)
    except Exception as exc:
        message = str(exc).lower()
        if "cublas" in message or "cuda" in message:
            if log:
                log("Transcribe failed on CUDA; retrying on CPU (int8).")
            model = _load_model(model_size, log, device="cpu", compute_type="int8")
            segments, _info = model.transcribe(wav_path, language=lang, vad_filter=True)
        else:
            raise
    results = []
    for seg in segments:
        if cancel_event.is_set():
            raise CancelledError()
        results.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text})
    return results


def run_job(config: JobConfig, cancel_event: threading.Event, log) -> list[str]:
    if not config.input_path and not config.youtube_url:
        raise RuntimeError("No input provided")

    os.makedirs(config.output_dir, exist_ok=True)
    outputs: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        if config.youtube_url:
            log("Fetching YouTube metadata...")
            meta = extract_metadata(config.youtube_url)
            if cancel_event.is_set():
                raise CancelledError()
            log("Downloading YouTube audio...")
            input_path = download_audio(config.youtube_url, tmpdir)
        else:
            meta = {}
            input_path = config.input_path

        if not os.path.exists(input_path):
            raise RuntimeError("Input file not found")

        wav_path = os.path.join(tmpdir, "audio.wav")
        log("Converting to WAV...")
        _run_ffmpeg(input_path, wav_path)

        if cancel_event.is_set():
            raise CancelledError()

        log("Transcribing...")
        segments = _transcribe(wav_path, config.model_size, config.language, cancel_event, log)

        if cancel_event.is_set():
            raise CancelledError()

        if config.youtube_url:
            author = youtube_author(meta)
            title = youtube_title(meta)
            _date_str, year = youtube_date(meta)
        else:
            author, title = parse_local_author_title(input_path)
            year = "n.d."

        source_name = title or os.path.splitext(os.path.basename(input_path))[0]
        output_dir = _build_output_dir(config.output_dir, config.topic, source_name)
        os.makedirs(output_dir, exist_ok=True)

        base = _safe_name(source_name, "source")

        diarization = []
        labeled_segments = segments
        if config.diarize_enabled:
            try:
                diarization = _run_diarization(
                    wav_path,
                    config.diarize_model,
                    config.hf_token,
                    log,
                )
                labeled_segments = _assign_speakers(segments, diarization)
            except Exception as exc:
                log(f"Diarization failed: {exc}")

        transcript_path = os.path.join(output_dir, f"{base}_transcript_clean.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            if config.diarize_enabled and labeled_segments != segments:
                f.write(_labeled_transcript(labeled_segments))
            else:
                f.write(paragraphize_segments(segments))
        outputs.append(transcript_path)

        if config.diarize_enabled and labeled_segments != segments:
            speaker_path = os.path.join(output_dir, f"{base}_transcript_speakers.txt")
            with open(speaker_path, "w", encoding="utf-8") as f:
                f.write(_labeled_transcript(labeled_segments))
            outputs.append(speaker_path)

        srt_path = os.path.join(output_dir, f"{base}_transcript.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(segments_to_srt(segments))
        outputs.append(srt_path)

        vtt_path = os.path.join(output_dir, f"{base}_transcript.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(segments_to_vtt(segments))
        outputs.append(vtt_path)

        clean_text = segments_to_text(segments)
        bullets = summary_bullets(clean_text, count=5)
        summary_path = os.path.join(output_dir, f"{base}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            for bullet in bullets:
                f.write(f"- {bullet}\n")
        outputs.append(summary_path)

        quotes = quote_candidates(segments, count=3)
        quotes_path = os.path.join(output_dir, f"{base}_quotes.txt")
        with open(quotes_path, "w", encoding="utf-8") as f:
            for quote in quotes:
                start = format_hhmmss(quote["start"])
                end = format_hhmmss(quote["end"])
                f.write(f"- [{start} - {end}] {quote['text']}\n")
        outputs.append(quotes_path)

        article_text = None
        if config.make_article:
            article_text = article_from_segments(segments)
            article_path = os.path.join(output_dir, f"{base}_transcript_article.txt")
            with open(article_path, "w", encoding="utf-8") as f:
                f.write(article_text)
            outputs.append(article_path)

        if config.make_citation:
            citation_path = os.path.join(output_dir, f"{base}_apa_reference.txt")
            if config.youtube_url:
                citation_text = apa7_from_youtube(meta, config.youtube_url)
            else:
                citation_text = apa7_from_local_file(config.input_path)
            with open(citation_path, "w", encoding="utf-8") as f:
                f.write(citation_text)
            outputs.append(citation_path)

            intext_path = os.path.join(output_dir, f"{base}_apa_intext.txt")
            with open(intext_path, "w", encoding="utf-8") as f:
                f.write(apa7_in_text_examples(author, year))
            outputs.append(intext_path)

            if article_text is not None:
                md_path = os.path.join(output_dir, f"{base}_transcript_article.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("# Citation\n")
                    f.write(citation_text.strip() + "\n\n")
                    f.write("# In-text Examples\n")
                    f.write(apa7_in_text_examples(author, year).strip() + "\n\n")
                    f.write("# Article\n")
                    f.write(article_text.strip() + "\n")
                outputs.append(md_path)

    return outputs
