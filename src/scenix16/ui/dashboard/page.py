"""Page MAIN : zone centrale du dashboard (Design Book v0.42, section 07).

Contenu : boutons de banque (2.6, D67), rangée de 16 touches sans titre (D62),
titre « CONCERTS » avec le bouton de tri à droite (2.5), grille des 16
emplacements, indicateur vers SETLISTS.
Sans concert à venir, le panneau d'état vide s'affiche sous le titre « CONCERTS »,
au-dessus des 16 emplacements INIT, pour rester lisible sans défilement à
1280 × 800 ; l'ordre des blocs avec concerts n'est pas modifié (il est masqué).

Touche N et emplacement N forment une paire : survol ou focus de l'une met
les deux en évidence ; un clic sur l'une ou l'autre émet la même demande
d'ouverture de fiche (D8), que la fenêtre principale traite (fiche en consultation, 2.7).
La page affiche une DashboardView calculée par le domaine : aucune règle ici.
Le bouton de tri émet sort_toggled ; la fenêtre décide du sens, le mémorise et
le renvoie (set_sort_order). Au changement de sens, les cartes glissent en
180 ms (reorder_animation), sauf si les animations sont réduites ; les touches
sont actualisées immédiatement.
Banques (D44 à D47) : les touches et les emplacements affichent la banque
sélectionnée ; changement de banque instantané ; ← → passent d'une banque à
l'autre, Page précédente / Page suivante vont à la banque occupée voisine dès
que le focus est dans le dashboard ; A au lancement, banque conservée pendant
la session, repli sur la dernière banque occupée (puis A) si elle se vide.
Aperçu au survol (D64) : 350 ms après la mise en évidence d'une paire occupée
(survol ou focus clavier), un aperçu s'attache à la carte de la paire ; il se
ferme à la sortie, au clic, à Échap, au défilement, au changement de banque ou
de tri. Après Échap, il ne revient qu'à la prochaine mise en évidence. Échap
ne fait rien d'autre sur le dashboard.
Clavier (2.8b, D46, D65, section 09) : un seul arrêt de Tab pour la rangée de touches et un
seul pour la grille de cartes, sur la paire sélectionnée de la banque affichée, sinon sur la
première paire active ; Maj+Tab est symétrique. Les flèches parcourent ensuite chaque groupe :
touches ← → (D46), ↓ vers la carte ; cartes ← → en continu entre banques, ↑ ↓ vers la rangée
voisine, ↑ depuis la première rangée vers la touche (D65). Une cible INIT ne déplace jamais le focus.
Animations (section 09, D74 — 2.8c) : pulsation de la paire sélectionnée, fondu de l'aperçu
et glissement du tri suivent en direct le réglage Windows (apply_animation_setting) ; en mode
réduit, le point reste fixe à pleine opacité, le délai de 350 ms de l'aperçu est conservé et
seul son fondu disparaît. La pulsation ne tourne que si le dashboard est affiché et la fenêtre
non réduite (update_pulse) ; elle reprend sans transition, à pleine opacité.
Quand la hauteur de la fenêtre ne suffit pas (1024 × 640, mise à l'échelle 200 %),
la zone centrale défile verticalement ; jamais horizontalement.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from scenix16.domain.dashboard import (BASE_KEYS, MIN_TABS, ConcertState, DashboardKey, DashboardView,
                                       SortOrder,
                                       bank_label, fallback_bank, step_bank)
from scenix16.services.dashboard_service import (key_accessible_name, preview_content,
                                                 preview_description, slot_accessible_name)
from scenix16.ui.dashboard.bank_tabs import BankTabs
from scenix16.ui.dashboard.concert_preview import (PREVIEW_DELAY_MS, ConcertPreview,
                                                   preview_geometry, preview_width)
from scenix16.ui.dashboard.reorder_animation import ReorderOverlay, snapshot
from scenix16.ui.dashboard.sequencer import Sequencer
from scenix16.ui.dashboard.setlists_indicator import EmptyState, SetlistsIndicator
from scenix16.ui.dashboard.slot_grid import SlotGrid
from scenix16.ui.system import animations_enabled
from scenix16.ui.theme import tokens as t
from scenix16.ui.widgets.bank_tab import MARGIN as TAB_MARGIN
from scenix16.ui.widgets.sort_button import SortButton
from scenix16.ui.widgets.step_key import GROUP_COLORS

CONTENT_MARGINS = (28, 24, 28, 24)   # marges de la zone centrale (maquette section 07)
PAGE_KEYS = {Qt.Key_PageUp: -1, Qt.Key_PageDown: +1}     # Page précédente / suivante (D46)
CONCERTS_TITLE = "CONCERTS"


class _Canvas(QWidget):
    """Contenu défilant : recentre la colonne à chaque changement de largeur utile."""

    def __init__(self, on_resize):
        super().__init__(objectName="DashboardCanvas")
        self._on_resize = on_resize

    def resizeEvent(self, event):
        self._on_resize(self.width())
        super().resizeEvent(event)


def initial_selection(bank_a: tuple[DashboardKey, ...]) -> int | None:
    """Présélection au lancement, dans la banque A (D47, D63 v0.45) : concert du jour, sinon
    prochain concert, sinon premier concert actif de la banque A ; banque A vide : aucune."""
    ordered = sorted(bank_a, key=lambda k: k.position)
    for state in (ConcertState.TODAY, ConcertState.NEXT):
        for dk in ordered:
            if dk.state is state:
                return dk.concert.id
    return ordered[0].concert.id if ordered else None


class DashboardPage(QWidget):
    concert_requested = Signal(int)   # identifiant de la setlist à ouvrir (fiche en 2.7)
    sort_toggled = Signal()            # demande d'inversion du sens de tri (D1, D7)

    def __init__(self, parent=None, animations: bool | None = None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")
        self.animations = animations
        self.view: DashboardView | None = None
        self.bank = 0                     # banque affichée (D47) : A au lancement
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

        self.bank_tabs = BankTabs()                  # créée avant les touches : ordre de tabulation
        self.bank_tabs.bank_requested.connect(self.select_bank)
        self.sequencer = Sequencer()
        self.sequencer.edge_reached.connect(self._cross_bank)
        self.sequencer.card_requested.connect(self._focus_card)
        self.sequencer.geometry_changed.connect(self._align_tabs)
        keys_block = QVBoxLayout()
        keys_block.setContentsMargins(0, 0, 0, 0)
        keys_block.setSpacing(6)
        keys_block.addWidget(self.bank_tabs)
        keys_block.addWidget(self.sequencer)
        concerts_row = QHBoxLayout()
        concerts_row.setContentsMargins(0, 8, 0, 0)
        self.concerts_title = QLabel(CONCERTS_TITLE, objectName="SectionTitle")
        concerts_row.addWidget(self.concerts_title)
        concerts_row.addStretch(1)
        self.sort_button = SortButton()
        self.sort_button.clicked.connect(self.sort_toggled)
        concerts_row.addWidget(self.sort_button, 0, Qt.AlignVCenter)
        self.sort_slot = concerts_row
        self.reorder: ReorderOverlay | None = None
        self.slot_grid = SlotGrid()
        self.slot_grid.edge_reached.connect(self._cross_bank_cards)
        self.slot_grid.key_requested.connect(self._focus_key)
        self.indicator = SetlistsIndicator()
        self.empty_state = EmptyState()

        self.content_layout.addLayout(keys_block)          # pas de titre (D62)
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
        # paire sélectionnée (D63, v0.45) : suit le concert lui-même (tri, banques)
        self.selected_concert: int | None = None
        self.open_concert: int | None = None    # rendu « fiche ouverte » (D63, D69), par concert
        self.last_request_by_keyboard = False   # mode de la dernière ouverture demandée (D69)
        self._selection_started = False         # présélection faite une fois par session
        for n in range(1, BASE_KEYS + 1):
            key, slot = self.key(n), self.slot(n)
            key.hover_changed.connect(lambda on, n=n: self._pair_source(n, "key-hover", on))
            key.focus_changed.connect(lambda on, n=n: self._pair_source(n, "key-focus", on))
            slot.hover_changed.connect(lambda on, n=n: self._pair_source(n, "slot-hover", on))
            slot.focus_changed.connect(lambda on, n=n: self._pair_source(n, "slot-focus", on))
            key.clicked.connect(lambda _=False, n=n, w=key: self._request(n, w))
            slot.clicked.connect(lambda _=False, n=n, w=slot: self._request(n, w))
        # Page précédente / suivante : dès que le focus est dans le dashboard (arbitrage 5).
        # Touches, cartes, onglets et bouton ignorent ces touches, qui remontent jusqu'à la
        # zone de défilement : elles y sont interceptées avant le défilement vertical.
        # La rangée d'onglets a sa propre zone de défilement (horizontale) : même règle.
        self.scroll.installEventFilter(self)
        self.bank_tabs.scroll.installEventFilter(self)

        # aperçu au survol (D64)
        self.preview = ConcertPreview(self)
        self._preview_pending: int | None = None      # paire en attente des 350 ms
        self._preview_suppressed: int | None = None   # paire fermée par Échap
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._show_preview)
        self.scroll.verticalScrollBar().valueChanged.connect(self.hide_preview)
        self.set_view(None)

    @staticmethod
    def _page_delta(event) -> int | None:
        if (event.key() in PAGE_KEYS and not event.modifiers()
                & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            return PAGE_KEYS[event.key()]
        return None

    def eventFilter(self, watched, event):
        if watched in (self.scroll, self.bank_tabs.scroll) and event.type() == QEvent.Type.KeyPress:
            delta = self._page_delta(event)
            if delta is not None:
                self.page_bank(delta)
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if not event.isAutoRepeat():           # Échap maintenue : un seul effet (2.8b)
                self.dismiss_preview()             # Échap : ferme l'aperçu, rien d'autre
            event.accept()
            return
        delta = self._page_delta(event)            # focus sur la page elle-même
        if delta is not None:
            self.page_bank(delta)
        else:
            super().keyPressEvent(event)

    # --- accès ---------------------------------------------------------------
    def key(self, number: int):
        return self.sequencer.keys[number - 1]

    def slot(self, number: int):
        return self.slot_grid.slots[number - 1]

    # --- données ---------------------------------------------------------------
    def set_sort_order(self, order: SortOrder) -> None:
        self.sort_button.set_order(order)

    def _animations_on(self) -> bool:
        return animations_enabled() if self.animations is None else self.animations

    def _should_glide(self, view: DashboardView | None, bank: int) -> bool:
        """Glissement réservé au changement de sens de tri (2.5), dans la banque affichée."""
        previous = self.view
        return (self._animations_on() and self.isVisible() and previous is not None
                and view is not None and previous.order is not view.order
                and bool(previous.bank(self.bank) or view.bank(bank)))

    def stop_reorder(self) -> None:
        if self.reorder is not None:
            self.reorder.stop()
            self.reorder = None

    def set_view(self, view: DashboardView | None, day_changed: bool = False) -> None:
        """Affiche une vue du dashboard.

        day_changed (D73, 2.8a) : vue recalculée au changement de jour SceniX16. La sélection
        reste sur son concert s'il est toujours sur le dashboard ; sinon la présélection D63
        s'applique de nouveau. Un rendu « fiche ouverte » dont le concert est parti est retiré.
        """
        self.stop_reorder()
        bank = fallback_bank(self.bank, view.occupied_banks if view else 0)   # D47
        glide = self._should_glide(view, bank)
        before = snapshot(self.slot_grid)[0] if glide else None
        focused = self._focused_pair()
        self.view = view
        self.bank = bank
        self._update_selection_for_view(reselect=day_changed)
        if day_changed and self.open_concert is not None and (
                view is None or view.key_of_concert(self.open_concert) is None):
            self.open_concert = None
        self._render_bank()
        self._restore_focus(focused)
        self.indicator.set_view(view)
        self.empty_state.set_view(view)
        if glide:
            after, free_after = snapshot(self.slot_grid)
            self.reorder = ReorderOverlay(self.slot_grid, before, after, free_after)
            self.reorder.finished.connect(self._reorder_finished)

    def _reorder_finished(self) -> None:
        self.reorder = None

    # --- banques (D44 à D47) ------------------------------------------------------
    def displayed_keys(self) -> tuple[DashboardKey, ...]:
        return self.view.bank(self.bank) if self.view else ()

    def _render_bank(self) -> None:
        """Touches, emplacements et boutons de banque de la banque affichée."""
        self.hide_preview()                        # changement de banque, de tri ou rafraîchissement
        by_position = {k.position: k for k in self.displayed_keys()}
        for n in range(1, BASE_KEYS + 1):
            dk = by_position.get(n)
            key, slot = self.key(n), self.slot(n)
            description = preview_description(dk) if dk else ""
            key.set_concert_state(dk.state if dk else None, animations=self.animations)
            key.setToolTip("")                     # l'aperçu remplace l'info-bulle (D64)
            key.setAccessibleName(key_accessible_name(self.bank, n, dk))
            key.setAccessibleDescription(description)
            slot.set_concert(dk, animations=self.animations)
            slot.setAccessibleName(slot_accessible_name(self.bank, n, dk))
            slot.setAccessibleDescription(description)
        self.sequencer.setAccessibleName(f"Touches, banque {bank_label(self.bank)}")
        self._resync_pairs()
        self._apply_selection()
        self._apply_open_concert()                 # « fiche ouverte » suit son concert
        self._reschedule_focused_preview()
        if self.view:
            counts = [len(self.view.bank(i)) for i in range(self.view.tab_count)]
        else:
            counts = [0] * MIN_TABS
        self.bank_tabs.set_tabs(counts, self.bank)

    def select_bank(self, index: int, focus: str | None = None, cards: bool = False) -> bool:
        """Affiche la banque `index` si elle est occupée ; changement instantané (arbitrage 7).

        focus : None (inchangé), "first" ou "last" (touche active de la nouvelle banque, ou
        carte active si `cards`, pour ← → sur les cartes, D65).
        """
        if self.view is None or not 0 <= index < self.view.occupied_banks:
            return False
        if index != self.bank:
            self.stop_reorder()
            self.bank = index
            self._preview_suppressed = None        # autre banque : la paire focalisée montre un autre concert
            self._render_bank()
        if focus:
            group = self.slot_grid if cards else self.sequencer
            group.focus_first(last=(focus == "last"))
            self._select_focused_pair()        # navigation clavier : la sélection suit, même si le
        return True                            # widget focalisé n'a pas changé (touche 01, D63 v0.45)

    def _select_focused_pair(self) -> None:
        for n in range(1, BASE_KEYS + 1):
            if self._sources[n] & {"key-focus", "slot-focus"}:
                self.select_pair(n)
                return

    def page_bank(self, delta: int) -> None:
        """Page précédente / suivante (D46) : banque occupée voisine, banques vides ignorées."""
        if self.view is None:
            return
        target = step_bank(self.view.bank_occupancy(), self.bank, delta)
        if target != self.bank:
            self.select_bank(target, focus="first")

    def _cross_bank(self, delta: int) -> None:
        """← sur la première touche active, → sur la dernière : banque voisine (A16 ↔ B01)."""
        if self.view is None:
            return
        target = self.bank + delta
        if 0 <= target < self.view.occupied_banks:          # sans bouclage
            self.select_bank(target, focus="first" if delta > 0 else "last")

    def _cross_bank_cards(self, delta: int) -> None:
        """← sur la première carte active, → sur la dernière : banque voisine, focus sur ses
        cartes (D65, Q15) ; aucun bouclage aux extrémités de l'ensemble des banques."""
        if self.view is None:
            return
        target = self.bank + delta
        if 0 <= target < self.view.occupied_banks:
            self.select_bank(target, focus="first" if delta > 0 else "last", cards=True)

    def _focus_card(self, number: int) -> None:
        """↓ sur une touche : carte de même numéro (D65) ; INIT : le focus reste en place."""
        slot = self.slot(number)
        if not slot.is_init:
            slot.setFocus(Qt.TabFocusReason)

    def _focus_key(self, number: int) -> None:
        """↑ depuis la première rangée de cartes : touche de même numéro (D65)."""
        key = self.key(number)
        if not key.is_init:
            key.setFocus(Qt.TabFocusReason)

    def show_concert_bank(self, setlist_id: int) -> bool:
        """Retour d'une fiche (D46, branché en 2.7) : banque du concert consulté.

        S'il n'est plus sur le dashboard, la banque affichée reste soumise à D47.
        """
        index = self.view.bank_of_concert(setlist_id) if self.view else None
        return index is not None and self.select_bank(index)

    def _focused_pair(self) -> tuple[str, int] | None:
        for n in range(1, BASE_KEYS + 1):
            if self.key(n).hasFocus():
                return "key", n
            if self.slot(n).hasFocus():
                return "slot", n
        return None

    def _restore_focus(self, focused: tuple[str, int] | None) -> None:
        """Touche ou carte focalisée devenue INIT : première touche active, sinon le dashboard."""
        if focused is None:
            return
        kind, n = focused
        widget = self.key(n) if kind == "key" else self.slot(n)
        if widget.is_init or not widget.hasFocus():
            if not self.sequencer.focus_first():
                self.setFocus(Qt.OtherFocusReason)

    def _align_tabs(self) -> None:
        """Premier onglet aligné sur la première touche."""
        self.bank_tabs.set_left_inset(round(self.sequencer.columns.left[0]) - TAB_MARGIN)

    def set_open_concert(self, setlist_id: int | None) -> None:
        """Rendu « fiche ouverte » (filet crème, bordure de groupe) sur la paire du concert (D63, D69).

        Rattaché au concert, et non à une position : il suit le tri et les banques.
        """
        self.open_concert = setlist_id
        self._apply_open_concert()

    def _apply_open_concert(self) -> None:
        setlist_id = self.open_concert
        for n in range(1, BASE_KEYS + 1):
            slot = self.slot(n)
            is_open = slot.key is not None and slot.key.concert.id == setlist_id
            self.key(n).set_selected(is_open)
            slot.set_selected(is_open)

    # --- couplage ----------------------------------------------------------------
    def _resync_pairs(self) -> None:
        """Rétablit la mise en évidence des paires d'après le survol et le focus réels.

        Après un rafraîchissement ou un changement de tri, la paire N peut porter un
        autre concert, ou devenir INIT, alors que la souris ou le focus n'ont pas bougé :
        les sources sont recalculées, et touche et carte sont remises en cohérence.
        """
        for n in range(1, BASE_KEYS + 1):
            key, slot = self.key(n), self.slot(n)
            key.hovered = key.underMouse() and not key.is_init
            sources = self._sources[n]
            sources.clear()
            if not key.is_init and not slot.is_init:
                if key.hovered:
                    sources.add("key-hover")
                if key.hasFocus():
                    sources.add("key-focus")
                if slot.underMouse():
                    sources.add("slot-hover")
                if slot.hasFocus():
                    sources.add("slot-focus")
            self._apply_highlight(n)

    def _pair_source(self, number: int, source: str, on: bool) -> None:
        """Mise en évidence de la paire tant qu'au moins une source est active."""
        sources = self._sources[number]
        before = bool(sources)
        if on:
            sources.add(source)
        else:
            sources.discard(source)
        after = bool(sources)
        if on and source in ("key-focus", "slot-focus"):
            self.select_pair(number)               # navigation clavier : la sélection suit (D63)
            self._update_tab_stops()               # l'arrêt de Tab suit le focus (2.8b)
        if after != before:
            self._apply_highlight(number)
            if after:
                self._schedule_preview(number)
            else:
                self._clear_preview(number)

    def is_highlighted(self, number: int) -> bool:
        """Survol ou focus clavier sur la paire (déclenche l'aperçu, D64)."""
        return bool(self._sources[number])

    def is_emphasized(self, number: int) -> bool:
        """Paire mise en évidence à l'écran : survol, focus clavier ou sélection (D63)."""
        return self.is_highlighted(number) or self.selected_position() == number

    def _apply_highlight(self, number: int) -> None:
        on = self.is_emphasized(number)
        self.key(number).set_highlighted(on)
        self.slot(number).set_highlighted(on)

    def _request(self, number: int, widget=None) -> None:
        """Clic ou Entrée sur la touche ou sur sa carte : même effet (D8, v0.45)."""
        self.hide_preview()
        slot = self.slot(number)
        if slot.key is not None:
            self.last_request_by_keyboard = bool(getattr(widget, "activated_by_keyboard", False))
            self.select_pair(number)
            self.concert_requested.emit(slot.key.concert.id)

    # --- paire sélectionnée (D63, D57, D11 — v0.45) --------------------------------
    def selected_position(self) -> int | None:
        """Position (1 à 16) de la paire sélectionnée dans la banque affichée, sinon None."""
        if self.selected_concert is None:
            return None
        for dk in self.displayed_keys():
            if dk.concert.id == self.selected_concert:
                return dk.position
        return None

    def select_pair(self, number: int) -> None:
        slot = self.slot(number)
        if slot.key is not None:
            self.select_concert(slot.key.concert.id)

    def select_concert(self, setlist_id: int | None) -> None:
        if setlist_id == self.selected_concert:
            return
        self.selected_concert = setlist_id
        if self.open_concert is not None and setlist_id != self.open_concert:
            self.set_open_concert(None)            # autre paire sélectionnée : fin de « fiche ouverte »
        self._apply_selection()

    def return_from_sheet(self, setlist_id: int, by_keyboard: bool) -> None:
        """Retour d'une fiche (D46, D47, D63, D69) : banque du concert, paire sélectionnée avec le
        rendu « fiche ouverte », focus rendu à la touche seulement si la fiche a été ouverte au
        clavier ; l'aperçu n'est pas rouvert.
        """
        self.hide_preview()
        if self.view is None or self.view.key_of_concert(setlist_id) is None:
            self.set_open_concert(None)            # concert absent : D47 a déjà choisi la banque
            self.setFocus(Qt.OtherFocusReason)
            return
        self.show_concert_bank(setlist_id)
        self.select_concert(setlist_id)
        self.set_open_concert(setlist_id)
        position = self.selected_position()
        if by_keyboard and position is not None:
            self._preview_suppressed = position    # pas d'aperçu automatique au retour
            self.key(position).setFocus(Qt.TabFocusReason)
        else:
            self.setFocus(Qt.OtherFocusReason)
        self.hide_preview()

    def _apply_selection(self) -> None:
        """Seule la paire sélectionnée pulse et reste mise en évidence (fixe sans animations)."""
        self.update_pulse()
        for n in range(1, BASE_KEYS + 1):
            self._apply_highlight(n)
        self._update_tab_stops()

    def pulse_allowed(self) -> bool:
        """Pulsation permise : animations autorisées, dashboard affiché, fenêtre non réduite (2.8c)."""
        window = self.window()
        minimized = window is not self and bool(window.windowState() & Qt.WindowMinimized)
        return self._animations_on() and self.isVisible() and not minimized

    def update_pulse(self) -> None:
        """Démarre ou arrête la pulsation selon la sélection, le réglage et la visibilité (2.8c).

        À l'arrêt, le point reste à pleine opacité ; à la reprise, la pulsation repart de la
        pleine opacité : aucun saut visible."""
        position = self.selected_position()
        animations = self.pulse_allowed()
        for n in range(1, BASE_KEYS + 1):
            on = n == position
            self.key(n).set_pulsing(on, animations=animations)
            self.slot(n).set_pulsing(on, animations=animations)

    def apply_animation_setting(self) -> None:
        """Réglage Windows modifié pendant l'exécution (2.8c).

        Réduction demandée : pulsation arrêtée, fondu en cours terminé à pleine opacité,
        glissement en cours terminé à sa position finale. Animations rétablies : la pulsation
        reprend si les conditions sont réunies ; fondu et glissement reviennent à leur prochain
        déclenchement."""
        if not self._animations_on():
            self.preview.finish_fade()
            self.stop_reorder()
        self.update_pulse()

    def tab_stop(self) -> int | None:
        """Numéro de la paire qui porte l'arrêt de Tab des touches et des cartes (2.8b) :
        paire focalisée, sinon paire sélectionnée de la banque affichée, sinon première paire
        active ; None si la banque est vide."""
        focused = self._focused_pair()
        if focused is not None and not self.key(focused[1]).is_init:
            return focused[1]
        position = self.selected_position()
        if position is not None and not self.key(position).is_init:
            return position
        return next((n for n in range(1, BASE_KEYS + 1) if not self.key(n).is_init), None)

    def _update_tab_stops(self) -> None:
        """Un seul arrêt de Tab par groupe ; les autres touches et cartes restent atteignables
        par les flèches (setFocus ne dépend pas de la politique de focus)."""
        anchor = self.tab_stop()
        for n in range(1, BASE_KEYS + 1):
            key, slot = self.key(n), self.slot(n)
            key.setFocusPolicy(Qt.TabFocus if n == anchor and not key.is_init else Qt.NoFocus)
            slot.setFocusPolicy(Qt.TabFocus if n == anchor and not slot.is_init else Qt.NoFocus)

    def _update_selection_for_view(self, reselect: bool = False) -> None:
        """Présélection au lancement ; sélection retirée si son concert quitte le dashboard.

        reselect (changement de jour, D73) : si le concert sélectionné a quitté le dashboard, ou
        si rien n'était sélectionné, la présélection D63 s'applique à la nouvelle vue.
        """
        view = self.view
        if self.selected_concert is not None and (
                view is None or view.bank_of_concert(self.selected_concert) is None):
            self.selected_concert = None
        if reselect and self.selected_concert is None:
            self._selection_started = False
        if self._selection_started or view is None or not view.bank(0):
            return
        self._selection_started = True
        self.selected_concert = initial_selection(view.bank(0))

    # --- aperçu au survol (D64) --------------------------------------------------
    def _schedule_preview(self, number: int) -> None:
        """Nouvelle mise en évidence d'une paire : aperçu dans 350 ms."""
        if self._preview_suppressed is not None and self._preview_suppressed != number:
            self._preview_suppressed = None
        if self._preview_suppressed == number or self.key(number).is_init:
            return
        if self.preview.number is not None and self.preview.number != number:
            self.preview.dismiss()
        self._preview_pending = number
        self._preview_timer.start()

    def _clear_preview(self, number: int) -> None:
        """La paire n'est plus mise en évidence : fermeture, et fin de la suppression par Échap."""
        if self._preview_suppressed == number:
            self._preview_suppressed = None
        if self._preview_pending == number:
            self._preview_timer.stop()
            self._preview_pending = None
        if self.preview.number == number:
            self.preview.dismiss()

    def _reschedule_focused_preview(self) -> None:
        """Après un rendu, l'aperçu suit le focus (D64), même si le widget focalisé n'a pas changé.

        Page suivante depuis la touche 01 garde le focus sur la touche 01 : aucun
        événement de focus ne relance l'aperçu, qui est donc reprogrammé ici pour la
        paire focalisée. Une fermeture par Échap reste respectée (_schedule_preview).
        """
        for n in range(1, BASE_KEYS + 1):
            if self._sources[n] & {"key-focus", "slot-focus"}:
                self._schedule_preview(n)
                return

    def hide_preview(self) -> None:
        self._preview_timer.stop()
        self._preview_pending = None
        self.preview.dismiss()

    def dismiss_preview(self) -> None:
        """Échap : ferme l'aperçu ; il ne revient qu'à la prochaine mise en évidence."""
        number = self.preview.number if self.preview.number is not None else self._preview_pending
        if number is not None:
            self._preview_suppressed = number
        self.hide_preview()

    def preview_visible(self) -> bool:
        return self.preview.isVisible()

    def _rect_in_page(self, widget, rect) -> QRect:
        top_left = widget.mapTo(self, rect.topLeft().toPoint())
        return QRect(top_left, rect.size().toSize())

    def _show_preview(self) -> None:
        number, self._preview_pending = self._preview_pending, None
        if (number is None or not self.is_highlighted(number) or self.key(number).is_init
                or not self.isVisible()):
            return
        slot = self.slot(number)
        anchor = self._rect_in_page(slot, slot.card_rect())
        viewport = self.scroll.viewport()
        area = QRect(viewport.mapTo(self, viewport.rect().topLeft()), viewport.size())
        sources = self._sources[number]
        avoid = None
        if sources & {"key-hover", "key-focus"} and not sources & {"slot-hover", "slot-focus"}:
            key = self.key(number)
            avoid = self._rect_in_page(key, key.body_rect())
        self.preview.set_content(preview_content(slot.key), GROUP_COLORS[slot.group % 4],
                                 preview_width(anchor.width(), area.width()))
        self.preview.number = number
        self.preview.present(preview_geometry(anchor, self.preview.size(), area, avoid),
                             animated=self._animations_on())

    def hideEvent(self, event):
        self.hide_preview()
        super().hideEvent(event)
        self.update_pulse()                 # fiche, PARAMÈTRES ou fenêtre réduite : suspendue

    def showEvent(self, event):
        super().showEvent(event)
        self.update_pulse()                 # retour sur CONCERTS : reprise si une paire est sélectionnée

    # --- dimensions ----------------------------------------------------------------
    def _fit_column(self, width: int) -> None:
        """Colonne pleine largeur jusqu'à 1600 px, puis centrée.

        La largeur de la colonne ne dépend pas de la barre de défilement verticale :
        sa place est toujours réservée. Sinon, la barre qui apparaît réduit la
        largeur, donc la hauteur des touches, donc le besoin de défiler, et la barre
        disparaît puis réapparaît sans fin (instabilité constatée en 2.6b).
        """
        left, top, right, bottom = CONTENT_MARGINS
        reserve = self.scroll.verticalScrollBar().sizeHint().width()
        usable = min(width, self.scroll.width() - reserve)        # largeur utile, barre comprise
        column = max(0, min(t.CONTENT_MAX_WIDTH, usable - left - right))
        free = width - column - left - right                      # place restante (centrage)
        self._outer.setContentsMargins(left + free // 2, top, right + free - free // 2, bottom)

    def resizeEvent(self, event):
        self.stop_reorder()                 # les positions changent : fin immédiate
        self.hide_preview()
        super().resizeEvent(event)
        self.slot_grid.refresh_mode()
