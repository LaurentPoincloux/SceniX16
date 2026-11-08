"""Grille des 16 emplacements (section 06, Q5, section 08).

- 2 × 8 (fenêtre de 1360 px effectifs et plus) : chaque carte couvre
  exactement deux colonnes de touches ; emplacements 1 à 8 sur la première
  rangée, 9 à 16 sur la seconde.
- 4 × 4 (fenêtre compacte, moins de 1360 px) : une rangée par groupe de
  couleur (1–4, 5–8, 9–12, 13–16).

Clavier (D65, Q11, Q15 — incrément 2.8b) : ← → carte active précédente ou suivante dans
l'ordre 1 à 16, INIT ignorées ; au bord, la page décide du passage à la banque voisine
(edge_reached). ↑ ↓ : même colonne, rangée voisine, selon la disposition affichée au moment
de l'appui (± 8 en 2 × 8, ± 4 en 4 × 4) ; ↑ depuis la première rangée demande la touche de
même numéro (key_requested) ; ↓ sur la dernière rangée, ou cible INIT : le focus reste en place.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QWidget

from scenix16.domain.dashboard import BASE_KEYS, key_group
from scenix16.ui.dashboard.sequencer import key_columns
from scenix16.ui.widgets.slot_card import MARGIN, SlotCard

COMPACT_BELOW = 1360    # largeur de fenêtre (px effectifs), section 08
ROW_GAP = 8
COMPACT_GAP = 8


class SlotGrid(QWidget):
    edge_reached = Signal(int)       # ← sur la première carte active (-1), → sur la dernière (+1)
    key_requested = Signal(int)      # ↑ depuis la première rangée : touche de même numéro

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SlotGrid")
        self.slots = [SlotCard(n, key_group(n), self) for n in range(1, BASE_KEYS + 1)]
        for slot in self.slots:
            slot.setMinimumSize(0, 0)
            slot.navigate.connect(lambda delta, s=slot: self.move_focus(s, delta))
            slot.navigate_rows.connect(lambda delta, s=slot: self.move_rows(s, delta))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode = "2x8"
        self._apply_geometry()

    def card_height(self) -> int:
        return self.slots[0].content_height()

    def mode_for(self, window_width: int) -> str:
        return "2x8" if window_width >= COMPACT_BELOW else "4x4"

    def sizeHint(self) -> QSize:
        rows = 2 if self.mode == "2x8" else 4
        return QSize(800, rows * self.card_height() + (rows - 1) * ROW_GAP + 2 * MARGIN)

    def resizeEvent(self, event):
        self._apply_geometry()
        super().resizeEvent(event)

    def refresh_mode(self) -> None:
        self._apply_geometry()

    def card_rects(self) -> list[QRectF]:
        """Rectangle de chaque carte (hors anneau), dans le repère de la grille."""
        h = self.card_height()
        rects = []
        if self.mode == "2x8":
            cols = key_columns(self.width())
            for j in range(BASE_KEYS):
                row, c = divmod(j, 8)
                left = cols.left[2 * c]
                right = cols.right(2 * c + 1)
                top = MARGIN + row * (h + ROW_GAP)
                rects.append(QRectF(left, top, right - left, h))
        else:
            usable = self.width() - 2 * MARGIN
            w = (usable - 3 * COMPACT_GAP) / 4
            for j in range(BASE_KEYS):
                row, c = divmod(j, 4)
                rects.append(QRectF(MARGIN + c * (w + COMPACT_GAP),
                                    MARGIN + row * (h + ROW_GAP), w, h))
        return rects

    def _apply_geometry(self) -> None:
        window = self.window()
        self.mode = self.mode_for(window.width() if window is not self else self.width())
        rows = 2 if self.mode == "2x8" else 4
        height = rows * self.card_height() + (rows - 1) * ROW_GAP + 2 * MARGIN
        if self.height() != height:
            self.setFixedHeight(height)
        for slot, rect in zip(self.slots, self.card_rects()):
            slot.setGeometry(round(rect.left() - MARGIN), round(rect.top() - MARGIN),
                             round(rect.width()) + 2 * MARGIN, round(rect.height()) + 2 * MARGIN)

    # --- clavier (D65) ---------------------------------------------------------------
    def columns_count(self) -> int:
        return 8 if self.mode == "2x8" else 4

    def move_focus(self, slot: SlotCard, delta: int) -> None:
        """← → : carte active voisine dans l'ordre 1 à 16 ; au bord, banque voisine (page)."""
        index = self.slots.index(slot) + delta
        while 0 <= index < len(self.slots):
            target = self.slots[index]
            if not target.is_init:
                target.setFocus(Qt.TabFocusReason)
                return
            index += delta
        self.edge_reached.emit(delta)

    def move_rows(self, slot: SlotCard, delta: int) -> None:
        """↑ ↓ : même colonne, rangée voisine ; jamais de changement de banque ni de bouclage."""
        target = slot.number + delta * self.columns_count()
        if target < 1:
            self.key_requested.emit(slot.number)          # ↑ depuis la première rangée
        elif target <= BASE_KEYS and not self.slots[target - 1].is_init:
            self.slots[target - 1].setFocus(Qt.TabFocusReason)
        # dernière rangée, ou cible INIT : le focus reste en place

    def focus_first(self, last: bool = False) -> bool:
        """Focus sur la première (ou la dernière) carte active ; False s'il n'y en a pas."""
        slots = reversed(self.slots) if last else self.slots
        for slot in slots:
            if not slot.is_init:
                slot.setFocus(Qt.TabFocusReason)
                return True
        return False
