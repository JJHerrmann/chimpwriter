import unittest

from chimpworks.core import cleanup, llm
from chimpworks.core.cleanup import CleanupOptions, clean_segments
from chimpworks.models import Segment


def _segs(*texts):
    return [Segment(start=float(i), end=float(i) + 1, text=t) for i, t in enumerate(texts)]


class CleanupReadyTests(unittest.TestCase):
    def test_disabled(self):
        self.assertEqual(CleanupOptions(enabled=False, model="m").ready()[0], False)

    def test_no_model(self):
        ok, why = CleanupOptions(enabled=True, model="").ready()
        self.assertFalse(ok)
        self.assertIn("model", why)

    def test_ready(self):
        self.assertTrue(CleanupOptions(enabled=True, model="m").ready()[0])


class CleanupRunTests(unittest.TestCase):
    def setUp(self):
        self._real = llm.chat
        self.calls = []

    def tearDown(self):
        llm.chat = self._real

    def _patch(self, fn):
        def spy(messages, **kw):
            self.calls.append((messages, kw))
            return fn(messages, **kw)
        llm.chat = spy

    def test_applies_numbered_reply(self):
        self._patch(lambda m, **k: "0. Use n8n today\n1. Second line fixed")
        segs = _segs("Use neighten today", "Second line fixd")
        changed = clean_segments(segs, CleanupOptions(enabled=True, model="m"))
        self.assertEqual(changed, 2)
        self.assertEqual(segs[0].text, "Use n8n today")
        self.assertEqual(segs[1].text, "Second line fixed")

    def test_line_count_mismatch_keeps_original(self):
        self._patch(lambda m, **k: "0. only one line back")
        segs = _segs("alpha", "beta")
        changed = clean_segments(segs, CleanupOptions(enabled=True, model="m"))
        self.assertEqual(changed, 0)
        self.assertEqual([s.text for s in segs], ["alpha", "beta"])

    def test_llm_error_keeps_original(self):
        def boom(m, **k):
            raise llm.LlmError("no endpoint")
        self._patch(boom)
        segs = _segs("alpha", "beta")
        self.assertEqual(clean_segments(segs, CleanupOptions(enabled=True, model="m")), 0)
        self.assertEqual([s.text for s in segs], ["alpha", "beta"])

    def test_glossary_and_chunking(self):
        self._patch(lambda m, **k: "\n".join(
            f"{n}. x" for n, _ in _num_lines(m)
        ))
        segs = _segs(*[f"line {i} " + "y" * 50 for i in range(6)])
        clean_segments(
            segs,
            CleanupOptions(enabled=True, model="m", max_chars=160, glossary=["n8n", "Twilio"]),
        )
        self.assertGreater(len(self.calls), 1)  # split into chunks
        user_msg = self.calls[0][0][1]["content"]
        self.assertIn("n8n, Twilio", user_msg)

    def test_blank_reply_line_rejected(self):
        self._patch(lambda m, **k: "0. \n1. fine")
        segs = _segs("aaa", "bbb")
        self.assertEqual(clean_segments(segs, CleanupOptions(enabled=True, model="m")), 0)


def _num_lines(messages):
    import re
    body = messages[1]["content"]
    return [(int(m.group(1)), m.group(2))
            for m in (re.match(r"^(\d+)\.\s*(.*)$", ln) for ln in body.splitlines()) if m]


if __name__ == "__main__":
    unittest.main()
