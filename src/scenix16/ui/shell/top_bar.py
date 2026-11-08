"""Barre supérieure (section 07, D59, D60) : 56 px.

À gauche, la barre de menus (« Fichier », « Aide ») ; à droite, l'afficheur
d'information (concerts à venir et passés, date de référence), puis l'engrenage
des paramètres à l'extrémité. Le logo est dans la barre latérale (D58).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from scenix16.paths import resource
from scenix16.services.dashboard_service import InfoReadout
from scenix16.ui.shell.info_display import InfoDisplay
from scenix16.ui.shell.menu_bar import AppMenuBar
from scenix16.ui.theme import tokens as t
from scenix16.ui.widgets.keyboard import enable_enter_activation

GEAR_SIZE = 36


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(t.TOP_BAR_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        self.menu_bar = AppMenuBar()
        layout.addWidget(self.menu_bar, 0, Qt.AlignVCenter)
        layout.addStretch(1)

        self.info = InfoDisplay()
        layout.addWidget(self.info, 0, Qt.AlignVCenter)

        self.gear_button = QToolButton(objectName="GearButton")
        self.gear_button.setIcon(QIcon(str(resource("icons", "settings.svg"))))
        self.gear_button.setIconSize(QSize(20, 20))
        self.gear_button.setFixedSize(GEAR_SIZE, GEAR_SIZE)
        self.gear_button.setToolTip("Paramètres")
        self.gear_button.setAccessibleName("Paramètres")
        self.gear_button.setFocusPolicy(Qt.TabFocus)          # clic : pas d'anneau (v0.45)
        enable_enter_activation(self.gear_button)             # Entrée = Espace (2.8b)
        layout.addWidget(self.gear_button)

    def set_readout(self, readout: InfoReadout) -> None:
        self.info.set_readout(readout)

    def set_gear_active(self, active: bool) -> None:
        self.gear_button.setProperty("active", active)
        self.gear_button.style().polish(self.gear_button)
