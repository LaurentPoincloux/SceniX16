"""Barre d'état (section 07) : informations passives seulement.

Contenu du Design Book : « SceniX16 · N titres au catalogue · M setlists ».
Le diagnostic technique (version, Python, Qt, échelle) n'apparaît que lorsque
le programme tourne depuis les sources, jamais dans l'exécutable portable.
"""

from __future__ import annotations

import platform

from PySide6 import QtCore
from PySide6.QtWidgets import QLabel, QStatusBar

from scenix16 import __version__
from scenix16.paths import is_frozen
from scenix16.ui.theme import tokens as t


class StatusLine(QStatusBar):
    def __init__(self, show_diagnostic: bool | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusLine")
        self.setSizeGripEnabled(True)
        self.setFixedHeight(t.STATUS_BAR_HEIGHT)
        self.parts: list[QLabel] = []
        self.diagnostic: QLabel | None = None
        if show_diagnostic is None:
            show_diagnostic = not is_frozen()
        if show_diagnostic:
            self.diagnostic = QLabel(objectName="DiagnosticLabel")
            self.addPermanentWidget(self.diagnostic)

    def set_parts(self, parts: list[str]) -> None:
        for label in self.parts:
            self.removeWidget(label)
            label.deleteLater()
        self.parts = []
        for text in parts:
            label = QLabel(text, objectName="StatusPart")
            self.addWidget(label)
            self.parts.append(label)

    def texts(self) -> list[str]:
        return [label.text() for label in self.parts]

    def update_diagnostic(self, scale: float) -> None:
        if self.diagnostic is not None:
            self.diagnostic.setText(
                f"dév. · {__version__} · Python {platform.python_version()} · "
                f"Qt {QtCore.qVersion()} · échelle {scale:g}")
