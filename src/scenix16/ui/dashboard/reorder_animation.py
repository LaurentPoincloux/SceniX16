"""Glissement des cartes au changement de sens de tri (section 06, arbitrage 5 de 2.5).

Au changement de sens, chaque carte occupée glisse de son ancienne position
vers la nouvelle en 180 ms, pour que l'œil suive le réordonnancement. Les
touches, elles, sont actualisées immédiatement.

Principe : les emplacements réels prennent aussitôt leur état final. Une couche
temporaire, posée au-dessus de la grille, dessine pendant 180 ms des images des
cartes (ancienne image qui s'efface, nouvelle qui apparaît) le long du trajet,
puis disparaît. Cette couche est transparente à la souris et ne prend jamais le
focus : clics, survols et clavier atteignent les emplacements réels.
Aucune animation si Windows demande de réduire les animations (décidé par l'appelant).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QPoint, QRect, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from scenix16.ui.theme import tokens as t

DURATION_MS = 180


@dataclass(frozen=True)
class CardImage:
    rect: QRect          # position de l'emplacement (anneau compris), repère de la grille
    pixmap: QPixmap


def card_pixmap(widget: QWidget) -> QPixmap:
    """Image du widget sur fond transparent (grab() peindrait le fond de la fenêtre)."""
    dpr = widget.devicePixelRatioF()
    pixmap = QPixmap(round(widget.width() * dpr), round(widget.height() * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    widget.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return pixmap


def snapshot(grid) -> tuple[dict[int, CardImage], list[CardImage]]:
    """Images des cartes occupées (par identifiant de concert) et des emplacements INIT."""
    cards, free = {}, []
    for slot in grid.slots:
        image = CardImage(QRect(slot.geometry()), card_pixmap(slot))
        if slot.key is not None:
            cards[slot.key.concert.id] = image
        else:
            free.append(image)
    return cards, free


def _lerp(a: QRect, b: QRect, v: float) -> QRectF:
    return QRectF(a.x() + (b.x() - a.x()) * v, a.y() + (b.y() - a.y()) * v,
                  a.width() + (b.width() - a.width()) * v, a.height() + (b.height() - a.height()) * v)


class ReorderOverlay(QWidget):
    finished = Signal()

    def __init__(self, grid: QWidget, before: dict[int, CardImage],
                 after: dict[int, CardImage], free_after: list[CardImage]):
        super().__init__(grid)
        self.setObjectName("ReorderOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.before, self.after, self.free_after = before, after, free_after
        self.value = 0.0
        self._done = False
        self.setGeometry(grid.rect())
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._on_value)
        self.animation.finished.connect(self._finish)
        self.raise_()
        self.show()
        self.animation.start()

    @property
    def running(self) -> bool:
        return not self._done

    def _on_value(self, value) -> None:
        self.value = float(value)
        self.update()

    def stop(self) -> None:
        """Termine immédiatement (nouveau tri, rafraîchissement, redimensionnement)."""
        self.animation.stop()
        self._finish()

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.hide()
        self.deleteLater()
        self.finished.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(t.GROUND))
        for image in self.free_after:
            p.drawPixmap(QRectF(image.rect), image.pixmap, QRectF(image.pixmap.rect()))
        v = self.value
        for cid in self.before.keys() | self.after.keys():
            old, new = self.before.get(cid), self.after.get(cid)
            if old and new:
                target = _lerp(old.rect, new.rect, v)
                layers = ((old.pixmap, 1.0 - v), (new.pixmap, v))
            elif new:
                target, layers = QRectF(new.rect), ((new.pixmap, v),)
            else:
                target, layers = QRectF(old.rect), ((old.pixmap, 1.0 - v),)
            for pixmap, opacity in layers:
                p.setOpacity(opacity)
                p.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
            p.setOpacity(1.0)
        p.end()
