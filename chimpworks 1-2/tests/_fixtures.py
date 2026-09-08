"""A hand-built Transcript so every render/test runs offline (no ASR, no network)."""
from __future__ import annotations

from chimpworks.models import Segment, SourceMeta, SpeakerTurn, Transcript, Word


def sample_meta_youtube() -> SourceMeta:
    return SourceMeta(
        kind="youtube",
        url="https://www.youtube.com/watch?v=abcdef12345",
        video_id="abcdef12345",
        title="Lecture 3: Thermodynamics of Small Systems",
        author="MIT OpenCourseWare",
        date="20240115",
        year="2024",
        duration=41.0,
    )


def sample_meta_file(path: str = "/tmp/Feynman - Lecture 1 on Physics.mp3") -> SourceMeta:
    return SourceMeta(kind="file", path=path, title="Feynman - Lecture 1 on Physics")


def _seg(start, end, text, speaker=None):
    dur = (end - start) / max(len(text.split()), 1)
    words = []
    t = start
    for tok in text.split():
        words.append(Word(start=round(t, 2), end=round(t + dur, 2), word=" " + tok, probability=0.9))
        t += dur
    return Segment(start=start, end=end, text=text, words=words, speaker=speaker)


def sample_transcript(*, with_speakers: bool = True) -> Transcript:
    sp_a = "SPEAKER_00" if with_speakers else None
    sp_b = "SPEAKER_01" if with_speakers else None
    segs = [
        _seg(0.0, 6.0, "Welcome back to the course on thermodynamics and statistical mechanics.", sp_a),
        _seg(6.0, 12.5, "Today we look at what happens when the number of particles is genuinely small.", sp_a),
        _seg(12.5, 13.2, "Um.", sp_a),
        _seg(13.2, 20.0, "Fluctuations that we normally ignore become the dominant effect in these systems.", sp_a),
        _seg(21.8, 28.0, "So does the second law still hold if we can watch every microstate directly?", sp_b),
        _seg(28.0, 35.0, "It holds on average, but individual trajectories can transiently violate it.", sp_a),
        _seg(35.0, 41.0, "That is the content of the fluctuation theorems we will derive next week.", sp_a),
    ]
    turns = []
    if with_speakers:
        turns = [
            SpeakerTurn(0.0, 20.0, "SPEAKER_00"),
            SpeakerTurn(21.8, 28.0, "SPEAKER_01"),
            SpeakerTurn(28.0, 41.0, "SPEAKER_00"),
        ]
    return Transcript(
        meta=sample_meta_youtube(),
        language="en",
        model="small",
        segments=segs,
        speakers=turns,
        created_utc=1_700_000_000,
    )
