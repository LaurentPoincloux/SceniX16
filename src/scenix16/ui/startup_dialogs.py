"""Fenêtres de dialogue du démarrage (implémentation Qt de StartupUI)."""

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


class QtStartupUI:
    def __init__(self):
        self._busy = False

    def storage_problem(self, check: WriteCheck, can_relocate: bool) -> Choice:
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
        text = str(error)
        if error.partial is not None:
            text += (f"\n\nUne copie partielle se trouve dans :\n{error.partial}\n"
                     "Elle n'a pas été supprimée. Le dossier d'origine n'a pas été modifié.")
        else:
            text += "\n\nRien n'a été copié. Le dossier d'origine n'a pas été modifié."
        MessageDialog("La copie n'a pas pu être faite", text,
                      [("OK", "secondary", None)], focus=0).exec()

    def offer_restart(self, result: RelocationResult) -> bool:
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
        MessageDialog(
            "SceniX16 est déjà ouvert",
            "Une autre fenêtre SceniX16 utilise déjà ce dossier de données :\n"
            f"{userdata}\n\nCette deuxième ouverture est arrêtée pour protéger vos données.",
            [("OK", "secondary", None)], focus=0,
        ).exec()
