"""Indicateur vers SETLISTS et état vide (section 06, D5, D22).

- Indicateur : « N concerts à venir sur le dashboard » et, à droite,
  « 2 sans date · 12 passés · 2 annulés dans SETLISTS → » ; masqué s'il n'y a
  rien à signaler.
- État vide (aucun concert à venir) : « Aucun concert à venir », explication,
  « Ouvrir SETLISTS → ».
Le lien vers SETLISTS est affiché mais inactif tant que l'écran n'existe pas
(arbitrage F).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from scenix16.domain.dashboard import DashboardView
from scenix16.services.dashboard_service import empty_state_text, indicator_parts

OPEN_SETLISTS = "Ouvrir SETLISTS →"
EMPTY_TITLE = "Aucun concert à venir"


class SetlistsIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SetlistsIndicator")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        self.left = QLabel(objectName="IndicatorText")
        self.link = QLabel(objectName="InactiveLink")
        layout.addWidget(self.left)
        layout.addStretch(1)
        layout.addWidget(self.link)

    def set_view(self, view: DashboardView | None) -> None:
        parts = indicator_parts(view)
        self.setVisible(parts is not None)
        if parts:
            self.left.setText(parts[0])
            self.link.setText(parts[1])


class EmptyState(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)
        self.title = QLabel(EMPTY_TITLE, objectName="EmptyTitle")
        self.text = QLabel(objectName="IndicatorText")
        self.text.setWordWrap(True)
        self.link = QLabel(OPEN_SETLISTS, objectName="InactiveLink")
        for label in (self.title, self.text, self.link):
            label.setAlignment(Qt.AlignHCenter)
            layout.addWidget(label)

    def set_view(self, view: DashboardView | None) -> None:
        self.setVisible(view is None or view.is_empty)
        self.text.setText(empty_state_text(view))
