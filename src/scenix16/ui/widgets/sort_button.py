"""Bouton de tri des concerts (Design Book v0.41, section 06 « Commande de classement »).

Un seul bouton à bascule, style secondaire : « DATE », flèche ▲ (plus ancien
d'abord) ou ▼ (plus récent d'abord), puis le libellé du sens affiché, en
capitales comme dans la maquette. Le nom accessible garde les formulations
de D12 et décrit l'action d'inversion. Le bouton ne change pas lui-même de
sens : il émet clicked, et l'appelant lui renvoie le sens retenu (set_order).

Hauteur 32 px, bordure line/strong, fond relevé au survol, anneau orange de
2 px au focus clavier (section 09). Accessible par Tab ; Espace ou Entrée.
Une pression maintenue sur Entrée ou Espace ne produit qu'une seule activation :
la répétition automatique du clavier est ignorée. Depuis 2.8b, cette règle est
commune à tous les boutons de l'application (ui.widgets.keyboard).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from scenix16.domain.dashboard import DEFAULT_SORT, SortOrder
from scenix16.services.dashboard_service import sort_accessible_name, sort_label
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY
from scenix16.ui.widgets.keyboard import fresh_activation, is_enter

BODY_HEIGHT = 32
RADIUS = 5
PAD_X = 12
GAP = 8
ARROW_W, ARROW_H = 8, 6
RING_OFFSET = 2
RING_WIDTH = 2
MARGIN = RING_OFFSET + RING_WIDTH
PREFIX = "DATE"


def _font(family: str, px: int, weight, spacing: float, caps: bool = False) -> QFont:
    font = QFont(family)
    font.setPixelSize(px)
    font.setWeight(weight)
    font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    if caps:
        font.setCapitalization(QFont.AllUppercase)
    return font


class SortButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SortButton")
        self.setFocusPolicy(Qt.TabFocus)          # pas d'anneau après un clic souris
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.order = DEFAULT_SORT
        self.set_order(DEFAULT_SORT)

    # --- état ----------------------------------------------------------------
    def set_order(self, order: SortOrder) -> None:
        self.order = order
        self.setText(sort_label(order))
        self.setAccessibleName(sort_accessible_name(order))
        self.updateGeometry()
        self.update()

    def display_text(self) -> str:
        """Texte visible, en capitales (maquette v0.41)."""
        return sort_label(self.order).upper()

    @property
    def arrow_up(self) -> bool:
        return self.order is SortOrder.OLDEST_FIRST

    # --- polices et dimensions --------------------------------------------------
    @staticmethod
    def prefix_font() -> QFont:
        return _font(MONO_FAMILY, 11, QFont.Weight.Medium, 1.0)

    @staticmethod
    def label_font() -> QFont:
        return _font(LABEL_FAMILY, 13, QFont.Weight.DemiBold, 1.0, caps=True)

    def _label_width(self) -> float:
        # largeur du plus long des deux libellés : le bouton ne change pas de taille
        fm = QFontMetricsF(self.label_font())
        return max(fm.horizontalAdvance(sort_label(o)) for o in SortOrder)

    def sizeHint(self) -> QSize:
        width = (PAD_X + QFontMetricsF(self.prefix_font()).horizontalAdvance(PREFIX) + GAP
                 + ARROW_W + GAP + self._label_width() + PAD_X)
        return QSize(round(width) + 2 * MARGIN, BODY_HEIGHT + 2 * MARGIN)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def body_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

    # --- clavier ---------------------------------------------------------------
    def keyPressEvent(self, event):
        if is_enter(event):
            if fresh_activation(self, event):  # une pression maintenue = une seule activation
                self.click()
            event.accept()
        else:
            super().keyPressEvent(event)         # Espace : comportement standard

    # --- dessin ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        body = self.body_rect()
        hovered = self.underMouse() or self.isDown()

        if self.hasFocus():
            ring = body.adjusted(-RING_OFFSET - 1, -RING_OFFSET - 1, RING_OFFSET + 1, RING_OFFSET + 1)
            p.setPen(QPen(QColor(t.BRAND), RING_WIDTH))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ring, RADIUS + RING_OFFSET, RADIUS + RING_OFFSET)

        p.setPen(QPen(QColor(t.LINE_STRONG), 1))
        p.setBrush(QColor(t.RAISED) if hovered else Qt.NoBrush)
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        x = body.left() + PAD_X
        mid = body.center().y()
        pf = self.prefix_font()
        p.setFont(pf)
        p.setPen(QColor(t.MUTED))
        pfm = QFontMetricsF(pf)
        p.drawText(QRectF(x, body.top(), pfm.horizontalAdvance(PREFIX) + 2, body.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, PREFIX)
        x += pfm.horizontalAdvance(PREFIX) + GAP

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.BRAND))
        top, bottom = mid - ARROW_H / 2, mid + ARROW_H / 2
        if self.arrow_up:
            tri = [QPointF(x, bottom), QPointF(x + ARROW_W, bottom), QPointF(x + ARROW_W / 2, top)]
        else:
            tri = [QPointF(x, top), QPointF(x + ARROW_W, top), QPointF(x + ARROW_W / 2, bottom)]
        p.drawPolygon(QPolygonF(tri))
        x += ARROW_W + GAP

        p.setFont(self.label_font())
        p.setPen(QColor(t.TEXT))
        p.drawText(QRectF(x, body.top(), body.right() - x, body.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, sort_label(self.order))
        p.end()
