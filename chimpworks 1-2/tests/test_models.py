import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from chimpworks.models import SCHEMA, Transcript
from tests._fixtures import sample_transcript


class TranscriptModelTests(unittest.TestCase):
    def test_json_roundtrip_is_lossless(self):
        t = sample_transcript()
        again = Transcript.from_dict(json.loads(t.to_json()))
        self.assertEqual(again.to_dict(), t.to_dict())
        self.assertEqual(again.schema, SCHEMA)
        self.assertEqual(again.segments[0].words[0].word, t.segments[0].words[0].word)
        self.assertEqual(again.speakers, t.speakers)

    def test_save_and_load(self):
        t = sample_transcript()
        with TemporaryDirectory() as d:
            p = Path(d) / "nested" / "x.transcript.json"
            t.save(p)
            self.assertTrue(p.exists())
            self.assertEqual(Transcript.load(p).to_dict(), t.to_dict())

    def test_convenience_helpers(self):
        t = sample_transcript()
        self.assertIn("thermodynamics", t.text())
        self.assertEqual(t.duration(), 41.0)
        self.assertTrue(t.has_speakers())
        self.assertGreater(t.word_count(), 40)

    def test_from_dict_tolerates_missing_and_extra_keys(self):
        t = Transcript.from_dict({
            "meta": {"kind": "file", "path": "/a/b.mp3", "bogus": 1},
            "segments": [{"start": 0, "end": 1, "text": "hi"}],
            "junk": True,
        })
        self.assertEqual(t.meta.path, "/a/b.mp3")
        self.assertEqual(t.segments[0].text, "hi")
        self.assertEqual(t.segments[0].words, [])
        self.assertFalse(t.has_speakers())


if __name__ == "__main__":
    unittest.main()
