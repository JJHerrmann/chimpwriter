from __future__ import annotations

from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


def _is_dark_theme() -> bool:
    palette = QtWidgets.QApplication.palette()
    return palette.color(QtGui.QPalette.Window).value() < 128


def load_app_icon() -> QtGui.QIcon:
    assets = _assets_dir()
    svg = assets / "chimpwriter.svg"
    dark = assets / "chimpwriter_dark.png"
    light = assets / "chimpwriter_light.png"
    ico = assets / "chimpwriter.ico"
    if svg.exists():
        return QtGui.QIcon(str(svg))
    if _is_dark_theme() and dark.exists():
        return QtGui.QIcon(str(dark))
    if light.exists():
        return QtGui.QIcon(str(light))
    if ico.exists():
        return QtGui.QIcon(str(ico))
    return QtGui.QIcon()


class TrayController(QtCore.QObject):
    def __init__(self, app: QtWidgets.QApplication, main_window, dropzone, parent=None):
        super().__init__(parent)
        self.app = app
        self.main_window = main_window
        self.dropzone = dropzone
        self.tray = QtWidgets.QSystemTrayIcon()
        self.tray.setIcon(load_app_icon())
        self.tray.setToolTip("Chimpwriter")

        self.menu = QtWidgets.QMenu()
        self.action_open = self.menu.addAction("Open main window")
        self.action_open.triggered.connect(self.show_main)

        self.action_drop = self.menu.addAction("Quick Drop Zone")
        self.action_drop.setCheckable(True)
        self.action_drop.triggered.connect(self.toggle_dropzone)

        self.action_settings = self.menu.addAction("Settings")
        self.action_settings.triggered.connect(self.open_settings)

        self.menu.addSeparator()
        self.action_quit = self.menu.addAction("Quit")
        self.action_quit.triggered.connect(self.quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self.tray.show()

    def _on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick):
            self.toggle_dropzone(True)

    def show_main(self) -> None:
        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def toggle_dropzone(self, checked: bool | None = None) -> None:
        if checked is None:
            checked = not self.dropzone.isVisible()
        if checked:
            self.dropzone.show_near_cursor()
        else:
            self.dropzone.hide()
        self.action_drop.setChecked(self.dropzone.isVisible())

    def open_settings(self) -> None:
        self.main_window.show_settings_dialog()

    def quit(self) -> None:
        self.tray.hide()
        self.app.quit()

