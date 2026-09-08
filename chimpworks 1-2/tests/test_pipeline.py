"""Pipeline wiring test - ASR, ffmpeg and yt-dlp are all stubbed so this runs
with nothing but the stdlib + platformdirs installed.
"""
import unittest
from pathlib import Path
from unittest import mock

from chimpworks.core.pipeline import TranscribeOptions, build_transcript
from chimpworks.models import Segment, SourceMeta


def _fake_segments():
    return [
        Segment(0.0, 4.0, "First line of the talk."),
        Segment(4.0, 9.0, "Second line, a bit longer than the first one here."),
    ], "en"


class PipelineWiringTests(unittest.TestCase):
    def test_build_transcript_produces_populated_transcript(self):
        with mock.patch("chimpworks.core.pipeline.resolve_source",
                        return_value=SourceMeta(kind="youtube", url="U", title="Talk", author="Chan", duration=None)), \
             mock.patch("chimpworks.core.pipeline.probe_metadata", side_effect=lambda s, **k: s), \
             mock.patch("chimpworks.core.pipeline.fetch_audio", side_effect=lambda s, wd, **k: Path(wd) / "in.m4a"), \
             mock.patch("chimpworks.core.audio.to_wav", side_effect=lambda s, d, **k: Path(d)), \
             mock.patch("chimpworks.core.asr.transcribe", side_effect=lambda *a, **k: _fake_segments()):
            t = build_transcript("U", TranscribeOptions(model="small"))
        self.assertEqual(len(t.segments), 2)
        self.assertEqual(t.language, "en")
        self.assertEqual(t.model, "small")
        self.assertEqual(t.meta.duration, 9.0)  # backfilled from last segment
        self.assertIn("First line", t.text())

    def test_diarization_failure_is_non_fatal(self):
        with mock.patch("chimpworks.core.pipeline.resolve_source",
                        return_value=SourceMeta(kind="file", path="/x/a.mp3", title="a")), \
             mock.patch("chimpworks.core.pipeline.probe_metadata", side_effect=lambda s, **k: s), \
             mock.patch("chimpworks.core.pipeline.fetch_audio", side_effect=lambda s, wd, **k: Path("/x/a.mp3")), \
             mock.patch("chimpworks.core.audio.to_wav", side_effect=lambda s, d, **k: Path(d)), \
             mock.patch("chimpworks.core.asr.transcribe", side_effect=lambda *a, **k: _fake_segments()), \
             mock.patch("chimpworks.core.diarize.diarize", side_effect=RuntimeError("no model")):
            t = build_transcript("/x/a.mp3", TranscribeOptions(model="small", diarize=True))
        self.assertEqual(len(t.segments), 2)          # transcript still produced
        self.assertFalse(t.has_speakers())


if __name__ == "__main__":
    unittest.main()
