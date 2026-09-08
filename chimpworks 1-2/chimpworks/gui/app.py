"""Chimpwriter main window + settings dialog."""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .. import __version__
from ..config import load_config, resolve_model
from ..core.pipeline import TranscribeOptions
from ..paths import MODELS_DIR
from ..render.packet import PacketOptions
from . import secrets as hfsecrets
from .lexicon_dialog import LexiconDialog
from .prefs import SPEED_TO_MODEL, GuiPrefs, load_prefs, save_prefs
from .worker import JobWorker

VENDORED_DIAR = MODELS_DIR / "pyannote-community-1" / "config.yaml"
TOKENS_URL = "https://huggingface.co/settings/tokens"
GATE_URL = "https://huggingface.co/pyannote/speaker-diarization-community-1"


def _dark_palette(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    p = QtGui.QPalette()
    c = QtGui.QColor
    p.setColor(QtGui.QPalette.Window, c(32, 34, 40))
    p.setColor(QtGui.QPalette.WindowText, c(240, 240, 240))
    p.setColor(QtGui.QPalette.Base, c(24, 26, 31))
    p.setColor(QtGui.QPalette.AlternateBase, c(32, 34, 40))
    p.setColor(QtGui.QPalette.ToolTipBase, c(240, 240, 240))
    p.setColor(QtGui.QPalette.ToolTipText, c(16, 18, 22))
    p.setColor(QtGui.QPalette.Text, c(240, 240, 240))
    p.setColor(QtGui.QPalette.Button, c(48, 52, 60))
    p.setColor(QtGui.QPalette.ButtonText, c(240, 240, 240))
    p.setColor(QtGui.QPalette.Highlight, c(122, 162, 255))
    p.setColor(QtGui.QPalette.HighlightedText, c(16, 18, 22))
    p.setColor(QtGui.QPalette.PlaceholderText, c(140, 146, 155))
    app.setPalette(p)


def _diar_is_vendored() -> bool:
    try:
        return VENDORED_DIAR.exists()
    except OSError:
        return False


# --------------------------------------------------------------------------- #
#  Token test -- runs off the UI thread                                        #
# --------------------------------------------------------------------------- #
class _TokenTester(QtCore.QThread):
    result = QtCore.Signal(dict)

    def __init__(self, token: str, parent=None):
        super().__init__(parent)
        self._token = token

    def run(self) -> None:
        self.result.emit(hfsecrets.verify_token(self._token))


# --------------------------------------------------------------------------- #
#  Settings dialog                                                             #
# --------------------------------------------------------------------------- #
class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, prefs: GuiPrefs, parent=None):
        super().__init__(parent)
        self.prefs = prefs
        self._tester: _TokenTester | None = None
        self.setWindowTitle("Chimpwriter settings")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build()
        self._load()

    def _build(self) -> None:
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.diar_model_edit = QtWidgets.QLineEdit()
        self.diar_model_edit.setPlaceholderText(
            "pyannote/speaker-diarization-3.1  or  a local pipeline path"
        )
        form.addRow("Diarization model", self.diar_model_edit)
        lay.addLayout(form)

        # --- Hugging Face token group ---
        box = QtWidgets.QGroupBox("Hugging Face account  (only needed to download the "
                                  "diarization model)")
        bl = QtWidgets.QVBoxLayout(box)
        bl.setSpacing(8)

        row = QtWidgets.QHBoxLayout()
        self.token_edit = QtWidgets.QLineEdit()
        self.token_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.token_edit.setPlaceholderText("hf_...")
        self.show_token = QtWidgets.QToolButton()
        self.show_token.setText("show")
        self.show_token.setCheckable(True)
        self.show_token.toggled.connect(
            lambda on: self.token_edit.setEchoMode(
                QtWidgets.QLineEdit.Normal if on else QtWidgets.QLineEdit.Password
            )
        )
        self.test_btn = QtWidgets.QPushButton("Test")
        self.test_btn.clicked.connect(self._test_token)
        row.addWidget(self.token_edit, 1)
        row.addWidget(self.show_token)
        row.addWidget(self.test_btn)
        bl.addLayout(row)

        self.token_status = QtWidgets.QLabel()
        self.token_status.setWordWrap(True)
        self.token_status.setStyleSheet("color: #9aa3ad;")
        bl.addWidget(self.token_status)

        links = QtWidgets.QHBoxLayout()
        get_btn = QtWidgets.QPushButton("Get a token →")
        get_btn.setFlat(True)
        get_btn.clicked.connect(lambda: webbrowser.open(TOKENS_URL))
        gate_btn = QtWidgets.QPushButton("Accept model terms →")
        gate_btn.setFlat(True)
        gate_btn.clicked.connect(lambda: webbrowser.open(GATE_URL))
        links.addWidget(get_btn)
        links.addWidget(gate_btn)
        links.addStretch(1)
        bl.addLayout(links)
        lay.addWidget(box)

        self.storage_hint = QtWidgets.QLabel(f"Stored in: {hfsecrets.storage_kind()}")
        self.storage_hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        lay.addWidget(self.storage_hint)

        if _diar_is_vendored():
            done = QtWidgets.QLabel("Diarization model already downloaded — a token "
                                    "is no longer required.")
            done.setStyleSheet("color: #6fcf97;")
            done.setWordWrap(True)
            lay.addWidget(done)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._save_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load(self) -> None:
        self.diar_model_edit.setText(self.prefs.diarize_model)
        self.token_edit.setText(hfsecrets.load_token())

    def _test_token(self) -> None:
        self.test_btn.setEnabled(False)
        self.token_status.setStyleSheet("color: #9aa3ad;")
        self.token_status.setText("Checking with huggingface.co…")
        self._tester = _TokenTester(self.token_edit.text().strip(), self)
        self._tester.result.connect(self._test_done)
        self._tester.start()

    def _test_done(self, res: dict) -> None:
        self.test_btn.setEnabled(True)
        if res.get("ok") and res.get("gated_ok"):
            self.token_status.setStyleSheet("color: #6fcf97;")
        elif res.get("ok"):
            self.token_status.setStyleSheet("color: #f2c94c;")
        else:
            self.token_status.setStyleSheet("color: #eb5757;")
        self.token_status.setText(res.get("detail", ""))

    def _save_accept(self) -> None:
        self.prefs.diarize_model = (
            self.diar_model_edit.text().strip() or "pyannote/speaker-diarization-3.1"
        )
        where = hfsecrets.save_token(self.token_edit.text().strip())
        self.storage_hint.setText(f"Stored in: {where}")
        save_prefs(self.prefs)
        self.accept()


# --------------------------------------------------------------------------- #
#  Main window                                                                 #
# --------------------------------------------------------------------------- #
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.prefs = load_prefs()
        self.worker: JobWorker | None = None
        self.setWindowTitle(f"Chimpwriter {__version__}")
        self.resize(720, 560)
        self._build()
        self._load_prefs()
        self._refresh_token_banner()

    # -- construction ----------------------------------------------------
    def _build(self) -> None:
        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        tag = QtWidgets.QLabel("1000 monkeys, 1000 typewriters — now headless underneath")
        tag.setAlignment(QtCore.Qt.AlignCenter)
        tag.setStyleSheet("color: #d9d9d9; font-weight: bold;")
        v.addWidget(tag)

        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)

        self.source_edit = QtWidgets.QLineEdit()
        self.source_edit.setPlaceholderText("YouTube URL, or path to an audio/video file")
        browse = QtWidgets.QPushButton("File…")
        browse.clicked.connect(self._choose_file)
        grid.addWidget(QtWidgets.QLabel("Source"), 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        grid.addWidget(browse, 0, 2)

        self.speed_combo = QtWidgets.QComboBox()
        for label, size in SPEED_TO_MODEL.items():
            self.speed_combo.addItem(f"{label} — {size}", size)
        grid.addWidget(QtWidgets.QLabel("Speed"), 1, 0)
        grid.addWidget(self.speed_combo, 1, 1)

        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.setEditable(True)
        self.lang_combo.addItems(["auto", "en", "es", "fr", "de", "it", "pt", "nl", "ja", "zh"])
        grid.addWidget(QtWidgets.QLabel("Language"), 2, 0)
        grid.addWidget(self.lang_combo, 2, 1)

        self.out_edit = QtWidgets.QLineEdit()
        out_btn = QtWidgets.QPushButton("Folder…")
        out_btn.clicked.connect(self._choose_out)
        grid.addWidget(QtWidgets.QLabel("Output to"), 3, 0)
        grid.addWidget(self.out_edit, 3, 1)
        grid.addWidget(out_btn, 3, 2)

        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText("Topic (folder name under Research/)")
        grid.addWidget(QtWidgets.QLabel("Topic"), 4, 0)
        grid.addWidget(self.topic_edit, 4, 1)
        v.addLayout(grid)

        self.diar_check = QtWidgets.QCheckBox("Multi-speaker (diarize)")
        self.diar_check.toggled.connect(self._refresh_token_banner)
        self.article_check = QtWidgets.QCheckBox("Readable article (strip filler)")
        self.cite_check = QtWidgets.QCheckBox("APA citation")
        v.addWidget(self.diar_check)
        v.addWidget(self.article_check)
        v.addWidget(self.cite_check)

        self.token_banner = QtWidgets.QLabel()
        self.token_banner.setWordWrap(True)
        self.token_banner.setOpenExternalLinks(True)
        self.token_banner.setStyleSheet(
            "background:#3a2f1a; color:#f2c94c; padding:8px; border-radius:6px;"
        )
        self.token_banner.hide()
        v.addWidget(self.token_banner)

        btnrow = QtWidgets.QHBoxLayout()
        self.go_btn = QtWidgets.QPushButton("Transcribe")
        self.go_btn.clicked.connect(self._start)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        terms_btn = QtWidgets.QPushButton("Terminology…")
        terms_btn.clicked.connect(self._open_lexicon)
        gear = QtWidgets.QPushButton("Settings…")
        gear.clicked.connect(self._open_settings)
        btnrow.addWidget(self.go_btn)
        btnrow.addWidget(self.stop_btn)
        btnrow.addStretch(1)
        btnrow.addWidget(terms_btn)
        btnrow.addWidget(gear)
        v.addLayout(btnrow)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        v.addWidget(self.progress)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        v.addWidget(self.log)

        self.setCentralWidget(central)

    # -- prefs round-trip ---------------------------------------------------
    def _load_prefs(self) -> None:
        p = self.prefs
        self.source_edit.setText(p.last_input)
        self.out_edit.setText(p.output_dir)
        self.topic_edit.setText(p.topic)
        self.lang_combo.setCurrentText(p.language or "auto")
        idx = self.speed_combo.findData(p.model)
        self.speed_combo.setCurrentIndex(idx if idx >= 0 else 1)
        self.diar_check.setChecked(p.diarize)
        self.article_check.setChecked(p.make_article)
        self.cite_check.setChecked(p.make_citation)

    def _collect_prefs(self) -> None:
        p = self.prefs
        p.last_input = self.source_edit.text().strip()
        p.output_dir = self.out_edit.text().strip()
        p.topic = self.topic_edit.text().strip() or "General"
        p.language = self.lang_combo.currentText().strip() or "auto"
        p.model = self.speed_combo.currentData()
        p.diarize = self.diar_check.isChecked()
        p.make_article = self.article_check.isChecked()
        p.make_citation = self.cite_check.isChecked()
        save_prefs(p)

    # -- token banner -----------------------------------------------------
    def _refresh_token_banner(self) -> None:
        if not self.diar_check.isChecked() or _diar_is_vendored() or hfsecrets.load_token():
            self.token_banner.hide()
            return
        self.token_banner.setText(
            "Diarization needs a Hugging Face token the first time (to download the "
            "speaker model). Add one in <b>Settings…</b>, or the run will fall "
            "back to no speaker labels."
        )
        self.token_banner.show()

    # -- dialogs --------------------------------------------------------
    def _choose_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose audio or video")
        if path:
            self.source_edit.setText(path)

    def _choose_out(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.out_edit.setText(path)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.prefs, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._refresh_token_banner()

    def _open_lexicon(self) -> None:
        LexiconDialog(self).exec()

    # -- job lifecycle -----------------------------------------------------
    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        source = self.source_edit.text().strip()
        if not source:
            self._append("No source given.")
            return
        out_dir = self.out_edit.text().strip()
        if not out_dir:
            self._append("Choose an output folder.")
            return
        self._collect_prefs()

        cfg = load_config()
        t_opts = TranscribeOptions(
            model=resolve_model(self.prefs.model),
            language=self.prefs.language,
            device=cfg.device,
            compute_type=cfg.compute_type,
            word_timestamps=cfg.word_timestamps,
            diarize=self.prefs.diarize,
            diarize_model=self.prefs.diarize_model,
            hf_token=hfsecrets.load_token(),
            cookies_from_browser=cfg.yt_cookies_from_browser,
        )
        p_opts = PacketOptions(
            topic=self.prefs.topic,
            formats=cfg.formats,
            make_article=self.prefs.make_article,
            make_citation=self.prefs.make_citation,
            citation_style=cfg.citation_style,
            digest=cfg.digest,
        )

        self.log.clear()
        self.progress.setValue(0)
        self._set_running(True)
        self.worker = JobWorker(
            source=source, out_root=out_dir, t_opts=t_opts, p_opts=p_opts,
            hf_token=t_opts.hf_token, parent=self,
        )
        self.worker.progressed.connect(self._on_progress)
        self.worker.logged.connect(self._append)
        self.worker.finished_ok.connect(self._on_ok)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._append("Stopping after the current step…")

    def _on_progress(self, stage: str, frac: float) -> None:
        if frac < 0:
            self.progress.setRange(0, 0)  # busy
            self._append(f"{stage}…")
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(frac * 100))
            if stage != "transcribe" or frac >= 1.0:
                self._append(f"{stage}: {int(frac * 100)}%")

    def _on_ok(self, paths: list) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._append(f"Done — {len(paths)} files:")
        for p in paths:
            self._append(f"  {p}")
        self._set_running(False)
        if paths:
            folder = str(Path(paths[0]).parent)
            self._append(f"Folder: {folder}")

    def _on_fail(self, msg: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._append("Cancelled." if msg == "cancelled" else f"Failed: {msg}")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.go_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _append(self, line: str) -> None:
        self.log.appendPlainText(line)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()


def main(argv: list[str] | None = None) -> int:
    app = QtWidgets.QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Chimpwriter")
    _dark_palette(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
