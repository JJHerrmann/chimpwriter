import subprocess
import unittest
from unittest import mock

from chimpworks.core import sources
from chimpworks.models import SourceMeta


class UrlDetectionTests(unittest.TestCase):
    def test_is_youtube_url(self):
        for good in (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/shorts/abc123DEF45",
            "watch this https://www.youtube.com/watch?v=abcdefghijk&t=30 please",
        ):
            self.assertTrue(sources.is_youtube_url(good), good)
        for bad in ("https://vimeo.com/12345", "just some text", "/home/me/lecture.mp4"):
            self.assertFalse(sources.is_youtube_url(bad), bad)

    def test_resolve_source_file_vs_url(self, ):
        m = sources.resolve_source("https://youtu.be/abcdefghijk")
        self.assertEqual(m.kind, "youtube")
        self.assertEqual(m.video_id, "abcdefghijk")
        with self.assertRaises(sources.SourceError):
            sources.resolve_source("/no/such/file.mp3")


class YtDlpInvocationTests(unittest.TestCase):
    def _fake_run(self, stdout="", returncode=0, stderr=""):
        def _run(cmd, capture_output=True, text=True):
            self.calls.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
        return _run

    def setUp(self):
        self.calls: list[list[str]] = []

    def test_probe_metadata_builds_expected_args(self):
        payload = '{"title": "T", "uploader": "U", "upload_date": "20240115", "duration": 12.0, "id": "vid123"}'
        with mock.patch("subprocess.run", side_effect=self._fake_run(stdout=payload)):
            meta = sources.probe_metadata(SourceMeta(kind="youtube", url="URL"), cookies_from_browser="firefox")
        cmd = self.calls[-1]
        self.assertIn("-j", cmd)
        self.assertIn("--no-playlist", cmd)
        self.assertIn("--cookies-from-browser", cmd)
        self.assertIn("firefox", cmd)
        self.assertEqual(meta.author, "U")
        self.assertEqual(meta.year, "2024")
        self.assertEqual(meta.duration, 12.0)

    def test_bot_check_message_is_actionable(self):
        run = self._fake_run(returncode=1, stderr="ERROR: Sign in to confirm you're not a bot")
        with mock.patch("subprocess.run", side_effect=run):
            with self.assertRaises(sources.SourceError) as ctx:
                sources.probe_metadata(SourceMeta(kind="youtube", url="URL"))
        self.assertIn("cookies-from-browser", str(ctx.exception))

    def test_expand_playlist_returns_urls(self):
        out = "https://www.youtube.com/watch?v=a\nhttps://www.youtube.com/watch?v=b\n"
        with mock.patch("subprocess.run", side_effect=self._fake_run(stdout=out)):
            urls = sources.expand_playlist("https://youtube.com/playlist?list=PL1")
        self.assertEqual(urls, ["https://www.youtube.com/watch?v=a", "https://www.youtube.com/watch?v=b"])
        self.assertIn("--flat-playlist", self.calls[-1])


if __name__ == "__main__":
    unittest.main()
