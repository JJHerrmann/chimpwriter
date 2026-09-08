from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from PySide6 import QtCore, QtGui, QtWidgets

from app.settings import AppSettings, load_settings, save_settings
from app.settings_dialog import SettingsDialog
from app.dropzone import DropZoneWindow, DropPayload
from app.transcribe import JobConfig, TranscriptionWorker
from app.presets import SPEED_PRESET_ORDER, SPEED_PRESETS, resolve_speed_preset, resolve_model_size, make_monkey_wall
from app.tray import TrayController, load_app_icon


def apply_dark_palette(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(32, 34, 40))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 26, 31))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(32, 34, 40))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(48, 52, 60))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(122, 162, 255))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(16, 18, 22))
    app.setPalette(palette)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.worker: TranscriptionWorker | None = None
        self.setWindowTitle("Chimpwriter")
        self.setWindowIcon(load_app_icon())
        self.resize(760, 520)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.monkey_tagline = QtWidgets.QLabel("1000 monkeys on 1000 typewriters")
        tag_font = QtGui.QFont("Cascadia Mono")
        tag_font.setPointSize(10)
        tag_font.setBold(True)
        self.monkey_tagline.setFont(tag_font)
        self.monkey_tagline.setAlignment(QtCore.Qt.AlignCenter)
        self.monkey_tagline.setStyleSheet("color: #d9d9d9;")

        self.monkey_wall = QtWidgets.QLabel(make_monkey_wall())
        wall_font = QtGui.QFont("Cascadia Mono")
        wall_font.setPointSize(8)
        self.monkey_wall.setFont(wall_font)
        self.monkey_wall.setAlignment(QtCore.Qt.AlignCenter)
        self.monkey_wall.setStyleSheet("color: #5c6570;")
        self.monkey_wall.setWordWrap(True)

        layout.addWidget(self.monkey_tagline)
        layout.addWidget(self.monkey_wall)
        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)

        self.file_edit = QtWidgets.QLineEdit()
        self.file_edit.setPlaceholderText("Path to audio or video file")
        self.file_button = QtWidgets.QPushButton("Feed audio")
        self.file_button.clicked.connect(self.choose_file)

        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText("YouTube snack")
        self.grab_button = QtWidgets.QPushButton("Grab audio")
        self.grab_button.clicked.connect(self.start_from_url)

        self.speed_combo = QtWidgets.QComboBox()
        for key in SPEED_PRESET_ORDER:
            label = SPEED_PRESETS[key]["label"]
            self.speed_combo.addItem(f"{key} - {label}", key)
        self.speed_hint = QtWidgets.QLabel("")
        self.speed_hint.setStyleSheet("color: #9aa3ad;")
        self.speed_combo.currentIndexChanged.connect(self._update_speed_hint)

        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.addItem("Auto")

        self.output_edit = QtWidgets.QLineEdit()
        self.output_edit.setPlaceholderText("Output folder")
        self.output_button = QtWidgets.QPushButton("Choose folder")
        self.output_button.clicked.connect(self.choose_output_dir)

        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText("Topic")

        grid.addWidget(QtWidgets.QLabel("File"), 0, 0)
        grid.addWidget(self.file_edit, 0, 1)
        grid.addWidget(self.file_button, 0, 2)

        grid.addWidget(QtWidgets.QLabel("YouTube snack"), 1, 0)
        grid.addWidget(self.url_edit, 1, 1)
        grid.addWidget(self.grab_button, 1, 2)

        grid.addWidget(QtWidgets.QLabel("Speed"), 2, 0)
        grid.addWidget(self.speed_combo, 2, 1)
        grid.addWidget(self.speed_hint, 2, 2)

        grid.addWidget(QtWidgets.QLabel("Language"), 3, 0)
        grid.addWidget(self.language_combo, 3, 1)

        grid.addWidget(QtWidgets.QLabel("Output folder"), 4, 0)
        grid.addWidget(self.output_edit, 4, 1)
        grid.addWidget(self.output_button, 4, 2)

        grid.addWidget(QtWidgets.QLabel("Topic"), 5, 0)
        grid.addWidget(self.topic_edit, 5, 1)

        layout.addLayout(grid)

        self.article_check = QtWidgets.QCheckBox("Make it readable (no grunts)")
        self.citation_check = QtWidgets.QCheckBox("Generate APA7 citation")
        self.diarize_check = QtWidgets.QCheckBox("Multi-speaker (diarize)")
        layout.addWidget(self.article_check)
        layout.addWidget(self.citation_check)
        layout.addWidget(self.diarize_check)

        buttons = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Let the chimp type")
        self.cancel_button = QtWidgets.QPushButton("Stop the monkey")
        self.cancel_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_from_best)
        self.cancel_button.clicked.connect(self.cancel_job)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.status_log = QtWidgets.QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMinimumHeight(180)
        layout.addWidget(self.status_log)

        self.setCentralWidget(central)

    def _load_settings(self) -> None:
        self.output_edit.setText(self.settings.output_dir)
        self.topic_edit.setText(self.settings.topic)
        self.article_check.setChecked(self.settings.make_article)
        self.citation_check.setChecked(self.settings.make_citation)
        self.diarize_check.setChecked(self.settings.diarize_enabled)
        self._set_speed_preset(self.settings.speed_preset)
        if self.settings.language and self.settings.language != "auto":
            self.language_combo.setCurrentText(self.settings.language)
        else:
            self.language_combo.setCurrentText("Auto")

    def choose_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose audio or video")
        if path:
            self.file_edit.setText(path)

    def choose_output_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_edit.setText(path)

    def start_from_best(self) -> None:
        file_path = self.file_edit.text().strip()
        url = self.url_edit.text().strip()
        if file_path:
            self.start_job(input_path=file_path)
        elif url:
            self.start_job(youtube_url=url)
        else:
            self.log("No input provided.")

    def start_from_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self.log("No URL provided.")
            return
        self.start_job(youtube_url=url)

    def start_job(self, input_path: str | None = None, youtube_url: str | None = None) -> None:
        if self.worker and self.worker.isRunning():
            self.log("A job is already running.")
            return

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            self.log("Output folder is required.")
            return

        language = self.language_combo.currentText().strip()
        if language.lower() == "auto":
            language = "auto"

        config = JobConfig(
            input_path=input_path or "",
            youtube_url=youtube_url or "",
            output_dir=output_dir,
            topic=self.topic_edit.text().strip() or "General",
            model_size=resolve_model_size(self._current_speed_preset()),
            language=language,
            make_article=self.article_check.isChecked(),
            make_citation=self.citation_check.isChecked(),
            diarize_enabled=self.diarize_check.isChecked(),
            diarize_model=self.settings.diarize_model,
            hf_token=self.settings.hf_token,
        )

        self._save_settings_from_ui()

        self.worker = TranscriptionWorker(config)
        self.worker.status.connect(self.log)
        self.worker.error.connect(lambda msg: self.log(f"Error: {msg}"))
        self.worker.finished.connect(self.on_worker_finished)
        self.set_running(True)
        self.worker.start()

    def _save_settings_from_ui(self) -> None:
        self.settings.output_dir = self.output_edit.text().strip()
        self.settings.topic = self.topic_edit.text().strip() or "General"
        self.settings.speed_preset = self._current_speed_preset()
        language = self.language_combo.currentText().strip()
        self.settings.language = "auto" if language.lower() == "auto" else language
        self.settings.make_article = self.article_check.isChecked()
        self.settings.make_citation = self.citation_check.isChecked()
        self.settings.diarize_enabled = self.diarize_check.isChecked()
        save_settings(self.settings)

    def _current_speed_preset(self) -> str:
        preset = self.speed_combo.currentData()
        if not preset:
            preset = self.speed_combo.currentText()
        return resolve_speed_preset(str(preset))

    def _set_speed_preset(self, preset: str) -> None:
        preset = resolve_speed_preset(preset)
        for i in range(self.speed_combo.count()):
            if self.speed_combo.itemData(i) == preset:
                self.speed_combo.setCurrentIndex(i)
                break
        self._update_speed_hint()

    def _update_speed_hint(self) -> None:
        preset = self._current_speed_preset()
        model = resolve_model_size(preset)
        label = SPEED_PRESETS.get(preset, {}).get("label", "")
        text = f"{label} (model: {model})" if label else f"Model: {model}"
        self.speed_hint.setText(text)
    def on_worker_finished(self, result: dict) -> None:
        if result.get("cancelled"):
            self.log("Job cancelled.")
        elif result.get("outputs"):
            self.log("Outputs:")
            for path in result["outputs"]:
                self.log(f"  {path}")
        self.set_running(False)

    def cancel_job(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log("Cancel requested.")

    def handle_drop(self, payload: DropPayload) -> None:
        if payload.kind == "file":
            self.file_edit.setText(payload.value)
            self.start_job(input_path=payload.value)
            return
        if payload.kind == "youtube":
            self.url_edit.setText(payload.value)
            self.start_job(youtube_url=payload.value)
            return

        output_dir = self.output_edit.text().strip() or self.settings.output_dir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            note_path = Path(output_dir) / "dropped_url.txt"
            with open(note_path, "a", encoding="utf-8") as f:
                f.write(payload.value.strip() + "\n")
            self.log(f"Saved URL note to {note_path}")
        else:
            self.log("Dropped text received, but output folder is missing.")

    def show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self._load_settings()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def log(self, message: str) -> None:
        self.status_log.append(message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_dark_palette(app)

    settings = load_settings()
    main_window = MainWindow(settings)
    main_window.show()
    main_window.raise_()
    main_window.activateWindow()
    dropzone = DropZoneWindow()
    dropzone.dropped.connect(main_window.handle_drop)

    tray = TrayController(app, main_window, dropzone)
    tray.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())








