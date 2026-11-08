"""Fiche du concert en consultation (D8, D16, D38, D45, D52, D69 — Design Book v0.47, incrément 2.7b).

Affiche une ConcertSheet préparée par services.concert_service (aucune règle métier ici) :
- bouton « ← CONCERTS » en haut à gauche, comme PARAMÈTRES (D38, v0.48) ; Échap a le même effet (D39) ;
  la fenêtre principale branche l'ouverture et le retour (2.7c) ;
- en-tête : « Touche A03 · Consultation », nom en grand, ligne « salle · jj/mm/aa · N titres » ;
  « Modifier » et « ⋯ » affichés mais inactifs (D69) ; ni projet ni visuel tant qu'ils ne sont
  pas disponibles (D69) ;
- setlist complète : #, Titre, Key, MK, Virus|TI, avec le statut ON/OFF en petite étiquette à
  côté du patch ; valeurs telles que stockées, « — » pour une valeur vide (préparées par le service) ;
- « Infos pratiques » : replié par défaut, sans mémorisation, masqué si tout est vide ; adresse
  avec « Copier » et confirmation discrète ; contacts et autres champs en texte sélectionnable,
  sans lien actif ; présentation 2.9 : résumé quand le bloc est replié (« Passage 21:30 ·
  2 contacts »), rubriques en petites capitales, deux colonnes sur une fiche large (adresse,
  organisateur, notes | horaires en colonne d'heures alignées, une carte par contact) ;
- la fiche défile verticalement, jamais horizontalement (les textes longs passent à la ligne).

Clavier (2.8b) : dès l'ouverture, ↑ ↓, Page précédente / suivante, Début et Fin font défiler la
fiche, sans passage préalable par Tab ; la zone de défilement n'est pas un arrêt de Tab.
Entrée et Espace activent les boutons, une fois par appui ; Échap maintenue ne revient qu'une fois.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from scenix16.services.concert_service import (ConcertSheet, filled, listed_contacts, practical_summary,
                                               schedule_lines)
from scenix16.ui.widgets.keyboard import enable_enter_activation

BACK_LABEL = "← CONCERTS"              # Design Book v0.48 (écran interne : MAIN)
EDIT_LABEL = "Modifier"
MORE_LABEL = "⋯"
INFO_TITLE = "Infos pratiques"
COPY_LABEL = "Copier"
COPIED_MESSAGE = "Adresse copiée"
COPIED_MS = 2000
SHEET_MAX_WIDTH = 1040
INFO_TWO_COLUMNS_MIN = 720      # largeur de fiche à partir de laquelle les infos passent sur deux colonnes
INFO_COLUMN_GAP = 40
SECTION_GAP = 10
TIME_COLUMN_WIDTH = 46
COLUMNS = (("#", 34), ("Titre", None), ("Key", 104), ("MK", 92), ("Virus|TI", 176))

SELECTABLE = Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
SCROLL_KEYS = (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End)


def _label(text: str, name: str, wrap: bool = False, selectable: bool = False) -> QLabel:
    label = QLabel(text, objectName=name)
    label.setTextFormat(Qt.PlainText)                  # jamais de lien actif ni d'interprétation
    label.setOpenExternalLinks(False)
    if wrap:
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    if selectable:
        label.setTextInteractionFlags(SELECTABLE)
    return label


class TrackRow(QFrame):
    """Une ligne de la setlist ; le titre passe à la ligne plutôt que d'élargir la fiche."""

    def __init__(self, cells: tuple[str, str, str, str, str], status: str | None, header: bool = False):
        super().__init__(objectName="SheetHeaderRow" if header else "SheetRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 7, 16, 7)
        row.setSpacing(12)
        self.cells: list[QLabel] = []
        for (title, width), text in zip(COLUMNS, cells):
            name = "SheetHeaderCell" if header else ("SheetTitle" if width is None else "SheetValue")
            cell = _label(text, name, wrap=width is None)
            if width is None:
                row.addWidget(cell, 1)
            else:
                cell.setFixedWidth(width if title != "Virus|TI" or header else width - 46)
                row.addWidget(cell)
                if title == "Virus|TI" and not header:
                    # statut ON/OFF discret à côté du patch (D69) ; « — » s'il est vide
                    name = {"ON": "VirusStatusOn", None: "VirusStatusEmpty"}.get(status, "VirusStatus")
                    self.status = _label(status or "—", name)
                    self.status.setAlignment(Qt.AlignCenter)
                    self.status.setFixedSize(34, 18)
                    self.status.setAccessibleName(f"Virus {status}" if status else "Statut Virus vide")
                    row.addWidget(self.status, 0, Qt.AlignVCenter)
            self.cells.append(cell)


class ConcertSheetPage(QWidget):
    back_requested = Signal()                         # « ← CONCERTS » et Échap

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ConcertSheetPage")
        self.sheet: ConcertSheet | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 24)
        outer.setSpacing(16)
        top = QHBoxLayout()
        self.back_button = QPushButton(BACK_LABEL)
        self.back_button.setProperty("variant", "back")
        self.back_button.clicked.connect(self.back_requested)
        self.back_button.setFocusPolicy(Qt.TabFocus)          # clic : pas de focus ni d'anneau
        enable_enter_activation(self.back_button)
        self.back_button.installEventFilter(self)             # ↑ ↓ … font défiler la fiche
        top.addWidget(self.back_button)
        top.addStretch(1)
        outer.addLayout(top)

        self.scroll = QScrollArea(objectName="SheetScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # jamais de défilement horizontal
        self.scroll.setFocusPolicy(Qt.NoFocus)    # pas d'arrêt de Tab sans anneau (2.8b) ; la page fait défiler
        self.canvas = QWidget(objectName="SheetCanvas")
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.canvas)
        outer.addWidget(self.scroll, 1)
        self.card: QFrame | None = None

        # Échap reproduit le bouton retour (D39), comme dans PARAMÈTRES
        self._escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._escape.setContext(Qt.WidgetWithChildrenShortcut)
        self._escape.setAutoRepeat(False)                     # Échap maintenue : un seul retour
        self._escape.activated.connect(self.back_requested)

    # --- clavier : défilement de la fiche (2.8b) -------------------------------------------------
    def scroll_by_key(self, key) -> bool:
        """↑ ↓ (pas), Page précédente / suivante (page), Début / Fin ; True si la touche est traitée.

        Les répétitions sont conservées : une touche maintenue continue de faire défiler."""
        bar = self.scroll.verticalScrollBar()
        if key == Qt.Key_Up:
            bar.setValue(bar.value() - bar.singleStep())
        elif key == Qt.Key_Down:
            bar.setValue(bar.value() + bar.singleStep())
        elif key == Qt.Key_PageUp:
            bar.setValue(bar.value() - bar.pageStep())
        elif key == Qt.Key_PageDown:
            bar.setValue(bar.value() + bar.pageStep())
        elif key == Qt.Key_Home:
            bar.setValue(bar.minimum())
        elif key == Qt.Key_End:
            bar.setValue(bar.maximum())
        else:
            return False
        return True

    @staticmethod
    def _is_scroll_key(event) -> bool:
        return (event.key() in SCROLL_KEYS
                and not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))

    def keyPressEvent(self, event):
        if self._is_scroll_key(event) and self.scroll_by_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        """Boutons de la fiche : ↑ ↓ … font défiler au lieu de déplacer le focus ; carte de la fiche
        redimensionnée : disposition des infos pratiques sur une ou deux colonnes (2.9)."""
        if event.type() == QEvent.Type.KeyPress and self._is_scroll_key(event):
            return self.scroll_by_key(event.key())
        if event.type() == QEvent.Type.Resize and watched is self.card:
            self._layout_info()
        return super().eventFilter(watched, event)

    # --- contenu ------------------------------------------------------------------------------
    def set_sheet(self, sheet: ConcertSheet | None) -> None:
        """Affiche la fiche (ou rien) ; la fiche précédente est entièrement remplacée."""
        self.sheet = sheet
        if self.card is not None:
            self.canvas_layout.removeWidget(self.card)
            self.card.hide()                           # masquée tout de suite, détruite ensuite
            self.card.deleteLater()
            self.card = None
        self.info_block = None
        while self.canvas_layout.count():
            self.canvas_layout.takeAt(0)
        if sheet is None:
            return
        self.card = self._build_card(sheet)
        self.card.installEventFilter(self)             # largeur de la fiche : une ou deux colonnes
        row = QHBoxLayout()
        row.addWidget(self.card, 1)
        self.canvas_layout.addLayout(row)
        self.canvas_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def update_day_context(self, sheet: ConcertSheet) -> bool:
        """Changement de jour SceniX16 (D73, 2.8a) : même concert, en-tête actualisé sur place.

        Seule l'adresse de touche dépend du jour ; la fiche n'est pas reconstruite (infos
        pratiques, défilement et focus inchangés). Refusé s'il ne s'agit pas du concert affiché.
        """
        if self.sheet is None or self.card is None or sheet.id != self.sheet.id:
            return False
        self.sheet = sheet
        self.heading_label.setText(sheet.heading)
        return True

    def _build_card(self, sheet: ConcertSheet) -> QFrame:
        card = QFrame(objectName="ConcertSheet")
        card.setMaximumWidth(SHEET_MAX_WIDTH)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_head(sheet))
        layout.addWidget(self._build_tracks(sheet))
        self.info_block = self._build_info(sheet) if sheet.has_practical_info else None
        if self.info_block is not None:
            layout.addWidget(self.info_block)
        return card

    def _build_head(self, sheet: ConcertSheet) -> QFrame:
        head = QFrame(objectName="SheetHead")
        row = QHBoxLayout(head)
        row.setContentsMargins(20, 16, 20, 16)
        row.setSpacing(16)
        ident = QVBoxLayout()
        ident.setSpacing(4)
        self.heading_label = _label(sheet.heading, "SheetHeading")
        self.name_label = _label(sheet.name, "SheetName", wrap=True, selectable=True)
        self.meta_label = _label(sheet.meta, "SheetMeta", wrap=True, selectable=True)
        for w in (self.heading_label, self.name_label, self.meta_label):
            ident.addWidget(w)
        row.addLayout(ident, 1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.edit_button = QPushButton(EDIT_LABEL)
        self.edit_button.setProperty("variant", "primary")
        self.more_button = QPushButton(MORE_LABEL)
        self.more_button.setProperty("variant", "ghost")
        self.more_button.setAccessibleName("Autres actions")
        for button in (self.edit_button, self.more_button):
            button.setEnabled(False)                   # affichés mais inactifs en 2.7 (D69)
            button.setFocusPolicy(Qt.NoFocus)
            actions.addWidget(button, 0, Qt.AlignTop)
        row.addLayout(actions)
        return head

    def _build_tracks(self, sheet: ConcertSheet) -> QWidget:
        box = QWidget(objectName="SheetTracks")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(TrackRow(tuple(c[0] for c in COLUMNS), None, header=True))
        self.track_rows: list[TrackRow] = []
        for t in sheet.tracks:                         # tous les titres, sans troncature (D69)
            status = None if t.virus_status == "—" else t.virus_status
            row = TrackRow((t.number, t.title, t.key, t.mk, t.virus), status)
            layout.addWidget(row)
            self.track_rows.append(row)
        return box

    def _build_info(self, sheet: ConcertSheet) -> QFrame:
        """Bloc « Infos pratiques » (D69 ; présentation 2.9) : replié par défaut, sans mémorisation,
        résumé visible quand il est replié ; deux colonnes si la fiche est assez large
        (adresse, organisateur, notes | horaires, contacts), une seule sinon."""
        block = QFrame(objectName="SheetInfo")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(12)
        self.info_toggle = QToolButton(objectName="SheetInfoToggle")
        self.info_toggle.setCheckable(True)
        self.info_toggle.setChecked(False)              # replié par défaut, sans mémorisation (D69)
        self.info_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.info_toggle.toggled.connect(self._toggle_info)
        self.info_toggle.setFocusPolicy(Qt.TabFocus)          # clic : pas d'anneau orange
        enable_enter_activation(self.info_toggle)
        self.info_toggle.installEventFilter(self)
        header.addWidget(self.info_toggle)
        self.info_summary = _label(practical_summary(sheet), "SheetInfoSummary")   # C2
        header.addWidget(self.info_summary, 0, Qt.AlignVCenter)
        header.addStretch(1)
        layout.addLayout(header)

        self.info_body = QWidget(objectName="SheetInfoBody")
        self.info_columns = QBoxLayout(QBoxLayout.LeftToRight, self.info_body)
        self.info_columns.setContentsMargins(6, 0, 6, 0)
        self.info_columns.setSpacing(INFO_COLUMN_GAP)
        self.copy_button = None
        self.copied_label = None
        self.address_label = None
        self.notes_label = None
        self.contact_cards: list[QFrame] = []
        self.schedule_times: list[QLabel] = []
        for column in (self._info_left(sheet), self._info_right(sheet)):
            if column is not None:
                self.info_columns.addWidget(column, 1, Qt.AlignTop)
        layout.addWidget(self.info_body)
        self._toggle_info(False)
        self._copied_timer = QTimer(self)
        self._copied_timer.setSingleShot(True)
        self._copied_timer.setInterval(COPIED_MS)
        self._copied_timer.timeout.connect(lambda: self.copied_label and self.copied_label.hide())
        return block

    @staticmethod
    def _section(title: str, column: QVBoxLayout) -> QHBoxLayout:
        """Titre de rubrique en petites capitales ; renvoie sa ligne (pour « Copier »)."""
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(_label(title.upper(), "SheetInfoLabel"), 0, Qt.AlignVCenter)
        column.addLayout(row)
        return row

    @staticmethod
    def _column() -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget(objectName="SheetInfoColumn")
        column = QVBoxLayout(widget)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        return widget, column

    def _info_left(self, sheet: ConcertSheet) -> QWidget | None:
        """Adresse (avec « Copier » à côté de son titre), organisateur, notes."""
        if not (filled(sheet.address) or filled(sheet.organizer) or filled(sheet.notes)):
            return None
        widget, column = self._column()
        if filled(sheet.address):
            row = self._section("Adresse", column)
            self.copy_button = QPushButton(COPY_LABEL)
            self.copy_button.setProperty("variant", "ghost")
            self.copy_button.setObjectName("SheetCopyButton")
            self.copy_button.setAccessibleName("Copier l'adresse")
            self.copy_button.clicked.connect(self.copy_address)
            self.copy_button.setFocusPolicy(Qt.TabFocus)      # clic : pas d'anneau orange
            enable_enter_activation(self.copy_button)
            self.copy_button.installEventFilter(self)
            row.addWidget(self.copy_button, 0, Qt.AlignVCenter)
            self.copied_label = _label(COPIED_MESSAGE, "SheetCopied")
            self.copied_label.hide()
            row.addWidget(self.copied_label, 0, Qt.AlignVCenter)
            row.addStretch(1)
            self.address_label = _label(sheet.address.strip(), "SheetInfoValue", wrap=True, selectable=True)
            column.addWidget(self.address_label)
            column.addSpacing(SECTION_GAP)
        if filled(sheet.organizer):
            self._section("Organisateur", column).addStretch(1)
            column.addWidget(_label(sheet.organizer.strip(), "SheetInfoValue", wrap=True, selectable=True))
            column.addSpacing(SECTION_GAP)
        if filled(sheet.notes):
            self._section("Notes", column).addStretch(1)
            panel = QFrame(objectName="SheetNotes")
            inner = QVBoxLayout(panel)
            inner.setContentsMargins(12, 10, 12, 10)
            self.notes_label = _label(sheet.notes.strip(), "SheetInfoValue", wrap=True, selectable=True)
            inner.addWidget(self.notes_label)
            column.addWidget(panel)
        column.addStretch(1)
        return widget

    def _info_right(self, sheet: ConcertSheet) -> QWidget | None:
        """Horaires (heure en colonne alignée, puis libellé) et une carte par contact."""
        lines, contacts = schedule_lines(sheet), listed_contacts(sheet)
        if not lines and not contacts:
            return None
        widget, column = self._column()
        if lines:
            self._section("Horaires", column).addStretch(1)
            grid = QGridLayout()
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(4)
            for row, (time, label) in enumerate(lines):
                time_label = _label(time, "SheetScheduleTime", selectable=True)
                time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                time_label.setMinimumWidth(TIME_COLUMN_WIDTH)
                grid.addWidget(time_label, row, 0)
                grid.addWidget(_label(label, "SheetInfoValue", wrap=True, selectable=True), row, 1)
                self.schedule_times.append(time_label)
            grid.setColumnStretch(1, 1)
            column.addLayout(grid)
            column.addSpacing(SECTION_GAP)
        if contacts:
            self._section("Contacts", column).addStretch(1)
            for c in contacts:
                card = QFrame(objectName="SheetContact")
                inner = QVBoxLayout(card)
                inner.setContentsMargins(12, 9, 12, 10)
                inner.setSpacing(2)
                for text, name in ((c.name, "SheetContactName"), (c.role, "SheetContactRole"),
                                   (c.phone, "SheetContactDetail"), (c.email, "SheetContactDetail")):
                    if filled(text):
                        inner.addWidget(_label(text.strip(), name, wrap=True, selectable=True))
                column.addWidget(card)
                self.contact_cards.append(card)
        column.addStretch(1)
        return widget

    def _layout_info(self) -> None:
        """Deux colonnes si la fiche est assez large, une seule sinon (2.9)."""
        if getattr(self, "info_block", None) is None or self.card is None:
            return
        wide = self.card.width() >= INFO_TWO_COLUMNS_MIN
        direction = QBoxLayout.LeftToRight if wide else QBoxLayout.TopToBottom
        if self.info_columns.direction() != direction:
            self.info_columns.setDirection(direction)
            self.info_columns.setSpacing(INFO_COLUMN_GAP if wide else 2 * SECTION_GAP)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_info()

    def showEvent(self, event):
        super().showEvent(event)
        self._layout_info()

    def info_two_columns(self) -> bool:
        return self.info_columns.direction() == QBoxLayout.LeftToRight

    def _toggle_info(self, expanded: bool) -> None:
        self.info_body.setVisible(expanded)
        summary = self.info_summary.text()
        self.info_summary.setVisible(not expanded and bool(summary))
        self.info_toggle.setText(f"{INFO_TITLE}  {'▾' if expanded else '▸'}")
        name = f"{INFO_TITLE}, {'déplié' if expanded else 'replié'}"
        if summary and not expanded:
            name += f" : {summary}"
        self.info_toggle.setAccessibleName(name)
        self._layout_info()

    # --- actions --------------------------------------------------------------------------------
    def copy_address(self) -> None:
        """Copie l'adresse (telle que stockée, sans espaces de bord) avec une confirmation discrète."""
        if self.sheet is None or not self.sheet.address:
            return
        QGuiApplication.clipboard().setText(self.sheet.address.strip())
        if self.copied_label is not None:
            self.copied_label.show()
            self._copied_timer.start()

    # --- état (tests, captures) ---------------------------------------------------------------
    def info_expanded(self) -> bool:
        return getattr(self, "info_block", None) is not None and self.info_body.isVisible()
