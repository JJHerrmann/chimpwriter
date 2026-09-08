import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from chimpworks.models import Transcript
from chimpworks.render.packet import PacketOptions, packet_dir, safe_name, write_packet
from tests._fixtures import sample_transcript


class PacketTests(unittest.TestCase):
    def test_safe_name_strips_path_chars(self):
        self.assertEqual(safe_name('a/b:c*?"d'), "a b c d")
        self.assertEqual(safe_name("   "), "source")

    def test_packet_dir_layout(self):
        d = packet_dir("/root", "Thermo 101", "Lecture 3")
        self.assertEqual(d, Path("/root/Research/Thermo 101/Lecture 3"))

    def test_write_packet_emits_expected_files(self):
        t = sample_transcript()
        with TemporaryDirectory() as d:
            opts = PacketOptions(
                topic="Thermodynamics",
                formats=["txt", "srt", "vtt", "json"],
                make_article=True,
                make_citation=True,
                citation_style="apa",
                digest="heuristic",
            )
            written = write_packet(t, d, opts)
            names = sorted(p.name for p in written)
            base = safe_name(t.meta.display_name())
            for suffix in (
                ".transcript.json",
                "_transcript_clean.txt",
                "_transcript_speakers.txt",
                "_transcript.srt",
                "_transcript.vtt",
                "_article.txt",
                "_summary.txt",
                "_quotes.txt",
                "_citation_apa.txt",
                "_citation_intext.txt",
                "_citation.bib",
            ):
                self.assertIn(base + suffix, names, suffix)

            # transcript.json is the source of truth and reloads losslessly
            tj = next(p for p in written if p.name.endswith(".transcript.json"))
            self.assertEqual(Transcript.load(tj).to_dict(), t.to_dict())

            # all files landed under Research/<topic>/<source>/
            self.assertTrue(all("Research/Thermodynamics" in str(p) for p in written))

    def test_no_speakers_skips_speaker_file(self):
        t = sample_transcript(with_speakers=False)
        with TemporaryDirectory() as d:
            written = write_packet(t, d, PacketOptions(formats=["txt", "json"], make_citation=False))
            self.assertFalse(any("_transcript_speakers.txt" in p.name for p in written))
            self.assertTrue(any(p.name.endswith(".transcript.json") for p in written))

    def test_render_from_saved_transcript_matches(self):
        """The 'render' CLI path: reload transcript.json, re-emit, no ASR."""
        t = sample_transcript()
        with TemporaryDirectory() as d:
            first = write_packet(t, d, PacketOptions(formats=["srt", "json"], make_citation=False))
            tj = next(p for p in first if p.name.endswith(".transcript.json"))
            reloaded = Transcript.load(tj)
            srt1 = next(p for p in first if p.name.endswith(".srt")).read_text()
            with TemporaryDirectory() as d2:
                second = write_packet(reloaded, d2, PacketOptions(formats=["srt", "json"], make_citation=False))
                srt2 = next(p for p in second if p.name.endswith(".srt")).read_text()
            self.assertEqual(srt1, srt2)


if __name__ == "__main__":
    unittest.main()
