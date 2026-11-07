"""Grille des 16 emplacements (section 06, Q5, section 08).

- 2 × 8 (fenêtre de 1360 px effectifs et plus) : chaque carte couvre
  exactement deux colonnes de touches ; emplacements 1 à 8 sur la première
  rangée, 9 à 16 sur la seconde.
- 4 × 4 (fenêtre compacte, moins de 1360 px) : une rangée par groupe de
  couleur (1–4, 5–8, 9–12, 13–16).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize
from PySide6.QtWidgets import QSizePolicy, QWidget

from scenix16.domain.dashboard import BASE_KEYS, key_group
from scenix16.ui.dashboard.sequencer import key_columns
from scenix16.ui.widgets.slot_card import MARGIN, SlotCard

COMPACT_BELOW = 1360    # largeur de fenêtre (px effectifs), section 08
ROW_GAP = 8
COMPACT_GAP = 8


class SlotGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SlotGrid")
        self.slots = [SlotCard(n, key_group(n), self) for n in range(1, BASE_KEYS + 1)]
        for slot in self.slots:
            slot.setMinimumSize(0, 0)
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
