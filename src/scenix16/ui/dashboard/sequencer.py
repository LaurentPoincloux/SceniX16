"""Rangée des 16 touches de base (sections 05 et 07).

Une seule rangée de 16 StepKey en 4 groupes de 4 (rouge, orange, jaune,
blanc). Écart visuel de 8 px entre deux touches, de 20 px entre deux
groupes. Largeur du corps calculée selon la place : bornée à 96 px ; sous
44 px seulement tant que le rail n'est pas repliable (arbitrage A ; barre repliée reportée
après les phases 1 et 2, D58).
La géométrie des colonnes est partagée avec la grille des emplacements, qui
s'aligne dessus en 2 × 8.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QWidget

from scenix16.domain.dashboard import BASE_KEYS, key_group
from scenix16.ui.widgets.step_key import ASPECT, MARGIN, MAX_WIDTH, StepKey

KEY_GAP = 8
GROUP_GAP = 20
GAPS_TOTAL = 12 * KEY_GAP + 3 * GROUP_GAP   # 156 px entre les 16 corps


@dataclass(frozen=True)
class KeyColumns:
    """Position horizontale des 16 corps de touche dans une largeur donnée."""

    left: tuple[float, ...]
    body_width: float

    def right(self, index: int) -> float:
        return self.left[index] + self.body_width


def key_columns(width: float) -> KeyColumns:
    usable = max(0.0, width - 2 * MARGIN)
    body = min(MAX_WIDTH, max(1.0, (usable - GAPS_TOTAL) / BASE_KEYS))
    total = BASE_KEYS * body + GAPS_TOTAL
    x = MARGIN + max(0.0, (usable - total) / 2)
    lefts = []
    for i in range(BASE_KEYS):
        lefts.append(x)
        x += body + (GROUP_GAP if i % 4 == 3 else KEY_GAP)
    return KeyColumns(tuple(lefts), body)


class Sequencer(QWidget):
    edge_reached = Signal(int)       # ← sur la première touche active (-1), → sur la dernière (+1)
    card_requested = Signal(int)     # ↓ sur une touche : carte de même numéro (D65)
    geometry_changed = Signal()      # colonnes recalculées (alignement des onglets)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sequencer")
        self.keys: list[StepKey] = []
        for n in range(1, BASE_KEYS + 1):
            key = StepKey(n, key_group(n), self)
            key.setMinimumSize(0, 0)          # taille imposée par la rangée (arbitrage A)
            key.navigate.connect(lambda delta, k=key: self.move_focus(k, delta))
            key.down_requested.connect(lambda k=key: self.card_requested.emit(k.number))
            self.keys.append(key)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.columns = key_columns(800)
        self._apply_geometry()

    def heightForWidth(self, width: int) -> int:
        return round(key_columns(width).body_width * ASPECT) + 2 * MARGIN

    def hasHeightForWidth(self) -> bool:
        return True

    def sizeHint(self) -> QSize:
        return QSize(800, self.heightForWidth(800))

    def resizeEvent(self, event):
        self._apply_geometry()
        super().resizeEvent(event)

    def _apply_geometry(self) -> None:
        self.columns = key_columns(self.width())
        body = self.columns.body_width
        height = round(body * ASPECT) + 2 * MARGIN
        if self.height() != height:
            self.setFixedHeight(height)
        for key, left in zip(self.keys, self.columns.left):
            key.setGeometry(round(left - MARGIN), 0, round(body) + 2 * MARGIN, height)
        self.geometry_changed.emit()

    # --- clavier (D9) --------------------------------------------------------
    def move_focus(self, key: StepKey, delta: int) -> None:
        """Passe à la touche active suivante dans la direction donnée ; ignore les INIT.

        Au bord de la rangée, la page décide du passage à la banque voisine (D46).
        """
        index = self.keys.index(key) + delta
        while 0 <= index < len(self.keys):
            target = self.keys[index]
            if not target.is_init:
                target.setFocus()
                return
            index += delta
        self.edge_reached.emit(delta)

    def focus_first(self, last: bool = False) -> bool:
        """Focus sur la première (ou la dernière) touche active ; False s'il n'y en a pas."""
        keys = reversed(self.keys) if last else self.keys
        for key in keys:
            if not key.is_init:
                key.setFocus(Qt.TabFocusReason)
                return True
        return False
