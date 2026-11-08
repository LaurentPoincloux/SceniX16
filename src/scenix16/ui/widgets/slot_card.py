"""Emplacement de concert (Design Book v0.42, section 06, D57, D63, D64).

Carte associée à la touche de même numéro :
- repère coloré en haut, à la couleur du groupe de la touche (1–4 rouge, …),
  à 70 % au repos et 100 % au survol ;
- numéro et point d'état plat ; nom (coupé avec « … ») ; salle sur une ligne ;
- pied : « J-n » ou « Ce soir », puis l'étiquette d'état.

États (D63) : normal (fond contenu, bordure line/soft) ; survol ou paire mise
en évidence (fond relevé, bordure line, repère à 100 %, aucun anneau) ;
sélectionnée, fiche ouverte (fond relevé, bordure fine à la couleur du groupe
à 70 %) ; focus clavier (anneau orange en plus du survol). Prochain garde sa
bordure orange ; aujourd'hui n'en a plus (D11, D63 v0.46). Tous deux ont un point
cerclé fixe et une étiquette orange (« PROCHAIN », « AUJOURD'HUI »).
Paire sélectionnée (D63, v0.45) : point d'état qui pulse lentement, commandé par la
page (set_pulsing), fixe si les animations sont réduites. Pas de focus au clic
(TabFocus) : l'anneau orange reste réservé au clavier. INIT : transparente, pointillés,
« INIT », inactive, sans focus. Pas d'info-bulle : l'aperçu au survol (D64)
la remplace ; son contenu est fourni comme description accessible.

Le composant n'applique aucune règle métier : il affiche une DashboardKey.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from scenix16.domain.dashboard import ConcertState, DashboardKey
from scenix16.services.dashboard_service import STATE_TAGS, card_venue, countdown_label
from shiboken6 import isValid

from scenix16.ui.system import animations_enabled
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY
from scenix16.ui.widgets.keyboard import fresh_activation, is_enter
from scenix16.ui.widgets.step_key import GROUP_COLORS, PULSE_MIN, PULSE_MS

RADIUS = 6
PAD_X, PAD_TOP, PAD_BOTTOM = 12, 12, 10
RING_OFFSET = 2
RING_WIDTH = 2
MARGIN = RING_OFFSET + RING_WIDTH
MIN_HEIGHT = 104
MARKER_REST = 0.70        # repère de groupe au repos ; 100 % au survol (D63)
MARKER_INIT = 0.25
DOT_RING_RADIUS = 6.75    # cercle d'état « prochain » / « aujourd'hui »


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


class SlotCard(QAbstractButton):
    hover_changed = Signal(bool)
    focus_changed = Signal(bool)
    navigate = Signal(int)           # ← (-1) / → (+1), D65
    navigate_rows = Signal(int)      # ↑ (-1) / ↓ (+1), rangée voisine (D65)

    def __init__(self, number: int, group: int, parent=None):
        super().__init__(parent)
        self.number = number
        self.group = group
        self.key: DashboardKey | None = None
        self.selected = False
        self.highlighted = False
        self.pulsing = False
        self.activated_by_keyboard = False     # dernière activation : Entrée (True) ou clic (False)
        self._dot_opacity = 1.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(PULSE_MS)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Linear)
        self._pulse.valueChanged.connect(self._on_pulse)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.set_concert(None)

    # --- fontes ------------------------------------------------------------
    @staticmethod
    def number_font() -> QFont:
        return _font(MONO_FAMILY, 11, QFont.Weight.Medium)

    @staticmethod
    def name_font() -> QFont:
        return _font(LABEL_FAMILY, 16, QFont.Weight.DemiBold)

    @staticmethod
    def venue_font() -> QFont:
        return _font("Segoe UI", 12)

    @staticmethod
    def foot_font() -> QFont:
        return _font(MONO_FAMILY, 11, QFont.Weight.Medium)

    @staticmethod
    def tag_font() -> QFont:
        return _font(LABEL_FAMILY, 10, QFont.Weight.DemiBold, 1.2, caps=True)

    @staticmethod
    def init_font() -> QFont:
        return _font(MONO_FAMILY, 13, QFont.Weight.Medium, 1.3)

    # --- état ----------------------------------------------------------------
    @property
    def is_init(self) -> bool:
        return self.key is None

    @property
    def state(self) -> ConcertState | None:
        return self.key.state if self.key else None

    def set_concert(self, key: DashboardKey | None, animations: bool | None = None) -> None:
        self.key = key
        self.setEnabled(key is not None)
        self.setFocusPolicy(Qt.TabFocus if key is not None else Qt.NoFocus)
        if key is None:
            self.selected = self.highlighted = False
            self.setAccessibleName(f"Emplacement {self.number:02d} : libre (INIT)")
        else:
            c = key.concert
            self.setAccessibleName(f"Emplacement {self.number:02d} : {c.name}")
        self.setToolTip("")                       # remplacée par l'aperçu au survol (D64)
        self.set_pulsing(False)                 # la page rétablit la pulsation de la paire sélectionnée
        self.updateGeometry()
        self.update()

    def set_pulsing(self, on: bool, animations: bool | None = None) -> None:
        """Pulsation du point d'état : paire sélectionnée seulement (D57, D63, v0.45)."""
        if not isValid(self._pulse):              # fenêtre en cours de destruction (fermeture)
            return
        if animations is None:
            animations = animations_enabled()
        pulsing = on and animations and not self.is_init
        if pulsing == self.pulsing and (pulsing == self.pulse_running()):
            return
        self.pulsing = pulsing
        if pulsing:
            self._pulse.start()
        else:
            self._pulse.stop()
            self._dot_opacity = 1.0
        self.update()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected and not self.is_init
        self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        self.highlighted = highlighted and not self.is_init
        self.update()

    def pulse_running(self) -> bool:
        return self._pulse.state() == QVariantAnimation.Running

    def _on_pulse(self, value) -> None:
        self._dot_opacity = PULSE_MIN + (1 - PULSE_MIN) * (0.5 + 0.5 * math.cos(2 * math.pi * value))
        self.update(self.dot_rect())              # seul le point d'état est redessiné (2.8c)

    def dot_center(self) -> QPointF:
        """Centre du point d'état, en haut à droite de la carte."""
        card = self.card_rect()
        nh = QFontMetrics(self.number_font()).height()
        return QPointF(card.right() - PAD_X - 6, card.top() + PAD_TOP + nh / 2)

    def dot_rect(self) -> QRect:
        """Zone redessinée par la pulsation : point et cercle d'état, marge d'anticrénelage."""
        c = self.dot_center()
        r = DOT_RING_RADIUS + 1.5 + 2
        return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r).toAlignedRect()

    # --- textes affichés ---------------------------------------------------
    def name_text(self) -> str:
        return "INIT" if self.is_init else self.key.concert.name

    def venue_text(self) -> str:
        return "" if self.is_init else card_venue(self.key.concert.venue)

    def foot_text(self) -> str:
        return "" if self.is_init else countdown_label(self.key.countdown)

    def tag_text(self) -> str:
        return "" if self.is_init else STATE_TAGS[self.key.state.value]

    # --- dimensions --------------------------------------------------------
    def content_height(self) -> int:
        h = PAD_TOP + QFontMetrics(self.number_font()).height() + 4
        h += QFontMetrics(self.name_font()).height() + 2
        h += QFontMetrics(self.venue_font()).height() + 8
        h += max(QFontMetrics(self.foot_font()).height(), QFontMetrics(self.tag_font()).height() + 4)
        return max(MIN_HEIGHT, h + PAD_BOTTOM)

    def sizeHint(self) -> QSize:
        return QSize(160 + 2 * MARGIN, self.content_height() + 2 * MARGIN)

    def minimumSizeHint(self) -> QSize:
        return QSize(60, self.content_height() + 2 * MARGIN)

    def card_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

    # --- événements ----------------------------------------------------------
    def enterEvent(self, event):
        if not self.is_init:
            self.hover_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_init:
            self.hover_changed.emit(False)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.focus_changed.emit(True)
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.focus_changed.emit(False)
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        """D65 : ← → carte active voisine (en continu entre banques), ↑ ↓ rangée voisine ;
        Entrée et Espace ouvrent la fiche, une fois par appui (D69, 2.8b). Les flèches ne
        suivent jamais l'ordre de tabulation (aucune fuite vers le tri ou les paramètres)."""
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right):
            if not self.is_init:
                self.navigate.emit(-1 if key == Qt.Key_Left else 1)
            event.accept()
            return
        if key in (Qt.Key_Up, Qt.Key_Down):
            if not self.is_init:
                self.navigate_rows.emit(-1 if key == Qt.Key_Up else 1)
            event.accept()
            return
        if is_enter(event) and not self.is_init:
            if fresh_activation(self, event):      # Entrée maintenue : une seule ouverture (D69)
                self.activated_by_keyboard = True
                self.click()
            event.accept()
            return
        if key == Qt.Key_Space and not self.is_init and fresh_activation(self, event):
            self.activated_by_keyboard = True      # Espace : même effet qu'Entrée
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.activated_by_keyboard = False
        super().mousePressEvent(event)

    # --- dessin --------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        card = self.card_rect()
        group_color = QColor(GROUP_COLORS[self.group % 4])
        state = self.state
        # image de pulsation : seule la zone du point est à redessiner, les textes sont inutiles (2.8c)
        dot_only = not self.is_init and self.dot_rect().contains(event.rect())
        emphasized = state in (ConcertState.NEXT, ConcertState.TODAY)

        raised = not self.is_init and (self.highlighted or self.selected)

        # focus clavier : seul anneau de la carte (D63)
        if self.hasFocus() and not self.is_init:
            r = card.adjusted(-RING_OFFSET - RING_WIDTH / 2, -RING_OFFSET - RING_WIDTH / 2,
                              RING_OFFSET + RING_WIDTH / 2, RING_OFFSET + RING_WIDTH / 2)
            p.setPen(QPen(QColor(t.BRAND), RING_WIDTH))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, RADIUS + RING_OFFSET, RADIUS + RING_OFFSET)

        # fond et bordure (D63)
        if self.is_init:
            pen = QPen(QColor(t.LINE_STRONG), 1, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        else:
            if state is ConcertState.NEXT:              # seule « Prochain » garde la bordure (v0.46)
                border, width = QColor(t.BRAND), 2
            elif self.selected:
                border, width = QColor(group_color), 1
                border.setAlphaF(0.70)
            elif self.highlighted:
                border, width = QColor(t.LINE), 1
            else:
                border, width = QColor(t.LINE_SOFT), 1
            p.setPen(QPen(border, width))
            p.setBrush(QColor(t.RAISED if raised else t.CELL))
            inset = width / 2
            p.drawRoundedRect(card.adjusted(inset, inset, -inset, -inset), RADIUS, RADIUS)

        # repère coloré du groupe (3 px, en haut, retrait de 10 px) : 70 % au repos, 100 % au survol
        bar = QColor(group_color)
        bar.setAlphaF(MARKER_INIT if self.is_init else (1.0 if raised else MARKER_REST))
        p.setPen(Qt.NoPen)
        p.setBrush(bar)
        path = QPainterPath()
        path.addRoundedRect(QRectF(card.left() + 10, card.top() - 1, card.width() - 20, 4), 2, 2)
        p.drawPath(path)

        x = card.left() + PAD_X
        w = card.width() - 2 * PAD_X
        y = card.top() + PAD_TOP

        # numéro + point
        p.setFont(self.number_font())
        p.setPen(QColor(t.MUTED))
        nh = QFontMetrics(self.number_font()).height()
        p.drawText(QRectF(x, y, w, nh), Qt.AlignLeft | Qt.AlignVCenter, f"{self.number:02d}")
        if not self.is_init:
            center = self.dot_center()
            if emphasized:                               # point cerclé, sans lueur (D57)
                ring_color = QColor(t.LED_ON)
                ring_color.setAlphaF(self._dot_opacity)
                p.setPen(QPen(ring_color, 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(center, DOT_RING_RADIUS, DOT_RING_RADIUS)
                p.setPen(Qt.NoPen)
            on, off = QColor(t.LED_ON), QColor(t.LED_OFF)
            o = self._dot_opacity
            p.setBrush(QColor(round(off.red() + (on.red() - off.red()) * o),
                              round(off.green() + (on.green() - off.green()) * o),
                              round(off.blue() + (on.blue() - off.blue()) * o)))
            p.drawEllipse(center, 4, 4)
        if dot_only:
            p.end()
            return
        y += nh + 4

        # nom (ou INIT)
        if self.is_init:
            p.setFont(self.init_font())
            p.setPen(QColor(t.DIM))
            ih = QFontMetrics(self.init_font()).height()
            p.drawText(QRectF(x, y, w, ih), Qt.AlignLeft | Qt.AlignVCenter, "INIT")
            p.end()
            return
        p.setFont(self.name_font())
        p.setPen(QColor(t.SILK))
        fm = QFontMetrics(self.name_font())
        p.drawText(QRectF(x, y, w, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(self.name_text(), Qt.ElideRight, round(w)))
        y += fm.height() + 2

        # salle / lieu (une ligne)
        p.setFont(self.venue_font())
        p.setPen(QColor(t.MUTED))
        vm = QFontMetrics(self.venue_font())
        p.drawText(QRectF(x, y, w, vm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   vm.elidedText(self.venue_text(), Qt.ElideRight, round(w)))

        # pied : compte à rebours + étiquette d'état
        tm = QFontMetrics(self.tag_font())
        tag = self.tag_text()
        tag_w = tm.horizontalAdvance(tag) + 12
        tag_h = tm.height() + 4
        bottom = card.bottom() - PAD_BOTTOM
        tag_rect = QRectF(x + w - tag_w, bottom - tag_h, tag_w, tag_h)
        if emphasized:
            p.setBrush(QColor(t.BRAND))
            tag_color = QColor(t.INK)
        else:
            p.setBrush(QColor(t.LINE_SOFT if raised else t.RAISED))   # lisible sur fond relevé
            tag_color = QColor(t.TEXT)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(tag_rect, 3, 3)
        p.setFont(self.tag_font())
        p.setPen(tag_color)
        p.drawText(tag_rect, Qt.AlignCenter, tag)

        p.setFont(self.foot_font())
        p.setPen(QColor(t.MUTED))
        p.drawText(QRectF(x, bottom - tag_h, w - tag_w - 6, tag_h),
                   Qt.AlignLeft | Qt.AlignVCenter, self.foot_text())
        p.end()
