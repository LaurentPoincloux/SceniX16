"""Touche du step sequencer (Design Book v0.42, section 05, D57, D63).

Anatomie (touches à plat, D57) :
1. corps : couleur historique du groupe en aplat, rayon 8 px, proportion 3:5,
   sans relief ni liseré ;
2. point d'état plat : 22 % de la largeur, dans le tiers haut ; éteint
   #5F1B13, allumé #F30400, sans lueur ;
3. numéro : IBM Plex Mono, #151515 à 72 %, en bas de la touche.

États (sections 05 et 06, D3, D8, D11, D63) :
- à venir : point allumé ;
- prochain et aujourd'hui : point allumé et cerclé, fixe (identifiant interne
  Led.HALO ; D11 révisée en v0.45) ;
- paire sélectionnée (D63, v0.45) : le point d'état pulse lentement (fixe si Windows
  demande de réduire les animations) ; la page commande la pulsation (set_pulsing) ;
- INIT (emplacement libre) : touche atténuée, inactive, sans survol ni focus ;
- survol, ou paire mise en évidence depuis l'emplacement : +6 % de luminosité ;
  appui : −5 % ; fiche ouverte : filet crème de 3 px sous la touche (2 px, dans l'anneau,
  quand la touche a aussi le focus clavier) ;
- focus clavier : anneau orange, seul anneau de la touche ; un clic à la souris ne
  donne pas le focus (TabFocus, D8 précisée en v0.45), donc jamais l'anneau.

Le composant ne décide d'aucune règle métier : il reçoit l'état calculé par
le domaine (ConcertState) ou None pour un emplacement INIT.
"""

from __future__ import annotations

import math
from enum import Enum

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from scenix16.domain.dashboard import ConcertState
from shiboken6 import isValid

from scenix16.ui.system import animations_enabled
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import MONO_FAMILY
from scenix16.ui.widgets.keyboard import fresh_activation, is_enter

GROUP_COLORS = (t.KEY_RED, t.KEY_ORANGE, t.KEY_YELLOW, t.KEY_WHITE)

ASPECT = 5 / 3            # hauteur / largeur du corps (3:5)
MIN_WIDTH = 44            # bornes de largeur du corps (section 08)
MAX_WIDTH = 96
RADIUS = 8
RING_OFFSET = 3           # anneau de focus : 2 px, décalé de 3 px
RING_WIDTH = 2
MARGIN = RING_OFFSET + RING_WIDTH   # place réservée autour du corps (anneau, filet)
UNDERLINE = 3             # filet crème « fiche ouverte » (D63)
UNDERLINE_GAP = 2
FOCUS_UNDERLINE = RING_OFFSET - RING_WIDTH / 2   # avec le focus : sous le corps, dans l'anneau (2 px)
STATUS_RING_GAP = 2       # point cerclé (D57) : écart, puis cercle de 1,5 px
STATUS_RING_WIDTH = 1.5
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
    down_requested = Signal()        # ↓ : carte de même numéro (D65)

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
        self.activated_by_keyboard = False     # dernière activation : Entrée (True) ou clic (False)
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
        self.setFocusPolicy(Qt.NoFocus if self.is_init else Qt.TabFocus)   # clic : pas de focus (v0.45)
        if self.is_init:
            self.hovered = self.highlighted = self.selected = False
        self.set_pulsing(False)                 # la page rétablit la pulsation de la paire sélectionnée
        self.update()

    def mousePressEvent(self, event):
        self.activated_by_keyboard = False
        super().mousePressEvent(event)

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
        self.update(self.led_rect())              # seul le point d'état est redessiné (2.8c)

    def led_geometry(self) -> tuple[QPointF, float]:
        """Centre et diamètre du point d'état (D57)."""
        body = self.body_rect()
        d = body.width() * LED_RATIO
        return QPointF(body.center().x(), body.top() + body.height() * LED_TOP + d / 2), d

    def led_rect(self) -> QRect:
        """Zone redessinée par la pulsation : point et cercle d'état, marge d'anticrénelage."""
        center, d = self.led_geometry()
        r = d / 2 + STATUS_RING_GAP + STATUS_RING_WIDTH + 2
        return QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r).toAlignedRect()

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
        y = (self.height() - h) / 2
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
        """D9, D46, D65 : ← → entre les touches actives ; ↓ vers la carte de même numéro ;
        ↑ sans effet ; Entrée et Espace ouvrent la fiche, une fois par appui (2.8b)."""
        key = event.key()
        if key == Qt.Key_Left:
            self.navigate.emit(-1)
        elif key == Qt.Key_Right:
            self.navigate.emit(1)
        elif key == Qt.Key_Down:
            self.down_requested.emit()
            event.accept()
        elif key == Qt.Key_Up:
            event.accept()
        elif is_enter(event):
            if not self.is_init and fresh_activation(self, event):
                self.activated_by_keyboard = True
                self.click()
            event.accept()
        else:
            if key == Qt.Key_Space and fresh_activation(self, event):
                self.activated_by_keyboard = True      # Espace : même effet qu'Entrée (D69)
            super().keyPressEvent(event)   # Espace : comportement standard du bouton

    # --- dessin ------------------------------------------------------------
    def body_color(self) -> QColor:
        color = QColor(GROUP_COLORS[self.group % 4])
        if self.is_init:   # atténuée : saturation × 0,25, luminosité × 0,55
            h, s, v, a = color.getHsvF()
            color = QColor.fromHsvF(max(h, 0), s * 0.25, v * 0.55, a)
        elif self.isDown():
            color = color.darker(105)                    # appui : −5 %
        elif self.hovered or self.highlighted:
            color = color.lighter(106)                   # survol ou paire : +6 % (D63)
        return color

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        body = self.body_rect()
        # image de pulsation : seule la zone du point est à redessiner, le numéro est inutile (2.8c)
        led_only = not self.is_init and self.led_rect().contains(event.rect())

        # focus clavier : seul anneau de la touche (D63)
        if self.hasFocus() and not self.is_init:
            ring = body.adjusted(-RING_OFFSET - RING_WIDTH / 2, -RING_OFFSET - RING_WIDTH / 2,
                                 RING_OFFSET + RING_WIDTH / 2, RING_OFFSET + RING_WIDTH / 2)
            p.setPen(QPen(QColor(t.BRAND), RING_WIDTH))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ring, RADIUS + RING_OFFSET, RADIUS + RING_OFFSET)

        # corps à plat (D57)
        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)
        p.setPen(Qt.NoPen)
        p.setBrush(self.body_color())
        p.drawPath(path)

        # fiche ouverte : filet crème sous la touche (D63). Avec le focus clavier, le filet est
        # réduit et collé au corps, à l'intérieur de l'anneau, qu'il ne recouvre plus (2.9, C1).
        if self.selected:
            p.setBrush(QColor(t.SILK))
            if self.hasFocus():
                underline = QRectF(body.left() + RADIUS / 2, body.bottom(),
                                   body.width() - RADIUS, FOCUS_UNDERLINE)
            else:
                underline = QRectF(body.left() + RADIUS / 2, body.bottom() + UNDERLINE_GAP,
                                   body.width() - RADIUS, UNDERLINE)
            p.drawRoundedRect(underline, 1, 1)

        # point d'état plat (D57)
        center, d = self.led_geometry()
        if self.led is Led.OFF:
            p.setBrush(QColor(t.LED_OFF))
            p.drawEllipse(center, d / 2, d / 2)
        else:
            opacity = self._led_opacity
            if self.led is Led.HALO:                     # « prochain » / « aujourd'hui » : cerclé
                ring_color = QColor(t.LED_ON)
                ring_color.setAlphaF(opacity)
                radius = d / 2 + STATUS_RING_GAP + STATUS_RING_WIDTH / 2
                p.setPen(QPen(ring_color, STATUS_RING_WIDTH))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(center, radius, radius)
                p.setPen(Qt.NoPen)
            led = QColor(t.LED_OFF)
            on = QColor(t.LED_ON)
            led = QColor(
                round(led.red() + (on.red() - led.red()) * opacity),
                round(led.green() + (on.green() - led.green()) * opacity),
                round(led.blue() + (on.blue() - led.blue()) * opacity),
            )
            p.setBrush(led)
            p.drawEllipse(center, d / 2, d / 2)

        if led_only:
            p.end()
            return

        # numéro
        ink = QColor(t.INK)
        ink.setAlphaF(0.72)
        p.setPen(ink)
        p.setFont(self.number_font())
        text_rect = QRectF(body.left(), body.top(), body.width(),
                           body.height() * (1 - NUMBER_BOTTOM))
        p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignBottom, f"{self.number:02d}")
        p.end()
