"""Fenêtre principale (section 07 du Design Book).

Barre supérieure (56 px), rail de navigation (208 px), zone centrale à deux
pages (MAIN = dashboard, PARAMÈTRES) et barre d'état (32 px).
La fenêtre n'applique aucune règle métier : les chiffres affichés viennent
de services.dashboard_service, avec l'instant courant fourni par `clock`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from scenix16.services import dashboard_service
from scenix16.ui.dashboard.page import DashboardPage
from scenix16.ui.settings_page import SettingsPage
from scenix16.ui.shell.nav_rail import NavRail
from scenix16.ui.shell.status_line import StatusLine
from scenix16.ui.shell.top_bar import GEAR_SIZE, LOGO_HEIGHT, LogoLabel, TopBar  # noqa: F401
from scenix16.ui.theme import tokens as t


class MainWindow(QMainWindow):
    def __init__(self, userdata: Path | None = None, settings_page: SettingsPage | None = None,
                 clock: Callable[[], datetime] = datetime.now,
                 show_diagnostic: bool | None = None):
        super().__init__()
        self.userdata = userdata
        self.clock = clock
        self.setWindowTitle("SceniX16")
        self.setMinimumSize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
        self.resize(t.WINDOW_DEFAULT_WIDTH, t.WINDOW_DEFAULT_HEIGHT)

        body = QWidget(objectName="Body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_bar = TopBar()
        self.logo = self.top_bar.logo
        self.gear_button = self.top_bar.gear_button
        self.gear_button.clicked.connect(self.show_settings)
        layout.addWidget(self.top_bar)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        self.rail = NavRail()
        self.rail.main_requested.connect(self.show_main)
        middle.addWidget(self.rail)

        self.pages = QStackedWidget()
        self.main_page = DashboardPage()
        self.main_page.setFocusPolicy(Qt.ClickFocus)   # reçoit le focus au retour, sans anneau visible
        self.settings_page = settings_page or SettingsPage(userdata)
        self.settings_page.back_requested.connect(self.show_main)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.settings_page)
        middle.addWidget(self.pages, 1)
        layout.addLayout(middle, 1)

        self.setCentralWidget(body)

        self.status_line = StatusLine(show_diagnostic)
        self.setStatusBar(self.status_line)

        self.show_main()
        self.update_diagnostic()

    # --- données affichées --------------------------------------------------
    def refresh(self) -> None:
        """Relit les chiffres (ouverture, retour sur MAIN, après un import)."""
        now = self.clock()
        summary = dashboard_service.load_summary(self.userdata, now)
        self.top_bar.set_markers(dashboard_service.concerts_label(summary),
                                 dashboard_service.date_label(now))
        self.status_line.set_parts(dashboard_service.status_parts(summary))
        self.main_page.set_view(summary.view)

    # --- navigation MAIN <-> PARAMÈTRES -------------------------------------
    def show_settings(self) -> None:
        self.pages.setCurrentWidget(self.settings_page)
        self.settings_page.setFocus()
        self.top_bar.set_gear_active(True)
        self.rail.set_active(None)          # écran secondaire : aucune section active

    def show_main(self) -> None:
        self.pages.setCurrentWidget(self.main_page)
        self.main_page.setFocus()
        self.top_bar.set_gear_active(False)
        self.rail.set_active("main")
        self.refresh()

    # --- diagnostic (développement uniquement) ------------------------------
    def update_diagnostic(self) -> None:
        screen = self.screen()
        self.status_line.update_diagnostic(screen.devicePixelRatio() if screen else 1.0)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.DevicePixelRatioChange:
            self.update_diagnostic()
        super().changeEvent(event)
