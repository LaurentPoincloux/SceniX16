"""Afficheur d'information de la barre supérieure (D60, Design Book v0.43).

Module sobre inspiré d'un afficheur LCD contemporain, sans segments, lueur ni vert :
panneau en léger retrait (fond LCD_BG, bordure line, rayon 6 px, 36 px de haut).
De gauche à droite : concerts à venir, concerts passés (chiffres mono 16 px crème,
libellés en capitales 10 px gris), puis la date de référence (mono 11 px, gris
atténué), séparés par des filets verticaux. Les compteurs priment sur la date.
La date est le jour SceniX16 (D10, Q12). À la bascule de 06:00 (D73, 2.8a), la
fenêtre principale recalcule l'affichage et appelle set_readout.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from scenix16.services.dashboard_service import InfoReadout
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY

HEIGHT = 36
PAD_X = 12
GAP = 12               # entre groupes et filets
VALUE_GAP = 6          # entre un chiffre et son libellé
SEP_HEIGHT = 18
RADIUS = 6


def value_font() -> QFont:
    font = QFont(MONO_FAMILY)
    font.setPixelSize(16)
    font.setWeight(QFont.Weight.Medium)
    return font


def label_font() -> QFont:
    font = QFont(LABEL_FAMILY)
    font.setPixelSize(10)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
    font.setCapitalization(QFont.AllUppercase)
    return font


def date_font() -> QFont:
    font = QFont(MONO_FAMILY)
    font.setPixelSize(11)
    font.setWeight(QFont.Weight.Medium)
    return font


class InfoDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoDisplay")
        self.setFixedHeight(HEIGHT)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.NoFocus)
        self.readout: InfoReadout | None = None

    def set_readout(self, readout: InfoReadout) -> None:
        self.readout = readout
        self.setAccessibleName(readout.accessible)
        self.updateGeometry()
        self.setFixedWidth(self._content_width())
        self.update()

    # --- dimensions --------------------------------------------------------------
    def _parts(self) -> list[tuple[str, str]]:
        r = self.readout
        return [(r.upcoming, r.upcoming_label), (r.past, r.past_label)] if r else []

    def _pair_width(self, value: str, label: str) -> float:
        return (QFontMetricsF(value_font()).horizontalAdvance(value) + VALUE_GAP
                + QFontMetricsF(label_font()).horizontalAdvance(label))

    def _content_width(self) -> int:
        if self.readout is None:
            return 2 * PAD_X
        width = 2 * PAD_X + sum(self._pair_width(v, lab) for v, lab in self._parts())
        width += 2 * (GAP + 1 + GAP)                        # deux filets
        width += QFontMetricsF(date_font()).horizontalAdvance(self.readout.date)
        return int(width + 0.999)

    def sizeHint(self) -> QSize:
        return QSize(self._content_width(), HEIGHT)

    # --- dessin --------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(t.LINE), 1))
        p.setBrush(QColor(t.LCD_BG))
        p.drawRoundedRect(box, RADIUS, RADIUS)
        if self.readout is None:
            return
        vf, lf, df = value_font(), label_font(), date_font()
        vm, lm, dm = QFontMetricsF(vf), QFontMetricsF(lf), QFontMetricsF(df)
        baseline = (self.height() + vm.ascent() - vm.descent()) / 2       # chiffres centrés
        x = float(PAD_X)
        for i, (value, label) in enumerate(self._parts()):
            p.setFont(vf)
            p.setPen(QColor(t.SILK))
            p.drawText(QRectF(x, baseline - vm.ascent(), vm.horizontalAdvance(value) + 1, vm.height()),
                       Qt.AlignLeft | Qt.AlignTop, value)
            x += vm.horizontalAdvance(value) + VALUE_GAP
            p.setFont(lf)
            p.setPen(QColor(t.MUTED))
            p.drawText(QRectF(x, baseline - lm.ascent(), lm.horizontalAdvance(label) + 2, lm.height()),
                       Qt.AlignLeft | Qt.AlignTop, label)                  # même ligne de base
            x += lm.horizontalAdvance(label) + GAP
            self._separator(p, x)
            x += 1 + GAP
        p.setFont(df)
        p.setPen(QColor(t.DIM))
        p.drawText(QRectF(x, 0, dm.horizontalAdvance(self.readout.date) + 2, self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self.readout.date)
        p.end()

    def _separator(self, p: QPainter, x: float) -> None:
        p.fillRect(QRectF(x, (self.height() - SEP_HEIGHT) / 2, 1, SEP_HEIGHT), QColor(t.LINE_SOFT))
