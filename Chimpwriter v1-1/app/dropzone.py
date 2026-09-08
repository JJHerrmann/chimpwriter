from __future__ import annotations

import re
from dataclasses import dataclass
from PySide6 import QtCore, QtGui, QtWidgets

from app.youtube import find_first_youtube_url

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


@dataclass
class DropPayload:
    kind: str
    value: str
    raw_text: str = ""


class DropZoneWindow(QtWidgets.QWidget):
    dropped = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlag(QtCore.Qt.WindowDoesNotAcceptFocus, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAcceptDrops(True)
        self.setFixedSize(360, 160)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("DropZone")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title = QtWidgets.QLabel("Drop URL or file to transcribe")
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.status = QtWidgets.QLabel("")
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.status)
        self._set_idle_style()

    def _set_idle_style(self) -> None:
        self.setStyleSheet(
            "QWidget#DropZone { background: #1f2227; color: #f0f0f0; border: 2px dashed #5c6570; border-radius: 12px; }"
            "QLabel { font-size: 14px; }"
        )

    def _set_drag_style(self) -> None:
        self.setStyleSheet(
            "QWidget#DropZone { background: #2a2f36; color: #ffffff; border: 2px solid #7aa2ff; border-radius: 12px; }"
            "QLabel { font-size: 14px; }"
        )

    def show_near_cursor(self) -> None:
        cursor_pos = QtGui.QCursor.pos()
        screen = QtWidgets.QApplication.screenAt(cursor_pos) or QtWidgets.QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = min(max(cursor_pos.x() - self.width() // 2, geom.left()), geom.right() - self.width())
            y = min(max(cursor_pos.y() - self.height() // 2, geom.top()), geom.bottom() - self.height())
            self.move(x, y)
        self.show()
        self.raise_()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()
            self._set_drag_style()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:
        self._set_idle_style()
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        self._set_idle_style()
        mime = event.mimeData()
        payload = None

        if mime.hasUrls():
            urls = mime.urls()
            if urls:
                url = urls[0]
                if url.isLocalFile():
                    payload = DropPayload(kind="file", value=url.toLocalFile())
                else:
                    payload = DropPayload(kind="text", value=url.toString(), raw_text=url.toString())
        elif mime.hasText():
            text = mime.text()
            yt = find_first_youtube_url(text)
            if yt:
                payload = DropPayload(kind="youtube", value=yt, raw_text=text)
            else:
                urls = URL_RE.findall(text)
                if urls:
                    payload = DropPayload(kind="text", value=urls[0], raw_text=text)
                else:
                    payload = DropPayload(kind="text", value=text.strip(), raw_text=text)

        if payload:
            self.status.setText("Starting...")
            self.dropped.emit(payload)
            QtCore.QTimer.singleShot(2000, self.hide)
            event.acceptProposedAction()
        else:
            event.ignore()
