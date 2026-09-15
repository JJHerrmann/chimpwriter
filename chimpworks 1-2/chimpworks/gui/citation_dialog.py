"""Citation style picker for the GUI.

A packet can carry more than one citation format at once - check every style
you want and ``write_packet`` emits a reference + in-text file per style
(plus one shared BibTeX file, since that format doesn't vary by style).
"""
from __future__ import annotations

from urllib.parse import quote

from PySide6 import QtWidgets

REQUEST_EMAIL = "chimpworks@rook.works"
REQUEST_SUBJECT = "FUNCTION REQUEST-ADDITIONAL CITATION"

# (style key used by chimpworks.render.citation, display label)
STYLES = [
    ("apa", "APA 7"),
    ("mla", "MLA 9"),
    ("chicago", "Chicago (notes-bibliography)"),
]


class CitationStylesDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, selected: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Citation styles")
        self.setModal(True)
        self._checks: dict[str, QtWidgets.QCheckBox] = {}
        self._build(selected or ["apa"])

    def _build(self, selected: list[str]) -> None:
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        blurb = QtWidgets.QLabel(
            "Pick every format you want written to the research packet. "
            "Each checked style gets its own reference + in-text file."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color:#9aa3ad;")
        v.addWidget(blurb)

        for key, label in STYLES:
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(key in selected)
            self._checks[key] = cb
            v.addWidget(cb)

        v.addSpacing(4)

        mailto = (
            f"mailto:{REQUEST_EMAIL}?subject={quote(REQUEST_SUBJECT)}"
        )
        request = QtWidgets.QLabel(
            f'Not seeing your citation style needs? '
            f'<a href="{mailto}">Send a request</a>'
        )
        request.setOpenExternalLinks(True)
        request.setStyleSheet("color:#6b7280; font-size:11px;")
        v.addWidget(request)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _accept(self) -> None:
        if not self.selected_styles():
            QtWidgets.QMessageBox.warning(
                self, "Citation styles", "Check at least one style, or Cancel."
            )
            return
        self.accept()

    def selected_styles(self) -> list[str]:
        return [key for key, cb in self._checks.items() if cb.isChecked()]
