"""Barre supérieure (section 07) : logo à gauche ; à droite, repères discrets
(nombre de concerts, date du jour) puis l'engrenage des paramètres (Q7)."""

from __future__ import annotations

from PySide6 import QtCore
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget

from scenix16.paths import resource
from scenix16.ui.theme import tokens as t

LOGO_HEIGHT = 30
GEAR_SIZE = 36


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


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(t.TOP_BAR_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        self.logo = LogoLabel(resource("logos", "scenix16.png"), LOGO_HEIGHT)
        layout.addWidget(self.logo)
        layout.addStretch(1)

        self.concerts_chip = QLabel(objectName="TopChip")
        self.date_chip = QLabel(objectName="TopChip")
        for chip in (self.concerts_chip, self.date_chip):
            chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(chip, 0, Qt.AlignVCenter)

        self.gear_button = QToolButton(objectName="GearButton")
        self.gear_button.setIcon(QIcon(str(resource("icons", "settings.svg"))))
        self.gear_button.setIconSize(QSize(20, 20))
        self.gear_button.setFixedSize(GEAR_SIZE, GEAR_SIZE)
        self.gear_button.setToolTip("Paramètres")
        self.gear_button.setAccessibleName("Paramètres")
        layout.addWidget(self.gear_button)

    def set_markers(self, concerts: str, today: str) -> None:
        self.concerts_chip.setText(concerts)
        self.date_chip.setText(today)

    def set_gear_active(self, active: bool) -> None:
        self.gear_button.setProperty("active", active)
        self.gear_button.style().polish(self.gear_button)
