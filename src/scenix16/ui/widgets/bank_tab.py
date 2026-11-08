"""Bouton de banque (Design Book v0.44, section 06, D44 à D47, D67 révisé en v0.44).

Bouton ON/OFF inspiré d'un équipement matériel, distinct des touches à plat (D57) —
seule exception assumée à D56, sans dégradé, halo ni lueur ; seule la lettre de la
banque est affichée (aucun texte ON ou OFF) :
- banque non sélectionnée, bouton éteint : fond vert sombre BANK_OFF_BG, bordure
  BANK_OFF_BORDER, lettre BANK_OFF_TEXT ; survol : BANK_OFF_HOVER ;
- banque sélectionnée, bouton allumé : fond vert lumineux BANK_ON_BG, bordure
  BANK_ON_BORDER, lettre en encre ; aucun filet crème (D63 le réserve aux touches) ;
- dans les deux cas, liseré clair de 1 px en haut et ombre fine de 1 px en bas ;
  la différence passe aussi par la luminosité, pas par la teinte seule ;
- focus clavier : anneau orange de 2 px (section 09), cumulable.
Banque vide : plate, bordure en pointillés, atténuée et inactive (ni survol,
ni focus, ni clic), comme une touche INIT. Dans l'état vide du dashboard, A reste sélectionnée sans être
active (arbitrage 8 de 2.6).

Clavier : ← et → demandent à la rangée de déplacer le focus (navigate) ;
Entrée ou Espace sélectionnent ; une pression maintenue sur Entrée ne produit
qu'une seule activation.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from scenix16.domain.dashboard import bank_label
from scenix16.services.dashboard_service import bank_accessible_name
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY
from scenix16.ui.widgets.keyboard import fresh_activation, is_enter

BODY_HEIGHT = 28
MIN_BODY_WIDTH = 32
PAD_X = 10
RADIUS = 5
TOP_LIGHT = (0.07, 0.18)  # liseré clair de 1 px en haut : éteint, allumé
BOTTOM_SHADOW = 0.45      # ombre fine de 1 px en bas
RING_OFFSET = 2
RING_WIDTH = 2
MARGIN = RING_OFFSET + RING_WIDTH
EMPTY_OPACITY = 0.55


def tab_font() -> QFont:
    font = QFont(LABEL_FAMILY)
    font.setPixelSize(13)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
    return font


class BankTab(QAbstractButton):
    navigate = Signal(int)          # ← (-1) / → (+1)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setText(bank_label(index))
        self.selected = False
        self.count = 0
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.NoFocus)          # la rangée gère le focus (un seul arrêt de Tab)
        self.set_state(False, 0)

    # --- état ----------------------------------------------------------------
    @property
    def occupied(self) -> bool:
        return self.count > 0

    def set_state(self, selected: bool, count: int) -> None:
        self.selected = selected
        self.count = count
        self.setEnabled(count > 0)
        self.setCursor(Qt.PointingHandCursor if count > 0 else Qt.ArrowCursor)
        self.setAccessibleName(bank_accessible_name(self.index, count))
        self.update()

    # --- dimensions -------------------------------------------------------------
    def sizeHint(self) -> QSize:
        text = QFontMetricsF(tab_font()).horizontalAdvance(self.text())
        body = max(MIN_BODY_WIDTH, round(text) + 2 * PAD_X)
        return QSize(body + 2 * MARGIN, BODY_HEIGHT + 2 * MARGIN)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def body_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

    # --- clavier -------------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Left:
            self.navigate.emit(-1)
        elif key == Qt.Key_Right:
            self.navigate.emit(1)
        elif is_enter(event):
            if fresh_activation(self, event):   # une seule activation par appui (2.8b)
                self.click()
            event.accept()
        else:
            super().keyPressEvent(event)      # Espace : comportement standard ; autres : remontent

    # --- dessin --------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        body = self.body_rect()
        if self.hasFocus():
            ring = body.adjusted(-RING_OFFSET - 1, -RING_OFFSET - 1, RING_OFFSET + 1, RING_OFFSET + 1)
            p.setPen(QPen(QColor(t.BRAND), RING_WIDTH))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ring, RADIUS + RING_OFFSET, RADIUS + RING_OFFSET)

        shape = body.adjusted(0.5, 0.5, -0.5, -0.5)
        if self.selected or self.isEnabled():
            # bouton ON/OFF : allumé si la banque est sélectionnée, éteint sinon (D67, v0.44).
            # La sélection prime : dans le dashboard vide, A reste sélectionnée sans être active
            # (arbitrage 8 de 2.6) et s'affiche donc allumée, tout en restant inactive.
            on = self.selected
            if on:
                border, fill, color = t.BANK_ON_BORDER, t.BANK_ON_BG, t.BANK_ON_TEXT
            else:
                border, color = t.BANK_OFF_BORDER, t.BANK_OFF_TEXT
                fill = t.BANK_OFF_HOVER if self.underMouse() else t.BANK_OFF_BG
            p.setPen(QPen(QColor(border), 1))
            p.setBrush(QColor(fill))
            p.drawRoundedRect(shape, RADIUS, RADIUS)
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(shape, RADIUS, RADIUS)
            p.setClipPath(clip)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, round(255 * TOP_LIGHT[1 if on else 0])))
            p.drawRect(QRectF(body.left(), body.top() + 1, body.width(), 1))
            p.restore()
            p.setPen(QPen(QColor(0, 0, 0, round(255 * BOTTOM_SHADOW)), 1))
            p.drawLine(QPointF(body.left() + RADIUS, body.bottom() + 0.5),
                       QPointF(body.right() - RADIUS, body.bottom() + 0.5))
            color = QColor(color)
        else:
            # banque vide non sélectionnée : plate, pointillés, atténuée (inchangé)
            p.setOpacity(EMPTY_OPACITY)
            p.setPen(QPen(QColor(t.LINE), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(shape, RADIUS, RADIUS)
            color = QColor(t.DIM)

        p.setFont(tab_font())
        p.setPen(color)
        p.drawText(body, Qt.AlignCenter, self.text())
        p.end()
