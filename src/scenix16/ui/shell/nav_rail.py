"""Rail de navigation (section 07, D14, D58) : 208 px.

En tête (D58, Design Book v0.44) : logo de l'application, 40 px de haut, centré
horizontalement (marges latérales d'environ 30 px), proportions conservées,
20 px au-dessus et 18 px au-dessous, puis un filet discret pleine largeur (1 px,
line/soft) ; le libellé de groupe est « MENU ».
Ordre : CONCERTS (écran MAIN, libellé v0.48), OUTPUT, TRACKS, SETLISTS, puis NEW SETLIST juste après SETLISTS,
au même niveau que les sections, en orange (action principale).
La barre repliée (logo masqué, filet conservé) est reportée après les phases 1 et 2 (D58, Q13 ;
elle dépend de l'icône Q16).

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
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from scenix16.paths import resource
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY
from scenix16.ui.widgets.keyboard import enable_enter_activation
from scenix16.ui.widgets.logo_label import LogoLabel

ITEM_HEIGHT = 40
LOGO_HEIGHT = 40          # D58 (v0.44)
GROUP_LABEL = "MENU"      # D58 : remplace « SECTIONS »
BAR_WIDTH = 4
BAR_WIDTH_ACTIVE = 6
BAR_HEIGHT = 18
INACTIVE_BAR_OPACITY = 0.35

SECTIONS = (
    ("main", "CONCERTS", t.BRAND),     # espace de travail du dashboard (libellé v0.48 ; clé interne « main »)
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
        enable_enter_activation(self)                  # Entrée = Espace, une fois par appui (2.8b)

    def set_available(self, available: bool) -> None:
        self.setEnabled(available)
        self.setFocusPolicy(Qt.TabFocus if available else Qt.NoFocus)   # clic : pas d'anneau (v0.45)
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # en tête : logo (D58, v0.44), centré horizontalement
        head = QHBoxLayout()
        head.setContentsMargins(14, 20, 14, 0)
        self.logo = LogoLabel(resource("logos", "scenix16.png"), LOGO_HEIGHT)
        self.logo.setAccessibleName("SceniX16")
        head.addStretch(1)
        head.addWidget(self.logo)
        head.addStretch(1)
        outer.addLayout(head)
        outer.addSpacing(18)
        # filet discret pleine largeur entre le logo et le menu
        self.rule = QFrame(objectName="RailRule")
        self.rule.setFixedHeight(1)
        outer.addWidget(self.rule)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 20)
        layout.setSpacing(8)
        outer.addLayout(layout, 1)

        self.group_label = QLabel(GROUP_LABEL, objectName="RailGroupLabel")
        layout.addWidget(self.group_label)
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
