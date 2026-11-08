"""Règles clavier communes aux boutons (incrément 2.8b, D9, D46, D69, section 09).

- Entrée et Espace ont le même effet sur tous les boutons de l'application.
- Une activation par appui : une touche d'activation maintenue (répétition automatique du
  clavier) ne déclenche jamais une seconde action, et Entrée pendant qu'Espace tient déjà le
  bouton enfoncé n'ajoute pas un second déclenchement au relâchement d'Espace.
- Les touches de navigation (flèches, Page précédente / suivante, Tab) gardent leur
  répétition normale : elles ne passent pas par ce module.

Espace suit le comportement standard de Qt (bouton enfoncé à l'appui, activé au relâchement,
répétitions ignorées). Entrée n'est pas gérée par Qt hors d'une boîte de dialogue : elle l'est
ici, à l'appui, sans répétition.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton

ENTER_KEYS = (Qt.Key_Return, Qt.Key_Enter)
ACTIVATION_KEYS = (*ENTER_KEYS, Qt.Key_Space, Qt.Key_Select)


def is_enter(event) -> bool:
    return event.key() in ENTER_KEYS


def fresh_activation(button: QAbstractButton, event) -> bool:
    """True si cet appui doit activer le bouton : ni répétition, ni bouton déjà enfoncé
    (Espace en cours), et bouton actif."""
    return not event.isAutoRepeat() and button.isEnabled() and not button.isDown()


class EnterActivation(QObject):
    """Filtre posé sur un bouton : Entrée l'active une fois par appui, comme Espace."""

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.KeyPress and isinstance(watched, QAbstractButton)
                and is_enter(event)):
            if fresh_activation(watched, event):
                watched.click()
            event.accept()
            return True
        return super().eventFilter(watched, event)


def enable_enter_activation(*buttons: QAbstractButton) -> None:
    """Entrée active chaque bouton donné (une fois par appui)."""
    for button in buttons:
        if getattr(button, "_enter_activation", None) is None:
            button._enter_activation = EnterActivation(button)
            button.installEventFilter(button._enter_activation)
