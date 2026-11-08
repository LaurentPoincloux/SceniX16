"""Bouton dont l'accent orange est réservé au focus clavier (incrément 2.6d).

Utilisé pour le bouton « Fermer » des fenêtres « À propos » et « Licences et
composants tiers » uniquement. Bordure neutre au repos ; la bordure orange de
2 px n'apparaît que si le bouton reçoit le focus par la navigation au clavier
(Tab, Maj+Tab, raccourci). Le focus donné automatiquement à l'ouverture de la
fenêtre ou par un clic ne l'affiche pas. Entrée et Échap gardent leur effet.
La propriété « kbfocus » est lue par la feuille de style.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

KEYBOARD_REASONS = (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)


class KeyboardFocusButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DialogCloseButton")
        self._set_keyboard_focus(False)

    def keyboard_focus(self) -> bool:
        return bool(self.property("kbfocus"))

    def _set_keyboard_focus(self, on: bool) -> None:
        if self.property("kbfocus") != on:
            self.setProperty("kbfocus", on)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def focusInEvent(self, event):
        reason = event.reason()
        if reason in KEYBOARD_REASONS:
            self._set_keyboard_focus(True)
        elif reason != Qt.ActiveWindowFocusReason:      # retour à la fenêtre : état conservé
            self._set_keyboard_focus(False)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if event.reason() != Qt.ActiveWindowFocusReason:
            self._set_keyboard_focus(False)
        super().focusOutEvent(event)
