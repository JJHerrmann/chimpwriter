"""Batch queue dialog for the GUI - Pro feature ("batch" in licensing.FEATURES).

Queues local files and/or YouTube URLs and runs them one after another
through the same pipeline as the single-source "Transcribe" button, reusing
whatever speed/language/topic/checkbox settings are currently set on the
main window. Mirrors the CLI's ``chimpworks batch`` (keep-going-on-error,
ok/fail count at the end) but adds a picker + a playlist-expand button
instead of requiring an ``@urls.txt`` file.
"""
from __future__ import annotations

from PySide6 import QtWidgets

from ..config import load_config
from ..core.pipeline import TranscribeOptions
from ..core.sources import expand_playlist
from ..render.packet import PacketOptions
from .worker import BatchWorker


class BatchDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent,
        *,
        t_opts: TranscribeOptions,
        p_opts: PacketOptions,
        out_root: str,
        hf_token: str = "",
        llm_key: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Batch queue")
        self.setModal(True)
        self.resize(580, 480)
        self._t_opts = t_opts
        self._p_opts = p_opts
        self._out_root = out_root
        self._hf_token = hf_token
        self._llm_key = llm_key
        self._worker: BatchWorker | None = None
        self._n = 0
        self._build()

    def _build(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        blurb = QtWidgets.QLabel(
            "Queue local files or YouTube URLs and run them one after another "
            "with the speed, language, topic, and checkboxes currently set on "
            "the main window. The model stays loaded between items."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color:#9aa3ad;")
        v.addWidget(blurb)

        self.queue_list = QtWidgets.QListWidget()
        v.addWidget(self.queue_list, 1)

        addrow = QtWidgets.QHBoxLayout()
        add_files = QtWidgets.QPushButton("Add files…")
        add_files.clicked.connect(self._add_files)
        del_btn = QtWidgets.QPushButton("Remove selected")
        del_btn.clicked.connect(self._remove_selected)
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self.queue_list.clear)
        addrow.addWidget(add_files)
        addrow.addWidget(del_btn)
        addrow.addWidget(clear_btn)
        addrow.addStretch(1)
        v.addLayout(addrow)

        urlrow = QtWidgets.QHBoxLayout()
        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText("YouTube video, playlist, or channel URL")
        self.url_edit.returnPressed.connect(self._add_url)
        add_url = QtWidgets.QPushButton("Add URL")
        add_url.clicked.connect(self._add_url)
        expand_btn = QtWidgets.QPushButton("Expand playlist…")
        expand_btn.clicked.connect(self._expand_playlist)
        urlrow.addWidget(self.url_edit, 1)
        urlrow.addWidget(add_url)
        urlrow.addWidget(expand_btn)
        v.addLayout(urlrow)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#9aa3ad;")
        v.addWidget(self.status_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        v.addWidget(self.progress)

        btnrow = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start batch")
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btnrow.addWidget(self.start_btn)
        btnrow.addWidget(self.cancel_btn)
        btnrow.addStretch(1)
        btnrow.addWidget(close_btn)
        v.addLayout(btnrow)

    # -- queue management ----------------------------------------------------
    def _add_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Add audio/video files")
        for p in paths:
            self.queue_list.addItem(p)

    def _add_url(self) -> None:
        url = self.url_edit.text().strip()
        if url:
            self.queue_list.addItem(url)
            self.url_edit.clear()

    def _expand_playlist(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return
        cfg = load_config()
        self.status_label.setText("Expanding playlist…")
        QtWidgets.QApplication.processEvents()
        try:
            urls = expand_playlist(url, cookies_from_browser=cfg.yt_cookies_from_browser)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, "Batch queue", f"Couldn't expand playlist: {exc}")
            self.status_label.setText("")
            return
        for u in urls:
            self.queue_list.addItem(u)
        self.url_edit.clear()
        self.status_label.setText(f"Added {len(urls)} item(s) from playlist.")

    def _remove_selected(self) -> None:
        for item in self.queue_list.selectedItems():
            self.queue_list.takeItem(self.queue_list.row(item))

    # -- run -------------------------------------------------------------------
    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.url_edit.setEnabled(not running)

    def _start(self) -> None:
        sources = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]
        if not sources:
            QtWidgets.QMessageBox.information(
                self, "Batch queue", "Add at least one file or URL first."
            )
            return
        self._n = len(sources)
        self._set_running(True)
        self.progress.setValue(0)
        self._worker = BatchWorker(
            sources=sources,
            out_root=self._out_root,
            t_opts=self._t_opts,
            p_opts=self._p_opts,
            hf_token=self._hf_token,
            llm_key=self._llm_key,
            parent=self,
        )
        self._worker.item_progressed.connect(self._on_item_progress)
        self._worker.item_logged.connect(self._on_item_logged)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.item_failed.connect(self._on_item_failed)
        self._worker.batch_finished.connect(self._on_batch_finished)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    def _mark(self, index: int, status: str) -> None:
        item = self.queue_list.item(index)
        if item:
            base = item.text().split("  —  ")[0]
            item.setText(f"{base}  —  {status}")

    def _on_item_progress(self, index: int, stage: str, fraction: float) -> None:
        self.status_label.setText(f"[{index + 1}/{self._n}] {stage}")
        if fraction >= 0:
            self.progress.setValue(int(fraction * 100))

    def _on_item_logged(self, index: int, _line: str) -> None:
        self._mark(index, "running…")

    def _on_item_done(self, index: int, _written: list) -> None:
        self._mark(index, "done")

    def _on_item_failed(self, index: int, error: str) -> None:
        self._mark(index, f"failed: {error}")

    def _on_batch_finished(self, ok: int, fail: int) -> None:
        self._set_running(False)
        self.progress.setValue(100)
        self.status_label.setText(f"Batch done — {ok} ok, {fail} failed.")
