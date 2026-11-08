"""Fenêtre principale (section 07 du Design Book).

Barre supérieure (56 px : menus, afficheur, paramètres), rail de navigation
(208 px, logo en tête), zone centrale à trois pages (MAIN = dashboard, fiche du
concert en consultation, PARAMÈTRES) et barre d'état (32 px).
Fiche (2.7, D8, D33, D38, D39, D46, D69) : ouverte par un clic ou Entrée sur une touche
ou sa carte ; retour par « ← CONCERTS », Échap ou CONCERTS dans la barre latérale, qui reste
active pendant la consultation ; au retour, banque du concert, paire sélectionnée avec
le rendu « fiche ouverte », focus rendu à la touche si la fiche a été ouverte au clavier.
Fermeture (D66) : un seul chemin, closeEvent, quel que soit le geste (bouton
Fermer, Alt+F4, Fichier › Quitter, Ctrl+Q). Le verrou d'instance est libéré à
la sortie de l'application (app.main).
La fenêtre n'applique aucune règle métier : les chiffres affichés viennent
de services.dashboard_service, avec l'instant courant fourni par `clock`.
Changement de jour (D73, 2.8a) : ui.day_watch signale le passage de 06:00, la sortie de
veille et les changements d'horloge ; la fenêtre recalcule alors tout ce qui en dépend.
Animations en direct (D74, section 09, 2.8c) : le réglage Windows est relu à chaque
WM_SETTINGCHANGE et quand l'application redevient active, sans interrogation périodique ;
le dashboard arrête ou relance aussitôt la pulsation, le fondu et le glissement. La pulsation
est aussi suspendue quand la fenêtre est réduite (et quand le dashboard est masqué).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from scenix16.services import concert_service, dashboard_service
from scenix16.storage import preferences
from scenix16.ui.animation_watch import AnimationWatcher
from scenix16.ui.concert.sheet_page import ConcertSheetPage
from scenix16.ui.dashboard.page import DashboardPage
from scenix16.ui.day_watch import DayWatcher
from scenix16.ui.settings_page import SettingsPage
from scenix16.ui.shell.nav_rail import NavRail
from scenix16.ui.shell.status_line import StatusLine
from scenix16.ui.shell.top_bar import TopBar
from scenix16.ui.theme import tokens as t


class MainWindow(QMainWindow):
    def __init__(self, userdata: Path | None = None, settings_page: SettingsPage | None = None,
                 clock: Callable[[], datetime] = datetime.now,
                 show_diagnostic: bool | None = None):
        super().__init__()
        self.userdata = userdata
        self.clock = clock
        # sens de tri mémorisé (D7) ; « Plus ancien d'abord » par défaut (D1)
        self.sort_order = preferences.load_sort_order(userdata, clock)
        self.setWindowTitle("SceniX16")
        self.setMinimumSize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
        self.resize(t.WINDOW_DEFAULT_WIDTH, t.WINDOW_DEFAULT_HEIGHT)

        body = QWidget(objectName="Body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_bar = TopBar()
        self.menu_bar = self.top_bar.menu_bar
        self.menu_bar.quit_requested.connect(self.close)          # même chemin que le bouton Fermer
        self.menu_bar.about_requested.connect(self.show_about)
        # F10 : focus à la barre de menus, comme Alt (D59) ; inactif sous une boîte modale
        self.f10_shortcut = QShortcut(QKeySequence(Qt.Key_F10), self,
                                      activated=self.menu_bar.activate_from_keyboard)
        self.gear_button = self.top_bar.gear_button
        self.gear_button.clicked.connect(self.show_settings)
        layout.addWidget(self.top_bar)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        self.rail = NavRail()
        self.logo = self.rail.logo                                  # D58
        self.rail.main_requested.connect(self.show_main)
        middle.addWidget(self.rail)

        self.pages = QStackedWidget()
        self.main_page = DashboardPage()
        self.main_page.setFocusPolicy(Qt.ClickFocus)   # reçoit le focus au retour, sans anneau visible
        self.main_page.sort_toggled.connect(self.toggle_sort)
        self.main_page.concert_requested.connect(self.open_concert)
        self.sheet_page = ConcertSheetPage()
        self.sheet_page.setFocusPolicy(Qt.ClickFocus)  # reçoit le focus à l'ouverture, sans anneau
        self.sheet_page.back_requested.connect(self.show_main)
        self._sheet_origin: tuple[int, bool] | None = None   # (concert, ouverte au clavier)
        self.settings_page = settings_page or SettingsPage(userdata)
        self.settings_page.back_requested.connect(self.show_main)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.sheet_page)
        self.pages.addWidget(self.settings_page)
        middle.addWidget(self.pages, 1)
        layout.addLayout(middle, 1)

        self.setCentralWidget(body)

        self.status_line = StatusLine(show_diagnostic)
        self.setStatusBar(self.status_line)

        self.show_main()
        self.update_diagnostic()

        # bascule de 06:00 en direct, avec vérification périodique (D73, 2.8a)
        self.day_watch = DayWatcher(self.clock, self)
        self.day_watch.day_changed.connect(self.on_day_changed)

        # réglage Windows « réduire les animations » suivi en direct (2.8c)
        self.animation_watch = AnimationWatcher(parent=self)
        self.animation_watch.changed.connect(self.on_animation_setting_changed)

    # --- données affichées --------------------------------------------------
    def refresh(self, day_changed: bool = False) -> None:
        """Relit les chiffres (ouverture, retour sur MAIN, après un import, changement de jour)."""
        now = self.clock()
        summary = dashboard_service.load_summary(self.userdata, now, self.sort_order)
        self.top_bar.set_readout(dashboard_service.info_readout(summary, now))
        self.status_line.set_parts(dashboard_service.status_parts(summary))
        self.main_page.set_sort_order(self.sort_order)
        self.main_page.set_view(summary.view, day_changed=day_changed)

    def on_day_changed(self, _day=None) -> None:
        """Nouveau jour SceniX16 (D73) : dashboard, afficheur et barre d'état recalculés.

        Fiche ouverte : elle reste ouverte sur le même concert ; seul son en-tête (adresse de
        touche) est actualisé. Si le concert a quitté le dashboard, l'en-tête devient
        « Consultation » et les règles de retour de 2.7c s'appliquent (D47, D63, D69).
        """
        self.refresh(day_changed=True)
        if self.pages.currentWidget() is self.sheet_page and self.sheet_page.sheet is not None:
            sheet = concert_service.load_concert_sheet(self.userdata, self.sheet_page.sheet.id,
                                                       self.clock(), self.sort_order)
            if sheet is not None:                   # base illisible : la fiche affichée est gardée
                self.sheet_page.update_day_context(sheet)

    def on_animation_setting_changed(self, _enabled=None) -> None:
        """Réglage Windows modifié pendant l'exécution (2.8c) : effet immédiat sur le dashboard."""
        self.main_page.apply_animation_setting()

    def toggle_sort(self) -> None:
        """Inverse le sens de tri, le mémorise (D7) et réaffiche le dashboard.

        Un échec d'écriture ne bloque jamais : le sens choisi reste actif pour la session.
        """
        self.sort_order = dashboard_service.other_order(self.sort_order)
        preferences.save_sort_order(self.userdata, self.sort_order, self.clock)
        self.refresh()

    # --- navigation MAIN <-> PARAMÈTRES -------------------------------------
    def show_settings(self) -> None:
        self.pages.setCurrentWidget(self.settings_page)
        self.settings_page.setFocus()
        self.top_bar.set_gear_active(True)
        self.rail.set_active(None)          # écran secondaire : aucune section active

    def show_main(self) -> None:
        """Retour sur MAIN (libellé CONCERTS, v0.48) : depuis PARAMÈTRES, ou depuis la fiche
        (« ← CONCERTS », Échap, CONCERTS dans la barre latérale)."""
        origin = self._sheet_origin if self.pages.currentWidget() is self.sheet_page else None
        self._sheet_origin = None
        self.pages.setCurrentWidget(self.main_page)
        self.main_page.setFocus()
        self.top_bar.set_gear_active(False)
        self.rail.set_active("main")
        self.refresh()                              # D47 s'applique si le concert a quitté le dashboard
        if origin is not None:
            self.main_page.return_from_sheet(*origin)

    # --- fiche du concert (2.7) -------------------------------------------------
    def open_concert(self, setlist_id: int) -> None:
        """Ouvre la fiche en consultation (D8) ; une seule ouverture à la fois."""
        if self.pages.currentWidget() is self.sheet_page:
            return                                  # protection : fiche déjà ouverte (D69)
        sheet = concert_service.load_concert_sheet(self.userdata, setlist_id, self.clock(), self.sort_order)
        if sheet is None:
            return                                  # identifiant inconnu ou base illisible : on reste
        by_keyboard = self.main_page.last_request_by_keyboard
        self.main_page.hide_preview()
        self._sheet_origin = (setlist_id, by_keyboard)
        self.sheet_page.set_sheet(sheet)
        self.pages.setCurrentWidget(self.sheet_page)
        self.sheet_page.setFocus(Qt.OtherFocusReason)
        self.top_bar.set_gear_active(False)
        self.rail.set_active("main")                # MAIN reste active pendant la fiche (D69)

    # --- Aide › À propos (D59, Q10, Q14) --------------------------------------
    def show_about(self) -> None:
        from scenix16.ui.about_dialog import AboutDialog
        AboutDialog(self).exec()

    # --- fermeture (D66) --------------------------------------------------------
    def confirm_close(self) -> bool:
        """Point d'accroche de la confirmation D38 (modifications en attente).

        Aucun écran d'édition n'existe encore : la fermeture est toujours acceptée.
        Aucune sauvegarde à la fermeture n'est ajoutée tant qu'aucune politique de
        sauvegarde n'est définie (Design Book v0.43, D66).
        """
        return True

    def closeEvent(self, event):
        """Chemin unique de fermeture : bouton Fermer, Alt+F4, Fichier › Quitter, Ctrl+Q."""
        if not self.confirm_close():
            event.ignore()                  # « Continuer l'édition » (D38)
            return
        super().closeEvent(event)

    # --- diagnostic (développement uniquement) ------------------------------
    def update_diagnostic(self) -> None:
        screen = self.screen()
        self.status_line.update_diagnostic(screen.devicePixelRatio() if screen else 1.0)

    def changeEvent(self, event):
        kind = event.type()
        if kind == QtCore.QEvent.Type.DevicePixelRatioChange:
            self.update_diagnostic()
        elif kind == QtCore.QEvent.Type.WindowStateChange:
            self.main_page.update_pulse()           # fenêtre réduite : pulsation suspendue (2.8c)
        elif kind == QtCore.QEvent.Type.ActivationChange and self.isActiveWindow():
            watch = getattr(self, "animation_watch", None)
            if watch is not None:
                watch.refresh()                     # filet de sécurité : réglage relu au retour
        super().changeEvent(event)
