"""Fenêtre principale – socle de la phase 0.

Contient seulement la barre supérieure avec le logo SceniX16, une zone
centrale vide et une barre d'état de diagnostic. Le dashboard (touches,
emplacements) arrivera en phase 2.
"""

import platform

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from scenix16 import __version__
from scenix16.paths import resource
from scenix16.ui.theme import tokens as t

LOGO_HEIGHT = 30


class LogoLabel(QLabel):
    """Affiche une image ajustée à une hauteur donnée, sans déformation."""

    def __init__(self, path, height: int, parent=None):
        super().__init__(parent)
        self.setObjectName("Logo")
        self._source = QPixmap(str(path))
        self._height = height
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._refresh()

    def source_is_valid(self) -> bool:
        return not self._source.isNull()

    def _refresh(self) -> None:
        if self._source.isNull():
            self.setText("SceniX16")
            return
        ratio = self.devicePixelRatioF()
        scaled = self._source.scaledToHeight(
            round(self._height * ratio), Qt.SmoothTransformation
        )
        scaled.setDevicePixelRatio(ratio)
        self.setPixmap(scaled)
        self.setFixedSize(
            round(scaled.width() / ratio), round(scaled.height() / ratio)
        )

    def changeEvent(self, event):  # recalcul net lors d'un changement d'écran/DPI
        if event.type() == QtCore.QEvent.Type.DevicePixelRatioChange:
            self._refresh()
        super().changeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SceniX16")
        self.setMinimumSize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
        self.resize(t.WINDOW_DEFAULT_WIDTH, t.WINDOW_DEFAULT_HEIGHT)

        body = QWidget(objectName="Body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = QWidget(objectName="TopBar")
        top_bar.setFixedHeight(t.TOP_BAR_HEIGHT)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        self.logo = LogoLabel(resource("logos", "scenix16.png"), LOGO_HEIGHT)
        top_layout.addWidget(self.logo)
        top_layout.addStretch(1)
        layout.addWidget(top_bar)

        placeholder = QLabel("SOCLE TECHNIQUE · PHASE 0", objectName="Placeholder")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder, 1)

        self.setCentralWidget(body)

        status = QStatusBar()
        status.setSizeGripEnabled(True)
        status.setFixedHeight(t.STATUS_BAR_HEIGHT)
        self.setStatusBar(status)
        self._diagnostic = QLabel()
        status.addWidget(self._diagnostic)
        self.update_diagnostic()

    def update_diagnostic(self) -> None:
        screen = self.screen()
        scale = screen.devicePixelRatio() if screen else 1.0
        self._diagnostic.setText(
            f"SceniX16 {__version__} · Python {platform.python_version()} · "
            f"Qt {QtCore.qVersion()} · échelle {scale:g}"
        )

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.DevicePixelRatioChange:
            self.update_diagnostic()
        super().changeEvent(event)
