"""Réglage Windows « réduire les animations » suivi en direct (D74, section 09 — incrément 2.8c).

Pas d'interrogation périodique : le réglage est relu quand Windows diffuse WM_SETTINGCHANGE
et quand l'application redevient active (filet de sécurité, par exemple si le message a été
manqué ; appelé par la fenêtre principale). Le message est reçu par un filtre natif posé sur
l'application : il voit les messages de toutes les fenêtres de SceniX16, ne consomme jamais
rien, et est retiré à la destruction de la surveillance. `changed` n'est émis que si la valeur
a réellement changé. La lecture passe par ui.system.animations_enabled, qui conserve les
animations en cas d'échec ; elle est injectable pour les tests.
"""

from __future__ import annotations

from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal
from shiboken6 import isValid

from scenix16.ui import system


def is_setting_change(event_type, message) -> bool:
    """Vrai si le message natif est WM_SETTINGCHANGE (Windows)."""
    try:
        address = int(message)                 # VoidPtr de Qt : sa valeur de vérité n'est pas fiable
        if bytes(event_type) != b"windows_generic_MSG" or not address:
            return False
        msg = wintypes.MSG.from_address(address)
    except Exception:
        return False
    return msg.message == system.WM_SETTINGCHANGE


class SettingChangeFilter(QAbstractNativeEventFilter):
    """Filtre natif de l'application : WM_SETTINGCHANGE déclenche une relecture du réglage."""

    def __init__(self, watcher: "AnimationWatcher"):
        super().__init__()
        self.watcher = watcher

    def nativeEventFilter(self, event_type, message):
        if is_setting_change(event_type, message) and isValid(self.watcher):
            self.watcher.refresh()
        return False, 0                  # jamais consommé : Qt et Windows le traitent normalement


def _remove_filter(app: QCoreApplication, native_filter: SettingChangeFilter) -> None:
    if isValid(app):
        app.removeNativeEventFilter(native_filter)


class AnimationWatcher(QObject):
    changed = Signal(bool)              # True : animations autorisées ; False : réduites

    def __init__(self, read: Callable[[], bool] | None = None, parent: QObject | None = None,
                 listen: bool = True):
        super().__init__(parent)
        self._read = read
        self.enabled = self.read()
        self.native_filter: SettingChangeFilter | None = None
        app = QCoreApplication.instance()
        if listen and app is not None:
            native_filter = SettingChangeFilter(self)
            app.installNativeEventFilter(native_filter)
            self.native_filter = native_filter
            self.destroyed.connect(lambda *_: _remove_filter(app, native_filter))

    def read(self) -> bool:
        reader = self._read or system.animations_enabled
        try:
            return bool(reader())
        except Exception:                # lecture impossible : on garde les animations
            return True

    def refresh(self) -> bool:
        """Relit le réglage ; True (et `changed` émis) s'il a changé."""
        enabled = self.read()
        if enabled == self.enabled:
            return False
        self.enabled = enabled
        self.changed.emit(enabled)
        return True
