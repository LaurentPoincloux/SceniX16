"""Logo affiché à une hauteur donnée, sans déformation, net à toute mise à l'échelle (Q7)."""

from __future__ import annotations

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


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
        scaled = self._source.scaledToHeight(round(self._height * ratio), Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        self.setPixmap(scaled)
        self.setFixedSize(round(scaled.width() / ratio), round(scaled.height() / ratio))

    def changeEvent(self, event):  # recalcul net lors d'un changement d'écran/DPI
        if event.type() == QtCore.QEvent.Type.DevicePixelRatioChange:
            self._refresh()
        super().changeEvent(event)
