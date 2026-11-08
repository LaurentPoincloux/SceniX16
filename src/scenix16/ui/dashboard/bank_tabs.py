"""Rangée des boutons de banque (Design Book v0.42, section 06, D44 à D47, D67).

- Onglets A à H toujours affichés ; à partir de I, seulement les banques occupées.
- Un seul arrêt de Tab : l'onglet de la banque sélectionnée (arbitrage 3 de 2.6) ;
  ← et → déplacent ensuite le focus entre les onglets actifs, sans bouclage
  (arbitrage 4) et sans changer de banque ; Entrée ou Espace sélectionnent.
- Si les onglets dépassent la largeur disponible, la rangée défile avec des
  flèches ‹ › ; les touches ne défilent jamais.
La rangée n'applique aucune règle : la page lui donne l'occupation et la
banque sélectionnée, et reçoit la demande de sélection (bank_requested).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QScrollArea, QSizePolicy,
                               QWidget)

from scenix16.domain.dashboard import MIN_TABS
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY
from scenix16.ui.widgets.bank_tab import BODY_HEIGHT, MARGIN, BankTab

TAB_GAP = 6
ARROW_WIDTH = 24
SCROLL_STEP = 120


class _Arrow(QAbstractButton):
    """Flèche ‹ ou › de défilement de la rangée (souris seulement)."""

    def __init__(self, direction: int, parent=None):
        super().__init__(parent)
        self.direction = direction
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("Onglets précédents" if direction < 0 else "Onglets suivants")
        self.setFixedSize(ARROW_WIDTH, BODY_HEIGHT + 2 * MARGIN)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse() and self.isEnabled():
            p.fillRect(QRectF(self.rect()).adjusted(0, MARGIN, 0, -MARGIN), QColor(t.PANEL))
        font = QFont(LABEL_FAMILY)
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(t.MUTED if self.isEnabled() else t.DIM))
        p.drawText(self.rect(), Qt.AlignCenter, "‹" if self.direction < 0 else "›")
        p.end()


class BankTabs(QWidget):
    bank_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BankTabs")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(BODY_HEIGHT + 2 * MARGIN)
        self.tabs: list[BankTab] = []
        self.selected = 0
        self.left_inset = 0
        self._laying_out = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.prev_arrow = _Arrow(-1)
        self.next_arrow = _Arrow(+1)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.scroll.viewport().setAutoFillBackground(False)
        self.strip = QWidget()
        self.strip.setObjectName("BankTabStrip")
        self.strip.setAutoFillBackground(False)
        self.strip_layout = QHBoxLayout(self.strip)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(TAB_GAP)
        self.strip_layout.addStretch(1)
        self.scroll.setWidget(self.strip)
        row.addWidget(self.prev_arrow)
        row.addWidget(self.scroll, 1)
        row.addWidget(self.next_arrow)
        self.prev_arrow.clicked.connect(lambda: self._scroll_by(-SCROLL_STEP))
        self.next_arrow.clicked.connect(lambda: self._scroll_by(SCROLL_STEP))
        self.scroll.horizontalScrollBar().valueChanged.connect(self._update_arrows)
        self.scroll.horizontalScrollBar().rangeChanged.connect(self._update_arrows)
        # seconde passe après la mise en page de Qt (largeur visible réduite par les flèches)
        self._ensure_timer = QTimer(self)
        self._ensure_timer.setSingleShot(True)
        self._ensure_timer.setInterval(0)
        self._ensure_timer.timeout.connect(lambda: self.ensure_visible(self.selected))
        self._update_arrows()
        # A à H créés tout de suite : la rangée précède les touches dans l'ordre de tabulation
        self.set_tabs([0] * MIN_TABS, 0)

    # --- état ----------------------------------------------------------------
    def set_tabs(self, counts: list[int], selected: int) -> None:
        """counts : nombre de concerts de chaque onglet affiché ; selected : banque affichée."""
        while len(self.tabs) < len(counts):
            tab = BankTab(len(self.tabs), self.strip)
            tab.clicked.connect(lambda _=False, i=tab.index: self.bank_requested.emit(i))
            tab.navigate.connect(lambda delta, i=tab.index: self.move_focus(i, delta))
            self.strip_layout.insertWidget(len(self.tabs), tab)
            if self.tabs:                        # I, J… juste après H dans l'ordre de tabulation
                QWidget.setTabOrder(self.tabs[-1], tab)
            self.tabs.append(tab)
        focused = next((tab.index for tab in self.tabs if tab.hasFocus()), None)
        self.selected = selected
        for tab in self.tabs:
            visible = tab.index < len(counts)
            tab.setVisible(visible)
            if visible:
                tab.set_state(tab.index == selected, counts[tab.index])
            # un seul arrêt de Tab : l'onglet sélectionné, s'il est actif
            tab.setFocusPolicy(Qt.TabFocus if visible and tab.index == selected and tab.occupied
                               else Qt.NoFocus)
        self._layout_strip()
        if focused is not None and focused < len(counts) and self.tabs[focused].occupied:
            self.tabs[focused].setFocus(Qt.OtherFocusReason)
        self.ensure_visible(selected)
        self._ensure_timer.start()

    def tab(self, index: int) -> BankTab:
        return self.tabs[index]

    def visible_tabs(self) -> list[BankTab]:
        return [tab for tab in self.tabs if tab.isVisibleTo(self)]

    def set_left_inset(self, inset: int) -> None:
        """Aligne le premier onglet sur la première touche (repère du séquenceur)."""
        inset = max(0, inset)
        if inset != self.left_inset:
            self.left_inset = inset
            self.strip_layout.setContentsMargins(inset, 0, 0, 0)
            self._layout_strip()

    # --- clavier ---------------------------------------------------------------
    def move_focus(self, index: int, delta: int) -> None:
        """← → : focus sur l'onglet actif voisin, sans bouclage, sans changer de banque."""
        target = index + delta
        visible = len(self.visible_tabs())
        while 0 <= target < visible:
            if self.tabs[target].occupied:
                self.tabs[target].setFocus(Qt.TabFocusReason)
                self.ensure_visible(target)
                return
            target += delta

    # --- défilement -------------------------------------------------------------
    def overflowing(self) -> bool:
        return self.scroll.horizontalScrollBar().maximum() > 0

    def ensure_visible(self, index: int) -> None:
        if 0 <= index < len(self.tabs) and self.tabs[index].isVisibleTo(self):
            self.scroll.ensureWidgetVisible(self.tabs[index], 8, 0)   # flèches hors de la zone visible

    def _scroll_by(self, dx: int) -> None:
        bar = self.scroll.horizontalScrollBar()
        bar.setValue(bar.value() + dx)

    def _layout_strip(self) -> None:
        """Mise en page immédiate : la largeur visible dépend de l'apparition des flèches.

        Non réentrante : la mise en page forcée peut redimensionner la rangée et
        rappeler resizeEvent ; un second passage imbriqué est ignoré (la passe en
        cours, puis le minuteur de mise en vue, terminent le travail).
        """
        if self._laying_out:
            return
        self._laying_out = True
        try:
            self._do_layout_strip()
        finally:
            self._laying_out = False

    def _do_layout_strip(self) -> None:
        self.strip_layout.activate()
        hint = self.strip_layout.sizeHint()
        for _ in range(2):                       # flèches affichées ou masquées : viewport modifié
            self.strip.resize(max(hint.width(), self.scroll.viewport().width()),
                              BODY_HEIGHT + 2 * MARGIN)
            self._update_arrows()
            self.layout().activate()
        self.strip_layout.activate()

    def _update_arrows(self, *_args) -> None:
        bar = self.scroll.horizontalScrollBar()
        over = bar.maximum() > 0
        self.prev_arrow.setVisible(over)
        self.next_arrow.setVisible(over)
        self.prev_arrow.setEnabled(bar.value() > 0)
        self.next_arrow.setEnabled(bar.value() < bar.maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_strip()
        self._ensure_timer.start()

    def sizeHint(self) -> QSize:
        return QSize(400, BODY_HEIGHT + 2 * MARGIN)

