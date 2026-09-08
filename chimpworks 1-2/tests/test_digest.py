import unittest

from chimpworks.render.digest import HeuristicDigest, NullDigest, get_digest
from tests._fixtures import sample_transcript


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.t = sample_transcript()

    def test_get_digest_dispatch(self):
        self.assertIsInstance(get_digest("heuristic"), HeuristicDigest)
        self.assertIsInstance(get_digest("off"), NullDigest)
        self.assertIsInstance(get_digest("nonsense"), HeuristicDigest)

    def test_heuristic_highlights_are_longest_segments_with_timecodes(self):
        quotes = HeuristicDigest().highlights(self.t, count=3)
        self.assertEqual(len(quotes), 3)
        lengths = [len(q.text) for q in quotes]
        self.assertEqual(lengths, sorted(lengths, reverse=True))
        self.assertRegex(quotes[0].timecode(), r"^\[\d{2}:\d{2}:\d{2} - \d{2}:\d{2}:\d{2}\]$")
        self.assertTrue(all(q.speaker for q in quotes))  # speakers carried through

    def test_heuristic_summary_count(self):
        bullets = HeuristicDigest().summary(self.t, count=4)
        self.assertLessEqual(len(bullets), 4)
        self.assertTrue(all(isinstance(b, str) and b for b in bullets))

    def test_null_digest_is_empty(self):
        self.assertEqual(NullDigest().summary(self.t), [])
        self.assertEqual(NullDigest().highlights(self.t), [])


if __name__ == "__main__":
    unittest.main()
