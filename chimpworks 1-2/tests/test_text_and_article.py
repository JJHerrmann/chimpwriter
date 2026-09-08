import unittest

from chimpworks.render.article import article
from chimpworks.render.text import (
    clean_transcript,
    joined_text,
    paragraphize,
    sentences,
    speaker_transcript,
)
from tests._fixtures import sample_transcript


class TextRenderTests(unittest.TestCase):
    def setUp(self):
        self.t = sample_transcript()

    def test_joined_text_collapses_whitespace(self):
        self.assertNotIn("  ", joined_text(self.t.segments))
        self.assertTrue(joined_text(self.t.segments).startswith("Welcome back"))

    def test_paragraphize_groups_four_sentences(self):
        text = " ".join(f"Sentence number {i} here." for i in range(1, 10))
        paras = paragraphize(text, per_paragraph=4).split("\n\n")
        self.assertEqual(len(paras), 3)  # 4 + 4 + 1
        self.assertEqual(len(sentences(paras[0])), 4)

    def test_clean_transcript_ends_with_newline(self):
        self.assertTrue(clean_transcript(self.t).endswith("\n"))

    def test_speaker_transcript_merges_consecutive_turns(self):
        out = speaker_transcript(self.t)
        # 00 speaks, then 01, then 00 again -> exactly 3 labelled blocks
        labels = [ln.split(":")[0] for ln in out.splitlines() if ln.startswith("SPEAKER_")]
        self.assertEqual(labels, ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"])
        self.assertIn("second law still hold", out)


class ArticleTests(unittest.TestCase):
    def setUp(self):
        self.t = sample_transcript()

    def test_strips_standalone_fillers(self):
        out = article(self.t.segments)
        self.assertNotIn("Um.", out)
        self.assertIn("Fluctuations", out)

    def test_pause_starts_new_paragraph(self):
        # there's a >1.5s gap before the "second law" question (20.0 -> 21.8)
        out = article(self.t.segments)
        self.assertGreaterEqual(len(out.strip().split("\n\n")), 2)


if __name__ == "__main__":
    unittest.main()
