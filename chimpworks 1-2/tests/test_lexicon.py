import unittest

from chimpworks.core.lexicon import Lexicon, parse_lexicon, save_lexicon, read_raw


class LexiconTests(unittest.TestCase):
    def test_hotwords_join(self):
        lex = parse_lexicon({"terms": ["n8n", " LangChain ", ""]})
        self.assertEqual(lex.hotwords(), "n8n, LangChain")

    def test_plain_fix_is_whole_word_ci(self):
        lex = parse_lexicon({"fixes": {"neighten": "n8n"}})
        self.assertEqual(lex.apply("So Neighten runs the flow"), "So n8n runs the flow")
        # substring should not match
        self.assertEqual(lex.apply("neightenish"), "neightenish")

    def test_regex_fix(self):
        lex = parse_lexicon({"fixes": {r"re:\bN[ -]?10\b": "n8n"}})
        self.assertEqual(lex.apply("open N-10 then N 10"), "open n8n then n8n")

    def test_fixes_apply_in_order(self):
        lex = parse_lexicon({"fixes": {"a": "b", "b": "c"}})
        self.assertEqual(lex.apply("a"), "c")

    def test_bad_regex_skipped(self):
        lex = parse_lexicon({"fixes": {"re:[unclosed": "x", "good": "ok"}})
        self.assertEqual(len(lex.fixes), 1)
        self.assertEqual(lex.apply("good"), "ok")

    def test_empty_lexicon_is_falsy_and_noop(self):
        lex = Lexicon()
        self.assertFalse(lex)
        self.assertEqual(lex.hotwords(), "")
        self.assertEqual(lex.apply("unchanged"), "unchanged")

    def test_save_then_read_roundtrip(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lex.toml"
            save_lexicon(["n8n", "n8n", "Make.com"], {"neighten": "n8n"}, p)
            terms, fixes, back = read_raw(p)
            self.assertEqual(terms, ["n8n", "Make.com"])   # de-duped, order kept
            self.assertEqual(fixes, {"neighten": "n8n"})
            self.assertEqual(back, p)


if __name__ == "__main__":
    unittest.main()
