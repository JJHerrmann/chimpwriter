"""Terminology library editor for the GUI.

Edits the same ``lexicon.toml`` the CLI's ``chimpworks terms`` touches:
a list of hotword terms (biases the ASR) and an ordered map of text fixes
(applied after). Prefix a fix's *match* with ``re:`` for a regex.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..core.lexicon import DEFAULT_LEXICON, read_raw, save_lexicon


class LexiconDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self._path = path or DEFAULT_LEXICON
        self.setWindowTitle("Terminology library")
        self.setModal(True)
        self.resize(560, 460)
        self._build()
        self._load()

    def _build(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        blurb = QtWidgets.QLabel(
            "<b>Terms</b> are fed to the transcriber as hints (spell <i>n8n</i>, "
            "<i>LangChain</i>… right the first time).<br><b>Fixes</b> replace text "
            "afterwards — the match is a whole word unless it starts with "
            "<code>re:</code> (regex). Fixes run top to bottom."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color:#9aa3ad;")
        v.addWidget(blurb)

        tabs = QtWidgets.QTabWidget()

        # --- Terms tab ---
        tw = QtWidgets.QWidget()
        tl = QtWidgets.QVBoxLayout(tw)
        self.terms_list = QtWidgets.QListWidget()
        self.terms_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        row = QtWidgets.QHBoxLayout()
        self.term_edit = QtWidgets.QLineEdit()
        self.term_edit.setPlaceholderText("new term, then Enter or Add")
        self.term_edit.returnPressed.connect(self._add_term)
        add_t = QtWidgets.QPushButton("Add")
        add_t.clicked.connect(self._add_term)
        del_t = QtWidgets.QPushButton("Remove selected")
        del_t.clicked.connect(self._del_terms)
        row.addWidget(self.term_edit, 1)
        row.addWidget(add_t)
        row.addWidget(del_t)
        tl.addWidget(self.terms_list, 1)
        tl.addLayout(row)
        tabs.addTab(tw, "Terms")

        # --- Fixes tab ---
        fw = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(fw)
        self.fix_table = QtWidgets.QTableWidget(0, 2)
        self.fix_table.setHorizontalHeaderLabels(["match  (re: = regex)", "replace with"])
        self.fix_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.fix_table.verticalHeader().setVisible(False)
        frow = QtWidgets.QHBoxLayout()
        add_f = QtWidgets.QPushButton("Add row")
        add_f.clicked.connect(lambda: self._add_fix_row("", ""))
        del_f = QtWidgets.QPushButton("Remove selected row")
        del_f.clicked.connect(self._del_fix_row)
        frow.addWidget(add_f)
        frow.addWidget(del_f)
        frow.addStretch(1)
        fl.addWidget(self.fix_table, 1)
        fl.addLayout(frow)
        tabs.addTab(fw, "Fixes")

        v.addWidget(tabs, 1)

        self.path_hint = QtWidgets.QLabel(str(self._path))
        self.path_hint.setStyleSheet("color:#6b7280; font-size:11px;")
        v.addWidget(self.path_hint)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._save_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    # -- data --------------------------------------------------------------
    def _load(self) -> None:
        terms, fixes, p = read_raw(self._path)
        self._path = p
        self.path_hint.setText(str(p))
        self.terms_list.addItems(terms)
        for k, val in fixes.items():
            self._add_fix_row(k, val)

    def _add_term(self) -> None:
        t = self.term_edit.text().strip()
        if not t:
            return
        existing = {self.terms_list.item(i).text().lower()
                    for i in range(self.terms_list.count())}
        if t.lower() not in existing:
            self.terms_list.addItem(t)
        self.term_edit.clear()

    def _del_terms(self) -> None:
        for item in self.terms_list.selectedItems():
            self.terms_list.takeItem(self.terms_list.row(item))

    def _add_fix_row(self, match: str, repl: str) -> None:
        r = self.fix_table.rowCount()
        self.fix_table.insertRow(r)
        self.fix_table.setItem(r, 0, QtWidgets.QTableWidgetItem(match))
        self.fix_table.setItem(r, 1, QtWidgets.QTableWidgetItem(repl))

    def _del_fix_row(self) -> None:
        rows = sorted({i.row() for i in self.fix_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.fix_table.removeRow(r)

    def _save_accept(self) -> None:
        terms = [self.terms_list.item(i).text() for i in range(self.terms_list.count())]
        fixes: dict[str, str] = {}
        for r in range(self.fix_table.rowCount()):
            k_item = self.fix_table.item(r, 0)
            v_item = self.fix_table.item(r, 1)
            k = (k_item.text() if k_item else "").strip()
            val = v_item.text() if v_item else ""
            if k:
                fixes[k] = val
        save_lexicon(terms, fixes, self._path)
        self.accept()
