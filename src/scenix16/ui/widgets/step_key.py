"""Touche du step sequencer (Design Book v0.40, section 05).

Anatomie :
1. corps : couleur historique du groupe en aplat, rayon 8 px, proportion 3:5 ;
2. relief : liseré clair en haut, bande sombre en bas (unique effet de matière) ;
3. voyant : 22 % de la largeur, dans le tiers haut ; éteint #5F1B13 en creux,
   allumé #F30400 ;
4. numéro : IBM Plex Mono, #151515 à 72 %, en bas de la touche.

États (sections 05 et 06, D3, D8, D11) :
- à venir : voyant allumé ;
- prochain : voyant allumé avec halo ;
- aujourd'hui : comme prochain, voyant qui pulse lentement (fixe si Windows
  demande de réduire les animations) ;
- INIT (emplacement libre) : touche atténuée, inactive, sans survol ni focus ;
- fiche ouverte : anneau #F2E9DA ; mise en évidence (survol de l'emplacement
  associé) : même anneau ; focus clavier : anneau orange ;
- survol : +6 % de luminosité ; pression : la touche s'enfonce d'1 px.

Le composant ne décide d'aucune règle métier : il reçoit l'état calculé par
le domaine (ConcertState) ou None pour un emplacement INIT.
"""

from __future__ import annotations

import math
from enum import Enum

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from scenix16.domain.dashboard import ConcertState
from scenix16.ui.system import animations_enabled
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import MONO_FAMILY

GROUP_COLORS = (t.KEY_RED, t.KEY_ORANGE, t.KEY_YELLOW, t.KEY_WHITE)

ASPECT = 5 / 3            # hauteur / largeur du corps (3:5)
MIN_WIDTH = 44            # bornes de largeur du corps (section 08)
MAX_WIDTH = 96
RADIUS = 8
RING_OFFSET = 3           # anneaux : 2 px, décalés de 3 px
RING_WIDTH = 2
MARGIN = RING_OFFSET + RING_WIDTH   # place réservée autour du corps pour les anneaux
LED_RATIO = 0.22
LED_TOP = 0.12
NUMBER_BOTTOM = 0.09
PULSE_MS = 2400
PULSE_MIN = 0.35          # opacité minimale du voyant pendant la pulsation


class Led(Enum):
    OFF = "off"
    ON = "on"
    HALO = "halo"


_STATE_LED = {
    ConcertState.UPCOMING: Led.ON,
    ConcertState.NEXT: Led.HALO,
    ConcertState.TODAY: Led.HALO,
}


class StepKey(QAbstractButton):
    hover_changed = Signal(bool)     # survol (couplage avec l'emplacement)
    focus_changed = Signal(bool)     # focus clavier (couplage avec l'emplacement)
    navigate = Signal(int)           # ← (-1) / → (+1), D9

    def __init__(self, number: int, group: int, parent=None):
        super().__init__(parent)
        self.number = number
        self.group = group
        self.led = Led.OFF
        self.is_init = True
        self.pulsing = False
        self.selected = False
        self.highlighted = False
        self.hovered = False
        self._led_opacity = 1.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(PULSE_MS)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Linear)
        self._pulse.valueChanged.connect(self._on_pulse)
        sp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.setMinimumWidth(MIN_WIDTH + 2 * MARGIN)
        self.setMaximumWidth(MAX_WIDTH + 2 * MARGIN)
        self.setAttribute(Qt.WA_Hover, True)
        self.set_concert_state(None)

    # --- état ------------------------------------------------------------
    def set_concert_state(self, state: ConcertState | None,
                          animations: bool | None = None) -> None:
        """None = emplacement INIT ; sinon un état présent sur le dashboard."""
        if state is None:
            self.is_init, self.led = True, Led.OFF
        elif state in _STATE_LED:
            self.is_init, self.led = False, _STATE_LED[state]
        else:
            raise ValueError(f"État absent du dashboard : {state}")
        self.setEnabled(not self.is_init)
        self.setFocusPolicy(Qt.NoFocus if self.is_init else Qt.StrongFocus)
        if self.is_init:
            self.hovered = self.highlighted = self.selected = False
        want_pulse = state is ConcertState.TODAY
        if animations is None:
            animations = animations_enabled()
        self.pulsing = want_pulse and animations
        if self.pulsing:
            self._pulse.start()
        else:
            self._pulse.stop()
            self._led_opacity = 1.0
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
        # 1 → PULSE_MIN → 1 sur une période (« ease-in-out » lissé par le cosinus)
        self._led_opacity = PULSE_MIN + (1 - PULSE_MIN) * (0.5 + 0.5 * math.cos(2 * math.pi * value))
        self.update()

    # --- dimensions ------------------------------------------------------
    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        body = min(max(width - 2 * MARGIN, MIN_WIDTH), MAX_WIDTH)
        return round(body * ASPECT) + 2 * MARGIN

    def sizeHint(self) -> QSize:
        width = 60 + 2 * MARGIN
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        width = MIN_WIDTH + 2 * MARGIN
        return QSize(width, self.heightForWidth(width))

    def body_rect(self) -> QRectF:
        """Rectangle du corps, centré, en proportion 3:5."""
        avail_w = self.width() - 2 * MARGIN
        avail_h = self.height() - 2 * MARGIN
        w = min(avail_w, avail_h / ASPECT)
        w = min(max(w, 1), MAX_WIDTH)
        h = w * ASPECT
        x = (self.width() - w) / 2
        y = (self.height() - h) / 2 + (1 if self.isDown() else 0)
        return QRectF(x, y, w, h)

    def number_font(self) -> QFont:
        font = QFont(MONO_FAMILY)
        font.setWeight(QFont.Weight.Medium)
        font.setPixelSize(max(10, min(13, round(self.body_rect().width() * 0.18))))
        return font

    # --- survol (WA_Hover) -------------------------------------------------
    def enterEvent(self, event):
        if not self.is_init:
            self.hovered = True
            self.update()
            self.hover_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        was_hovered = self.hovered
        self.hovered = False
        self.update()
        if was_hovered:
            self.hover_changed.emit(False)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.focus_changed.emit(True)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.focus_changed.emit(False)
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        """D9 : ← → entre les touches actives ; Entrée / Espace ouvrent ; ↑ ↓ sans effet."""
        key = event.key()
        if key == Qt.Key_Left:
            self.navigate.emit(-1)
        elif key == Qt.Key_Right:
            self.navigate.emit(1)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if not self.is_init:
                self.click()
        elif key in (Qt.Key_Up, Qt.Key_Down):
            event.accept()
        else:
            super().keyPressEvent(event)   # Espace : comportement standard du bouton

    # --- dessin ------------------------------------------------------------
    def body_color(self) -> QColor:
        color = QColor(GROUP_COLORS[self.group % 4])
        if self.is_init:   # atténuée : saturation × 0,25, luminosité × 0,55
            h, s, v, a = color.getHsvF()
            color = QColor.fromHsvF(max(h, 0), s * 0.25, v * 0.55, a)
        elif self.hovered:
            color = color.lighter(106)
        return color

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        body = self.body_rect()

        # anneaux : focus clavier (orange) prioritaire, sinon fiche ouverte / mise en évidence
        ring_color = None
        if self.hasFocus() and not self.is_init:
            ring_color = QColor(t.BRAND)
        elif self.selected or self.highlighted:
            ring_color = QColor(t.SILK)
        if ring_color is not None:
            ring = body.adjusted(-RING_OFFSET - RING_WIDTH / 2, -RING_OFFSET - RING_WIDTH / 2,
                                 RING_OFFSET + RING_WIDTH / 2, RING_OFFSET + RING_WIDTH / 2)
            p.setPen(QPen(ring_color, RING_WIDTH))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ring, RADIUS + RING_OFFSET, RADIUS + RING_OFFSET)

        # corps
        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)
        p.setPen(Qt.NoPen)
        p.setBrush(self.body_color())
        p.drawPath(path)

        # relief : bande sombre en bas, liseré clair en haut
        p.save()
        p.setClipPath(path)
        band = 3 if self.isDown() else 6
        p.setBrush(QColor(0, 0, 0, round(255 * (0.22 if self.isDown() else 0.18))))
        p.drawRect(QRectF(body.left(), body.bottom() - band, body.width(), band))
        if not self.isDown():
            p.setBrush(QColor(255, 255, 255, round(255 * 0.35)))
            p.drawRect(QRectF(body.left(), body.top(), body.width(), 1))
        p.restore()

        # voyant
        d = body.width() * LED_RATIO
        center = QPointF(body.center().x(), body.top() + body.height() * LED_TOP + d / 2)
        if self.led is Led.OFF:
            p.setBrush(QColor(t.LED_OFF))
            p.drawEllipse(center, d / 2, d / 2)
            p.setBrush(QColor(0, 0, 0, 110))       # creux : ombre interne en haut
            p.save()
            clip = QPainterPath()
            clip.addEllipse(center, d / 2, d / 2)
            p.setClipPath(clip)
            p.drawEllipse(QPointF(center.x(), center.y() - d * 0.62), d / 2, d / 2)
            p.restore()
        else:
            opacity = self._led_opacity
            if self.led is Led.HALO:
                glow = QRadialGradient(center, d * 1.4)
                glow.setColorAt(0.0, QColor(243, 4, 0, round(140 * opacity)))
                glow.setColorAt(1.0, QColor(243, 4, 0, 0))
                p.setBrush(glow)
                p.drawEllipse(center, d * 1.4, d * 1.4)
                p.setBrush(QColor(243, 4, 0, round(46 * opacity)))   # anneau 2 px à 18 %
                p.drawEllipse(center, d / 2 + 2, d / 2 + 2)
            led = QColor(t.LED_OFF)
            on = QColor(t.LED_ON)
            led = QColor(
                round(led.red() + (on.red() - led.red()) * opacity),
                round(led.green() + (on.green() - led.green()) * opacity),
                round(led.blue() + (on.blue() - led.blue()) * opacity),
            )
            p.setBrush(led)
            p.drawEllipse(center, d / 2, d / 2)

        # numéro
        ink = QColor(t.INK)
        ink.setAlphaF(0.72)
        p.setPen(ink)
        p.setFont(self.number_font())
        text_rect = QRectF(body.left(), body.top(), body.width(),
                           body.height() * (1 - NUMBER_BOTTOM))
        p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignBottom, f"{self.number:02d}")
        p.end()
