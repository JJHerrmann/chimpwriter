from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.presets import SPEED_PRESET_ORDER, SPEED_PRESETS, resolve_speed_preset
from app.settings import AppSettings, save_settings
from app.tray import load_app_icon


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setWindowIcon(load_app_icon())
        self.setModal(True)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.output_edit = QtWidgets.QLineEdit()
        self.output_button = QtWidgets.QPushButton("Browse")
        self.output_button.clicked.connect(self._choose_output_dir)
        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(self.output_button)
        output_wrap = QtWidgets.QWidget()
        output_wrap.setLayout(output_row)

        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText("Topic")

        self.speed_combo = QtWidgets.QComboBox()
        for key in SPEED_PRESET_ORDER:
            label = SPEED_PRESETS[key]["label"]
            self.speed_combo.addItem(f"{key} - {label}", key)

        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.addItem("Auto")

        self.article_check = QtWidgets.QCheckBox("Make it readable (no grunts)")
        self.citation_check = QtWidgets.QCheckBox("Generate APA7 citation")
        self.diarize_check = QtWidgets.QCheckBox("Multi-speaker (diarize)")

        self.diarize_model_edit = QtWidgets.QLineEdit()
        self.diarize_model_edit.setPlaceholderText(
            r"R:\Rookworks\011_AI_Operations\03_Audio\models\pyannote\speaker-diarization-3.1"
        )

        self.hf_token_edit = QtWidgets.QLineEdit()
        self.hf_token_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.hf_token_edit.setPlaceholderText("Hugging Face token (optional if model is local)")

        form.addRow("Output folder", output_wrap)
        form.addRow("Topic", self.topic_edit)
        form.addRow("Speed", self.speed_combo)
        form.addRow("Language", self.language_combo)

        layout.addLayout(form)
        layout.addWidget(self.article_check)
        layout.addWidget(self.citation_check)
        layout.addWidget(self.diarize_check)
        layout.addWidget(QtWidgets.QLabel("Diarization model"))
        layout.addWidget(self.diarize_model_edit)
        layout.addWidget(QtWidgets.QLabel("Hugging Face token"))
        layout.addWidget(self.hf_token_edit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self) -> None:
        self.output_edit.setText(self.settings.output_dir)
        self.topic_edit.setText(self.settings.topic)
        preset = resolve_speed_preset(self.settings.speed_preset)
        for i in range(self.speed_combo.count()):
            if self.speed_combo.itemData(i) == preset:
                self.speed_combo.setCurrentIndex(i)
                break

        if self.settings.language and self.settings.language != "auto":
            self.language_combo.setCurrentText(self.settings.language)
        else:
            self.language_combo.setCurrentText("Auto")

        self.article_check.setChecked(self.settings.make_article)
        self.citation_check.setChecked(self.settings.make_citation)
        self.diarize_check.setChecked(self.settings.diarize_enabled)
        self.diarize_model_edit.setText(self.settings.diarize_model)
        self.hf_token_edit.setText(self.settings.hf_token)

    def _choose_output_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_edit.setText(path)

    def _apply_and_accept(self) -> None:
        self.settings.output_dir = self.output_edit.text().strip()
        self.settings.topic = self.topic_edit.text().strip() or "General"
        preset = self.speed_combo.currentData()
        if not preset:
            preset = self.speed_combo.currentText()
        self.settings.speed_preset = resolve_speed_preset(str(preset))

        language = self.language_combo.currentText().strip()
        self.settings.language = "auto" if language.lower() == "auto" else language

        self.settings.make_article = self.article_check.isChecked()
        self.settings.make_citation = self.citation_check.isChecked()
        self.settings.diarize_enabled = self.diarize_check.isChecked()
        self.settings.diarize_model = (
            self.diarize_model_edit.text().strip()
            or r"R:\Rookworks\011_AI_Operations\03_Audio\models\pyannote\speaker-diarization-3.1"
        )
        self.settings.hf_token = self.hf_token_edit.text().strip()

        save_settings(self.settings)
        self.accept()
