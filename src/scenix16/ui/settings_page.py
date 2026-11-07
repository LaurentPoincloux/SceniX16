"""Écran PARAMÈTRES (squelette) avec la section DONNÉES.

Design Book v0.40 : écran secondaire ouvert par l'icône d'engrenage de la
barre supérieure ; retour par « ← MAIN » ou Échap (D38, D39). Les autres
paramètres (logos, sauvegarde manuelle) arrivent en phase 6.

Section DONNÉES (choix validés) : entrée discrète « Importer le classeur
Excel… », active seulement si la base est vide ; état relu à chaque
ouverture de l'écran et après chaque import.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scenix16.importer.service import ImportFailed, ImportRefused, import_into_userdata
from scenix16.storage import database
from scenix16.storage.userdata import application_dir, database_path

IMPORT_LABEL = "Importer le classeur Excel…"
IMPORT_HINT = "Opération ponctuelle, destinée à initialiser une base vide."
IMPORT_DISABLED_HINT = "Disponible uniquement quand la base ne contient encore aucune donnée."


def default_choose_file(parent: QWidget) -> Path | None:
    filename, _ = QFileDialog.getOpenFileName(
        parent, "Choisir le classeur Excel", str(application_dir()),
        "Classeur Excel (*.xlsx)")
    return Path(filename) if filename else None


def default_show_message(title: str, text: str) -> None:
    from scenix16.ui.startup_dialogs import MessageDialog

    MessageDialog(title, text, [("OK", "secondary", None)], focus=0).exec()


class SettingsPage(QWidget):
    back_requested = Signal()

    def __init__(self, userdata: Path | None,
                 choose_file: Callable[[QWidget], Path | None] = default_choose_file,
                 show_message: Callable[[str, str], None] = default_show_message,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.userdata = userdata
        self._choose_file = choose_file
        self._show_message = show_message

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(16)
        self.back_button = QPushButton("← MAIN")
        self.back_button.setProperty("variant", "back")
        self.back_button.clicked.connect(self.back_requested)
        title = QLabel("PARAMÈTRES", objectName="PageTitle")
        head.addWidget(self.back_button)
        head.addWidget(title)
        head.addStretch(1)
        layout.addLayout(head)

        layout.addStretch(1)  # la section DONNÉES reste en bas de l'écran

        section = QWidget(objectName="SettingsSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 14, 0, 0)
        section_layout.setSpacing(6)
        section_layout.addWidget(QLabel("DONNÉES", objectName="SectionLabel"))
        self.import_button = QPushButton(IMPORT_LABEL)
        self.import_button.setProperty("variant", "ghost")
        self.import_button.clicked.connect(self.run_import)
        self.import_hint = QLabel(IMPORT_HINT, objectName="HintLabel")
        self.import_hint.setWordWrap(True)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.import_button)
        row.addStretch(1)
        section_layout.addLayout(row)
        section_layout.addWidget(self.import_hint)
        layout.addWidget(section)

        # Échap reproduit le bouton retour (D39)
        self._escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._escape.setContext(Qt.WidgetWithChildrenShortcut)
        self._escape.activated.connect(self.back_requested)

    # --- état de l'entrée d'import -----------------------------------------
    def database_is_empty(self) -> bool:
        if self.userdata is None:
            return False
        try:
            connection = database.connect(database_path(self.userdata))
        except Exception:
            return False
        try:
            return database.is_empty(connection)
        finally:
            connection.close()

    def refresh(self) -> None:
        """Relit l'état réel de la base (à chaque ouverture et après un import)."""
        enabled = self.database_is_empty()
        self.import_button.setEnabled(enabled)
        self.import_hint.setText(IMPORT_HINT if enabled else IMPORT_DISABLED_HINT)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    # --- import ------------------------------------------------------------
    def run_import(self) -> None:
        if self.userdata is None:
            return
        xlsx = self._choose_file(self)
        if xlsx is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = import_into_userdata(xlsx, self.userdata)
        except ImportRefused as exc:
            QApplication.restoreOverrideCursor()
            self._show_message("Import refusé", f"{exc}\n\nAucune donnée n'a été modifiée.")
        except ImportFailed as exc:
            QApplication.restoreOverrideCursor()
            self._show_message("L'import a échoué", str(exc))
        except Exception as exc:  # garde-fou : jamais d'erreur technique brute
            QApplication.restoreOverrideCursor()
            self._show_message(
                "L'import a échoué",
                f"Erreur inattendue ({type(exc).__name__}). "
                "Aucune donnée partielle n'est conservée : l'écriture se fait en une seule fois.")
        else:
            QApplication.restoreOverrideCursor()
            report = (f"Rapport d'import :\n{result.report_path}" if result.report_path
                      else result.report_error or "")
            self._show_message(
                "Import terminé",
                f"{result.tracks} morceaux, {result.setlists} setlists et "
                f"{result.entries} entrées de setlist importés.\n"
                f"{len(result.data.findings)} particularités à vérifier.\n\n{report}")
        finally:
            self.refresh()
