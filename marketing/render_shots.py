"""Render clean Chimpwriter GUI screenshots for the store listing."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6 import QtWidgets  # noqa: E402
from PIL import Image  # noqa: E402

import chimpworks.licensing as L  # noqa: E402
from chimpworks.gui.app import MainWindow, SettingsDialog, _dark_palette  # noqa: E402
from chimpworks.gui.prefs import load_prefs  # noqa: E402
from chimpworks.gui.lexicon_dialog import LexiconDialog  # noqa: E402

OUT = sys.argv[1]
RAW = os.path.join(OUT, "_raw")
os.makedirs(RAW, exist_ok=True)

app = QtWidgets.QApplication([])
_dark_palette(app)

BG = (18, 19, 23)
PAD = 56
SCALE = 2
OUTDIR = "~/Documents/Chimpworks"


def snap(widget, name, w=880, h=520, crop_bottom=0):
    widget.resize(w, h)
    widget.show()
    for _ in range(3):
        app.processEvents()
    raw = os.path.join(RAW, name)
    widget.grab().save(raw)
    im = Image.open(raw).convert("RGB")
    im = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    if crop_bottom:
        im = im.crop((0, 0, im.width, im.height - crop_bottom * SCALE))
    pad = PAD * SCALE
    canvas = Image.new("RGB", (im.width + pad * 2, im.height + pad * 2), BG)
    canvas.paste((8, 8, 10), (pad + 16, pad + 16, pad + 16 + im.width, pad + 16 + im.height))
    canvas.paste(im, (pad, pad))
    canvas.save(os.path.join(OUT, name), quality=92)
    print("wrote", name)


def main_win():
    w = MainWindow()
    w.out_edit.setText(OUTDIR)
    return w


# 1. fresh
win = main_win()
win.token_banner.hide()
snap(win, "01-main.png", 880, 520, crop_bottom=210)

# 2. a job set up, ready to run  (hero)
win.source_edit.setText("https://www.youtube.com/watch?v=physics-lecture-07")
win.topic_edit.setText("Thermodynamics")
for c in (win.diar_check, win.cleanup_check, win.article_check, win.cite_check):
    c.setChecked(True)
win.token_banner.hide()
snap(win, "02-ready.png", 880, 540, crop_bottom=230)

# 3. running
for line in ["Source: https://www.youtube.com/watch?v=physics-lecture-07",
             "resolve…", "fetch-audio…", "transcribe  58%"]:
    win._append(line)
win.progress.setRange(0, 100)
win.progress.setValue(58)
win.go_btn.setEnabled(False)
win.stop_btn.setEnabled(True)
win.token_banner.hide()
snap(win, "03-running.png", 880, 600, crop_bottom=40)

# 4. done
win.log.clear()
folder = f"{OUTDIR}/Research/Thermodynamics/Lecture 07"
for line in [
    "Transcribed 8,412 words, 2 speaker(s) — writing packet…",
    "Done — 6 files:",
    f"  {folder}/Lecture 07.transcript.json",
    f"  {folder}/Lecture 07_transcript_clean.txt",
    f"  {folder}/Lecture 07_article.txt",
    f"  {folder}/Lecture 07_transcript.srt",
    f"  {folder}/Lecture 07_transcript.vtt",
    f"  {folder}/Lecture 07_citation.txt",
    f"Folder: {folder}",
]:
    win._append(line)
win.progress.setValue(100)
win.go_btn.setEnabled(True)
win.stop_btn.setEnabled(False)
win.token_banner.hide()
snap(win, "04-done.png", 880, 640)

# 5. settings — render as a finished, licensing-configured build
L.ENFORCE = True
L.BASE_URL = "https://licensing.chimpwriter.app"
L.cached.cache_clear()
dlg = SettingsDialog(load_prefs())
snap(dlg, "05-settings.png", 640, dlg.sizeHint().height())

# 6. terminology library
lex_path = os.path.join(tempfile.gettempdir(), "Thermodynamics.lexicon.toml")
with open(lex_path, "w") as fh:
    fh.write(
        'terms = ["n8n", "Make.com", "LangChain", "Zapier", "webhook", "idempotent"]\n\n'
        "[fixes]\n'lang chain' = 'LangChain'\n'make dot com' = 'Make.com'\n"
    )
try:
    lex = LexiconDialog(path=lex_path)
    snap(lex, "06-terminology.png", 720, 560)
except Exception as exc:  # noqa: BLE001
    print("terminology skipped:", exc)

print("done ->", OUT)
