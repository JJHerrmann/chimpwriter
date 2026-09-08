import re
import unittest

from chimpworks.render.subtitles import (
    format_hhmmss,
    srt_timestamp,
    to_srt,
    to_vtt,
    vtt_timestamp,
)
from tests._fixtures import sample_transcript


class TimestampTests(unittest.TestCase):
    def test_srt_and_vtt_timestamp_formats(self):
        self.assertEqual(srt_timestamp(3661.5), "01:01:01,500")
        self.assertEqual(vtt_timestamp(3661.5), "01:01:01.500")
        self.assertEqual(srt_timestamp(0), "00:00:00,000")
        self.assertEqual(format_hhmmss(75), "00:01:15")


class SubtitleRenderTests(unittest.TestCase):
    def setUp(self):
        self.t = sample_transcript()

    def test_srt_structure(self):
        srt = to_srt(self.t.segments)
        blocks = srt.strip().split("\n\n")
        self.assertEqual(len(blocks), len(self.t.segments))
        first = blocks[0].splitlines()
        self.assertEqual(first[0], "1")
        self.assertRegex(first[1], r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")
        # speaker carried into the cue
        self.assertIn("<v SPEAKER_00>", first[2])

    def test_vtt_has_header_and_dot_timestamps(self):
        vtt = to_vtt(self.t.segments)
        self.assertTrue(vtt.startswith("WEBVTT\n"))
        self.assertIn(" --> ", vtt)
        self.assertNotIn(",", vtt.split("-->")[0].splitlines()[-1])

    def test_srt_indices_are_sequential(self):
        srt = to_srt(self.t.segments)
        indices = [int(m) for m in re.findall(r"^(\d+)$", srt, re.M)]
        self.assertEqual(indices, list(range(1, len(self.t.segments) + 1)))


if __name__ == "__main__":
    unittest.main()
