"""Rail de navigation (section 07, D14) : 208 px.

Ordre : MAIN, OUTPUT, TRACKS, SETLISTS, puis NEW SETLIST juste après SETLISTS,
au même niveau que les sections, en orange (action principale).

Arbitrages validés (incrément 2.3) :
- les entrées dont l'écran n'existe pas encore restent visibles mais
  inactives : libellé gris, repère coloré atténué, ni clic, ni focus, ni
  info-bulle ;
- NEW SETLIST garde son identité orange sous une forme désactivée lisible ;
- dans PARAMÈTRES, aucune section n'est active et MAIN reste cliquable.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QLabel, QPushButton, QVBoxLayout, QWidget

from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY

ITEM_HEIGHT = 40
BAR_WIDTH = 4
BAR_WIDTH_ACTIVE = 6
BAR_HEIGHT = 18
INACTIVE_BAR_OPACITY = 0.35

SECTIONS = (
    ("main", "MAIN", t.BRAND),
    ("output", "OUTPUT", t.SECTION_OUTPUT),
    ("tracks", "TRACKS", t.SECTION_TRACKS),
    ("setlists", "SETLISTS", t.SECTION_SETLISTS),
)
NEW_SETLIST_LABEL = "+ NEW SETLIST ▾"   # libellé du Design Book (menu prévu en phase 3)


class NavItem(QAbstractButton):
    """Entrée de section : fond neutre, barre verticale à la couleur de la section."""

    def __init__(self, key: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.color = QColor(color)
        self.setText(label)
        self.setAccessibleName(label)
        self.active = False
        self.setFixedHeight(ITEM_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def set_available(self, available: bool) -> None:
        self.setEnabled(available)
        self.setFocusPolicy(Qt.StrongFocus if available else Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor if available else Qt.ArrowCursor)
        self.setToolTip("")
        self.update()

    def set_active(self, active: bool) -> None:
        self.active = active
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(t.RAIL_WIDTH - 28, ITEM_HEIGHT)

    def label_font(self) -> QFont:
        font = QFont(LABEL_FAMILY)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPixelSize(14)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
        return font

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hovered = self.isEnabled() and self.underMouse()
        bg = QColor(t.RAISED if (self.active or hovered) else t.CELL)
        border = QColor(t.LINE_STRONG if self.active else t.LINE_SOFT)
        if self.hasFocus():
            border = QColor(t.BRAND)
        p.setPen(QPen(border, 2 if self.hasFocus() else 1))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 5, 5)

        bar = QColor(self.color)
        if not self.isEnabled():
            bar.setAlphaF(INACTIVE_BAR_OPACITY)
        width = BAR_WIDTH_ACTIVE if self.active else BAR_WIDTH
        p.setPen(Qt.NoPen)
        p.setBrush(bar)
        p.drawRoundedRect(QRectF(12, (self.height() - BAR_HEIGHT) / 2, width, BAR_HEIGHT), 2, 2)

        p.setPen(QColor(t.TEXT if self.isEnabled() else t.DIM))
        p.setFont(self.label_font())
        p.drawText(QRectF(12 + BAR_WIDTH_ACTIVE + 10, 0, self.width(), self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class NavRail(QWidget):
    main_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NavRail")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(t.RAIL_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(8)

        layout.addWidget(QLabel("SECTIONS", objectName="RailGroupLabel"))
        self.items: dict[str, NavItem] = {}
        for key, label, color in SECTIONS:
            item = NavItem(key, label, color)
            item.set_available(key == "main")    # seules les sections développées sont actives
            layout.addWidget(item)
            self.items[key] = item
        self.items["main"].clicked.connect(self.main_requested)

        self.new_setlist = QPushButton(NEW_SETLIST_LABEL, objectName="NewSetlistButton")
        self.new_setlist.setEnabled(False)               # création : phase 3
        self.new_setlist.setFocusPolicy(Qt.NoFocus)
        layout.addSpacing(6 - layout.spacing())
        layout.addWidget(self.new_setlist)
        layout.addStretch(1)

    def set_active(self, key: str | None) -> None:
        """Section surlignée ; None dans les écrans secondaires (PARAMÈTRES)."""
        for item_key, item in self.items.items():
            item.set_active(item_key == key)
