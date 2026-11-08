"""Aperçu au survol d'un concert (Design Book v0.42, D64).

Panneau conçu comme une extension de la carte : fond relevé, bordure line,
rayon 6 px, repère de groupe en tête, mêmes polices. Contenu, par ordre
d'importance : adresse et état ; nom complet sur plusieurs lignes, jamais
tronqué ; lieu complet ; date en toutes lettres et compte à rebours ; nombre
de titres.

Le panneau ne prend jamais le focus et laisse passer la souris : c'est une
simple prévisualisation (la fiche s'ouvre au clic, 2.7). Le déclenchement
(350 ms), la fermeture et la position sont décidés par la page ; la position
est calculée par preview_geometry, en coordonnées logiques Qt (indépendantes
de la mise à l'échelle de Windows).
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from scenix16.services.dashboard_service import PreviewContent
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY

PREVIEW_DELAY_MS = 350
FADE_MS = 120
GAP = 6            # écart avec la carte
EDGE = 8           # marge minimale avec les bords de la zone centrale
MIN_WIDTH = 300
MAX_WIDTH = 420
PAD_X, PAD_TOP, PAD_BOTTOM = 14, 16, 12
LINE_GAP = 6
RADIUS = 6
MARKER_H = 3
MARKER_INSET = 12


def _font(family: str, px: int, weight=QFont.Weight.Normal, spacing: float = 0.0,
          caps: bool = False) -> QFont:
    font = QFont(family)
    font.setPixelSize(px)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    if caps:
        font.setCapitalization(QFont.AllUppercase)
    return font


def address_font() -> QFont:
    return _font(MONO_FAMILY, 11, QFont.Weight.Medium)


def tag_font() -> QFont:
    return _font(LABEL_FAMILY, 10, QFont.Weight.DemiBold, 1.2, caps=True)


def name_font() -> QFont:
    return _font(LABEL_FAMILY, 18, QFont.Weight.DemiBold)


def venue_font() -> QFont:
    return _font("Segoe UI", 13)


def date_font() -> QFont:
    return _font("Segoe UI", 12)


def mono_font(px: int = 12) -> QFont:
    return _font(MONO_FAMILY, px, QFont.Weight.Medium)


def preview_width(card_width: int, area_width: int) -> int:
    """Au moins la largeur de la carte, entre 300 et 420 px, et jamais plus que la zone."""
    width = min(max(card_width, MIN_WIDTH), MAX_WIDTH)
    return max(1, min(width, area_width - 2 * EDGE))


def preview_geometry(anchor: QRect, size: QSize, area: QRect, avoid: QRect | None = None) -> QRect:
    """Position de l'aperçu (coordonnées logiques de la zone `area`).

    Sous la carte, aligné sur son bord gauche, 6 px plus bas ; au-dessus si la
    place manque en bas, sauf si cela couvrait `avoid` (la touche survolée) ;
    recalé horizontalement pour rester dans la zone avec 8 px de marge. Si ni le
    dessus ni le dessous ne conviennent, le côté le plus grand est retenu et
    l'aperçu est recalé dans la zone (cas extrême : fenêtre très basse).
    """
    w, h = size.width(), size.height()
    left_min, left_max = area.left() + EDGE, area.left() + area.width() - EDGE - w
    x = min(max(anchor.left(), left_min), max(left_min, left_max))
    top_min, bottom_max = area.top() + EDGE, area.top() + area.height() - EDGE
    below = anchor.top() + anchor.height() + GAP
    above = anchor.top() - GAP - h
    above_ok = above >= top_min and (avoid is None or not QRect(x, above, w, h).intersects(avoid))
    if below + h <= bottom_max:
        y = below
    elif above_ok:
        y = above
    else:
        room_below = bottom_max - below
        room_above = anchor.top() - GAP - top_min
        y = below if room_below >= room_above else above
        y = min(max(y, top_min), max(top_min, bottom_max - h))
    return QRect(x, y, w, h)


class ConcertPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConcertPreview")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.content: PreviewContent | None = None
        self.group_color = QColor(t.KEY_RED)
        self.number: int | None = None          # paire montrée (1 à 16)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    # --- contenu et dimensions ---------------------------------------------
    def set_content(self, content: PreviewContent, group_color: str, width: int) -> None:
        self.content = content
        self.group_color = QColor(group_color)
        self.resize(width, self.height_for(width))
        self.update()

    def _text_width(self, width: int) -> int:
        return max(1, width - 2 * PAD_X)

    def _wrapped_height(self, font: QFont, text: str, width: int) -> int:
        if not text:
            return 0
        fm = QFontMetrics(font)
        return fm.boundingRect(QRect(0, 0, self._text_width(width), 10_000),
                               int(Qt.TextWordWrap), text).height()

    def height_for(self, width: int) -> int:
        c = self.content
        h = PAD_TOP + QFontMetrics(tag_font()).height() + 4 + LINE_GAP
        h += self._wrapped_height(name_font(), c.name, width) + LINE_GAP
        if c.venue:
            h += self._wrapped_height(venue_font(), c.venue, width) + LINE_GAP
        h += max(QFontMetrics(date_font()).height(), QFontMetrics(mono_font()).height()) + 4
        h += QFontMetrics(mono_font(11)).height()
        return h + PAD_BOTTOM

    # --- apparition ----------------------------------------------------------
    def present(self, geometry: QRect, animated: bool) -> None:
        self.setGeometry(geometry)
        self.raise_()
        self._fade.stop()
        if animated:
            self._effect.setOpacity(0.0)
            self.show()
            self._fade.start()
        else:
            self._effect.setOpacity(1.0)
            self.show()

    def dismiss(self) -> None:
        self._fade.stop()
        self.hide()
        self.number = None

    def finish_fade(self) -> None:
        """Animations réduites en cours de fondu (2.8c) : pleine opacité immédiate."""
        if self._fade.state() == QPropertyAnimation.Running:
            self._fade.stop()
            self._effect.setOpacity(1.0)

    def fading(self) -> bool:
        return self._fade.state() == QPropertyAnimation.Running

    # --- dessin --------------------------------------------------------------
    def paintEvent(self, event):
        c = self.content
        if c is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(t.LINE), 1))
        p.setBrush(QColor(t.RAISED))
        p.drawRoundedRect(box, RADIUS, RADIUS)

        # repère de groupe en tête, comme sur la carte
        path = QPainterPath()
        path.addRoundedRect(QRectF(MARKER_INSET, 0, self.width() - 2 * MARKER_INSET, MARKER_H + 1), 2, 2)
        p.setPen(Qt.NoPen)
        p.setBrush(self.group_color)
        p.drawPath(path)

        x, w = PAD_X, self._text_width(self.width())
        y = PAD_TOP

        # adresse et état
        tm = QFontMetrics(tag_font())
        tag_w, tag_h = tm.horizontalAdvance(c.tag) + 12, tm.height() + 4
        p.setFont(address_font())
        p.setPen(QColor(t.MUTED))
        p.drawText(QRectF(x, y, w - tag_w - 8, tag_h), Qt.AlignLeft | Qt.AlignVCenter, c.address)
        tag_rect = QRectF(x + w - tag_w, y, tag_w, tag_h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.BRAND if c.emphasized else t.CELL))
        p.drawRoundedRect(tag_rect, 3, 3)
        p.setFont(tag_font())
        p.setPen(QColor(t.INK if c.emphasized else t.TEXT))
        p.drawText(tag_rect, Qt.AlignCenter, c.tag)
        y += tag_h + LINE_GAP

        # nom complet, sur plusieurs lignes, jamais tronqué
        p.setFont(name_font())
        p.setPen(QColor(t.SILK))
        nh = self._wrapped_height(name_font(), c.name, self.width())
        p.drawText(QRectF(x, y, w, nh), Qt.AlignLeft | Qt.TextWordWrap, c.name)
        y += nh + LINE_GAP

        # lieu complet
        if c.venue:
            p.setFont(venue_font())
            p.setPen(QColor(t.TEXT))
            vh = self._wrapped_height(venue_font(), c.venue, self.width())
            p.drawText(QRectF(x, y, w, vh), Qt.AlignLeft | Qt.TextWordWrap, c.venue)
            y += vh + LINE_GAP

        # date en toutes lettres et compte à rebours
        dh = max(QFontMetrics(date_font()).height(), QFontMetrics(mono_font()).height())
        p.setFont(mono_font())
        p.setPen(QColor(t.TEXT))
        cw = QFontMetrics(mono_font()).horizontalAdvance(c.countdown) + 2
        p.drawText(QRectF(x + w - cw, y, cw, dh), Qt.AlignRight | Qt.AlignVCenter, c.countdown)
        p.setFont(date_font())
        p.setPen(QColor(t.MUTED))
        p.drawText(QRectF(x, y, w - cw - 8, dh), Qt.AlignLeft | Qt.AlignVCenter, c.date)
        y += dh + 4

        # nombre de titres
        p.setFont(mono_font(11))
        p.setPen(QColor(t.DIM))
        p.drawText(QRectF(x, y, w, QFontMetrics(mono_font(11)).height()),
                   Qt.AlignLeft | Qt.AlignVCenter, c.tracks)
        p.end()
