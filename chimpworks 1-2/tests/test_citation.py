import unittest

from chimpworks.models import SourceMeta
from chimpworks.render import citation as cite
from tests._fixtures import sample_meta_file, sample_meta_youtube


class CitationTests(unittest.TestCase):
    def test_apa7_youtube(self):
        ref = cite.apa7(sample_meta_youtube())
        self.assertIn("MIT OpenCourseWare", ref)
        self.assertIn("(2024, January 15)", ref)
        self.assertIn("[Video]. YouTube.", ref)
        self.assertIn("youtube.com/watch?v=abcdef12345", ref)

    def test_apa7_missing_date_is_nd(self):
        meta = SourceMeta(kind="youtube", url="u", title="T", author="A", date="", year="")
        self.assertIn("(n.d.)", cite.apa7(meta))

    def test_mla_and_chicago_render(self):
        meta = sample_meta_youtube()
        self.assertIn('"Lecture 3: Thermodynamics of Small Systems."', cite.mla9(meta))
        self.assertTrue(cite.chicago(meta).startswith("MIT OpenCourseWare. 2024."))

    def test_local_file_author_title_from_filename(self):
        author, title = cite.parse_local_author_title("/x/Feynman - Lecture 1 on Physics.mp3")
        self.assertEqual(author, "Feynman")
        self.assertEqual(title, "Lecture 1 on Physics")
        ref = cite.apa7(sample_meta_file())
        self.assertIn("Feynman", ref)
        self.assertIn("[Audio file]", ref)

    def test_in_text_examples(self):
        out = cite.in_text(sample_meta_youtube(), "apa")
        self.assertIn("Parenthetical: (MIT OpenCourseWare, 2024)", out)
        self.assertIn("Narrative: MIT OpenCourseWare (2024)", out)

    def test_bibtex_is_wellformed(self):
        bib = cite.bibtex(sample_meta_youtube())
        self.assertTrue(bib.startswith("@misc{"))
        self.assertIn("title = {Lecture 3: Thermodynamics of Small Systems}", bib)
        self.assertEqual(bib.count("{"), bib.count("}"))

    def test_render_all_keys(self):
        parts = cite.render_all(sample_meta_youtube(), "mla")
        self.assertEqual(set(parts), {"reference", "in_text", "bibtex"})


if __name__ == "__main__":
    unittest.main()
