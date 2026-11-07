"""Page MAIN : zone centrale du dashboard (section 07).

Contenu (incrément 2.4) : titre « RACCOURCIS · 16 TOUCHES », rangée de 16
touches, titre « CONCERTS » (place du bouton de tri réservée pour 2.5),
grille des 16 emplacements, indicateur vers SETLISTS.
Sans concert à venir, le panneau d'état vide s'affiche sous le titre « CONCERTS »,
au-dessus des 16 emplacements INIT, pour rester lisible sans défilement à
1280 × 800 ; l'ordre des blocs avec concerts n'est pas modifié (il est masqué).

Touche N et emplacement N forment une paire : survol ou focus de l'une met
les deux en évidence ; un clic sur l'une ou l'autre émet la même demande
d'ouverture de fiche (D8), sans écran provisoire avant 2.7 (arbitrage B).
La page affiche une DashboardView calculée par le domaine : aucune règle ici.
Quand la hauteur de la fenêtre ne suffit pas (1024 × 640, mise à l'échelle 200 %),
la zone centrale défile verticalement ; jamais horizontalement.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from scenix16.domain.dashboard import BASE_KEYS, DashboardView
from scenix16.ui.dashboard.sequencer import Sequencer
from scenix16.ui.dashboard.setlists_indicator import EmptyState, SetlistsIndicator
from scenix16.ui.dashboard.slot_grid import SlotGrid
from scenix16.ui.theme import tokens as t

CONTENT_MARGINS = (28, 24, 28, 24)   # marges de la zone centrale (maquette section 07)
KEYS_TITLE = "RACCOURCIS · 16 TOUCHES"
CONCERTS_TITLE = "CONCERTS"


class _Canvas(QWidget):
    """Contenu défilant : recentre la colonne à chaque changement de largeur utile."""

    def __init__(self, on_resize):
        super().__init__(objectName="DashboardCanvas")
        self._on_resize = on_resize

    def resizeEvent(self, event):
        self._on_resize(self.width())
        super().resizeEvent(event)


class DashboardPage(QWidget):
    concert_requested = Signal(int)   # identifiant de la setlist à ouvrir (fiche en 2.7)

    def __init__(self, parent=None, animations: bool | None = None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")
        self.animations = animations
        self.view: DashboardView | None = None
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(objectName="DashboardScroll")
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        page_layout.addWidget(self.scroll)
        self.canvas = _Canvas(self._fit_column)
        outer = QHBoxLayout(self.canvas)
        outer.setContentsMargins(*CONTENT_MARGINS)
        outer.setSpacing(0)
        self.content = QWidget(objectName="DashboardContent")
        self.content.setMaximumWidth(t.CONTENT_MAX_WIDTH)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(14)

        self.keys_title = QLabel(KEYS_TITLE, objectName="SectionTitle")
        self.sequencer = Sequencer()
        concerts_row = QHBoxLayout()
        concerts_row.setContentsMargins(0, 8, 0, 0)
        self.concerts_title = QLabel(CONCERTS_TITLE, objectName="SectionTitle")
        concerts_row.addWidget(self.concerts_title)
        concerts_row.addStretch(1)                 # place du bouton de tri (2.5)
        self.sort_slot = concerts_row
        self.slot_grid = SlotGrid()
        self.indicator = SetlistsIndicator()
        self.empty_state = EmptyState()

        self.content_layout.addWidget(self.keys_title)
        self.content_layout.addWidget(self.sequencer)
        self.content_layout.addLayout(concerts_row)
        self.content_layout.addWidget(self.empty_state)     # visible seulement sans concert à venir
        self.content_layout.addWidget(self.slot_grid)
        self.content_layout.addWidget(self.indicator)
        self.content_layout.addStretch(1)
        outer.addWidget(self.content)
        self._outer = outer
        self.scroll.setWidget(self.canvas)

        # paires touche N / emplacement N
        self._sources: dict[int, set[str]] = {n: set() for n in range(1, BASE_KEYS + 1)}
        for n in range(1, BASE_KEYS + 1):
            key, slot = self.key(n), self.slot(n)
            key.hover_changed.connect(lambda on, n=n: self._pair_source(n, "key-hover", on))
            key.focus_changed.connect(lambda on, n=n: self._pair_source(n, "key-focus", on))
            slot.hover_changed.connect(lambda on, n=n: self._pair_source(n, "slot-hover", on))
            slot.focus_changed.connect(lambda on, n=n: self._pair_source(n, "slot-focus", on))
            key.clicked.connect(lambda _=False, n=n: self._request(n))
            slot.clicked.connect(lambda _=False, n=n: self._request(n))
        self.set_view(None)

    # --- accès ---------------------------------------------------------------
    def key(self, number: int):
        return self.sequencer.keys[number - 1]

    def slot(self, number: int):
        return self.slot_grid.slots[number - 1]

    # --- données ---------------------------------------------------------------
    def set_view(self, view: DashboardView | None) -> None:
        self.view = view
        base = {k.number: k for k in view.base_keys} if view else {}
        for n in range(1, BASE_KEYS + 1):
            dk = base.get(n)
            key, slot = self.key(n), self.slot(n)
            self._sources[n].clear()
            key.set_highlighted(False)
            key.set_concert_state(dk.state if dk else None, animations=self.animations)
            if dk:
                c = dk.concert
                when = c.concert_date.strftime("%d/%m/%Y")
                key.setToolTip("\n".join(x for x in (c.name, c.venue or "", when) if x))
                key.setAccessibleName(f"Touche {n:02d} : {c.name}")
            else:
                key.setToolTip("")
                key.setAccessibleName(f"Touche {n:02d} : libre (INIT)")
            slot.set_concert(dk, animations=self.animations)
        self.indicator.set_view(view)
        self.empty_state.set_view(view)

    def set_open_concert(self, setlist_id: int | None) -> None:
        """Anneau « fiche ouverte » sur la paire du concert (utilisé à partir de 2.7)."""
        for n in range(1, BASE_KEYS + 1):
            slot = self.slot(n)
            is_open = slot.key is not None and slot.key.concert.id == setlist_id
            self.key(n).set_selected(is_open)
            slot.set_selected(is_open)

    # --- couplage ----------------------------------------------------------------
    def _pair_source(self, number: int, source: str, on: bool) -> None:
        """Mise en évidence de la paire tant qu'au moins une source est active."""
        sources = self._sources[number]
        before = bool(sources)
        if on:
            sources.add(source)
        else:
            sources.discard(source)
        after = bool(sources)
        if after != before:
            self.key(number).set_highlighted(after)
            self.slot(number).set_highlighted(after)

    def is_highlighted(self, number: int) -> bool:
        return bool(self._sources[number])

    def _request(self, number: int) -> None:
        slot = self.slot(number)
        if slot.key is not None:
            self.concert_requested.emit(slot.key.concert.id)

    # --- dimensions ----------------------------------------------------------------
    def _fit_column(self, width: int) -> None:
        # la colonne occupe toute la largeur jusqu'à 1600 px, puis reste centrée
        left, top, right, bottom = CONTENT_MARGINS
        extra = max(0, width - left - right - t.CONTENT_MAX_WIDTH)
        self._outer.setContentsMargins(left + extra // 2, top, right + extra - extra // 2, bottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.slot_grid.refresh_mode()
