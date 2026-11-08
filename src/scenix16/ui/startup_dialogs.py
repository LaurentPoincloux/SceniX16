"""Fenêtres de dialogue du démarrage (implémentation Qt de StartupUI).

Écran de démarrage (2.8d, B4) : il est fermé définitivement avant toute boîte de démarrage
(dossier non accessible, choix du dossier, échec de copie, redémarrage, instance déjà ouverte,
échec du démarrage), pour ne jamais la recouvrir.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scenix16.services.relocation import RelocationError, RelocationResult
from scenix16.startup import Choice
from scenix16.storage.userdata import WriteCheck


class MessageDialog(QDialog):
    """Boîte sobre du Design Book : titre, texte, boutons alignés à droite."""

    def __init__(self, title: str, text: str, buttons: list[tuple[str, str, object]],
                 focus: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MessageDialog")
        self.setWindowTitle("SceniX16")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.result_value = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        heading = QLabel(title, objectName="DialogTitle")
        heading.setWordWrap(True)
        body = QLabel(text, objectName="DialogText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(heading)
        layout.addWidget(body)
        row = QHBoxLayout()
        row.addStretch(1)
        self.buttons: list[QPushButton] = []
        self._values: list[object] = []
        for label, variant, value in buttons:
            button = QPushButton(label)
            button.setProperty("variant", variant)
            # méthode liée (et non lambda) : évite un cycle de références qui
            # retarderait la destruction de la boîte après la fermeture de Qt
            button.clicked.connect(self._on_clicked)
            row.addWidget(button)
            self.buttons.append(button)
            self._values.append(value)
        layout.addLayout(row)
        self.buttons[focus].setDefault(True)
        self.buttons[focus].setFocus()

    def _on_clicked(self):
        self.result_value = self._values[self.buttons.index(self.sender())]
        self.accept()


STARTUP_FAILED_TITLE = "SceniX16 n'a pas pu démarrer"


def startup_failed_text(step_name: str, report: Path | None) -> str:
    text = f"Le démarrage s'est arrêté à l'étape « {step_name} ».\n\n"
    if report is not None:
        text += f"Un rapport technique a été enregistré dans :\n{report}\n\n"
    else:
        text += "Aucun rapport technique n'a pu être enregistré.\n\n"
    return text + "Vous pouvez relancer SceniX16. Si le problème persiste, conservez ce rapport."


class QtStartupUI:
    def __init__(self, splash=None):
        self._busy = False
        self.splash = splash

    def _close_splash(self) -> None:
        """B4 : l'écran de démarrage disparaît définitivement avant toute boîte."""
        if self.splash is not None:
            self.splash.dismiss()

    def storage_problem(self, check: WriteCheck, can_relocate: bool) -> Choice:
        self._close_splash()
        text = (
            f"Windows interdit l'écriture dans ce dossier :\n{check.path}\n\n"
            "SceniX16 ne peut donc enregistrer ni données, ni paramètres, ni sauvegardes.\n\n"
            "« Choisir un emplacement… » copie le dossier SceniX16 complet (programme et "
            "données) vers un dossier de votre choix, sans modifier le dossier actuel."
        )
        if not can_relocate:
            text += ("\n\nCette copie n'est disponible que depuis la version portable "
                     "(SceniX16.exe).")
        dialog = MessageDialog(
            "SceniX16 ne peut pas enregistrer ses données",
            text,
            [("Quitter", "secondary", Choice.QUIT),
             ("Choisir un emplacement…", "primary", Choice.CHOOSE_LOCATION)],
            focus=1 if can_relocate else 0,
        )
        dialog.buttons[1].setEnabled(can_relocate)
        dialog.exec()
        return dialog.result_value or Choice.QUIT

    def choose_parent_folder(self) -> Path | None:
        self._close_splash()
        folder = QFileDialog.getExistingDirectory(
            None, "Choisir le dossier où copier SceniX16")
        return Path(folder) if folder else None

    def copying(self, running: bool) -> None:
        if running and not self._busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        elif not running and self._busy:
            QApplication.restoreOverrideCursor()
        self._busy = running

    def relocation_failed(self, error: RelocationError) -> None:
        self._close_splash()
        text = str(error)
        if error.partial is not None:
            text += (f"\n\nUne copie partielle se trouve dans :\n{error.partial}\n"
                     "Elle n'a pas été supprimée. Le dossier d'origine n'a pas été modifié.")
        else:
            text += "\n\nRien n'a été copié. Le dossier d'origine n'a pas été modifié."
        MessageDialog("La copie n'a pas pu être faite", text,
                      [("OK", "secondary", None)], focus=0).exec()

    def offer_restart(self, result: RelocationResult) -> bool:
        self._close_splash()
        dialog = MessageDialog(
            "Copie terminée et vérifiée",
            f"SceniX16 a été copié dans :\n{result.destination}\n\n"
            f"{result.files} fichiers vérifiés. Le dossier d'origine n'a pas été modifié.\n\n"
            "Redémarrer SceniX16 depuis ce nouvel emplacement ?",
            [("Plus tard", "secondary", False), ("Redémarrer", "primary", True)],
            focus=1,
        )
        dialog.exec()
        return bool(dialog.result_value)

    def already_running(self, userdata: Path) -> None:
        self._close_splash()
        MessageDialog(
            "SceniX16 est déjà ouvert",
            "Une autre fenêtre SceniX16 utilise déjà ce dossier de données :\n"
            f"{userdata}\n\nCette deuxième ouverture est arrêtée pour protéger vos données.",
            [("OK", "secondary", None)], focus=0,
        ).exec()

    def startup_failed(self, step_name: str, report: Path | None) -> None:
        """Échec inattendu (B5) : message compréhensible ; le code de sortie est rendu par l'appelant."""
        self._close_splash()
        if self._busy:
            self.copying(False)
        MessageDialog(STARTUP_FAILED_TITLE, startup_failed_text(step_name, report),
                      [("OK", "secondary", None)], focus=0).exec()
