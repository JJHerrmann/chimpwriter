import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from chimpworks.config import Config, hf_token, load_config, resolve_model, with_overrides


class ConfigTests(unittest.TestCase):
    def test_speed_aliases_resolve_to_model_sizes(self):
        self.assertEqual(resolve_model("cheetah"), "tiny")
        self.assertEqual(resolve_model("Dolphin"), "small")
        self.assertEqual(resolve_model("whale"), "large-v3")
        self.assertEqual(resolve_model("large-v3"), "large-v3")
        self.assertEqual(resolve_model("garbage"), "small")
        self.assertEqual(resolve_model(None), "small")

    def test_defaults(self):
        c = Config()
        self.assertEqual(c.model, "small")
        self.assertTrue(c.word_timestamps)
        self.assertEqual(c.formats, ["txt", "srt", "vtt", "json"])
        self.assertFalse(c.diarize)

    def test_toml_overlay_and_alias_normalisation(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            p.write_text('\n'.join([
                'model = "whale"',
                'default_topic = "Physics"',
                'diarize = true',
                'citation_style = "mla"',
                'formats = ["txt", "json"]',
            ]), encoding="utf-8")
            c = load_config(p)
        self.assertEqual(c.model, "large-v3")   # alias normalised on load
        self.assertEqual(c.default_topic, "Physics")
        self.assertTrue(c.diarize)
        self.assertEqual(c.citation_style, "mla")
        self.assertEqual(c.formats, ["txt", "json"])

    def test_missing_config_returns_defaults(self):
        self.assertEqual(load_config("/no/such/config.toml").model, "small")

    def test_with_overrides_ignores_none_and_normalises_model(self):
        c = with_overrides(Config(), model="cheetah", language=None, topic_unknown="x" if False else None)
        self.assertEqual(c.model, "tiny")
        self.assertEqual(c.language, "auto")

    def test_hf_token_from_env_only(self):
        os.environ.pop("CHIMPWORKS_HF_TOKEN", None)
        self.assertEqual(hf_token(), "")
        os.environ["CHIMPWORKS_HF_TOKEN"] = "hf_abc"
        try:
            self.assertEqual(hf_token(), "hf_abc")
        finally:
            del os.environ["CHIMPWORKS_HF_TOKEN"]


if __name__ == "__main__":
    unittest.main()
