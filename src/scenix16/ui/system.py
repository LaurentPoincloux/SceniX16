"""Préférences système utiles à l'interface."""

from __future__ import annotations

import ctypes
import sys

SPI_GETCLIENTAREAANIMATION = 0x1042


def animations_enabled() -> bool:
    """Faux si Windows demande de réduire les animations (« Afficher les animations »).

    Utilisé pour la pulsation du voyant « Aujourd'hui » (D11), qui devient fixe.
    """
    if sys.platform != "win32":
        return True
    value = ctypes.c_bool(True)
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0)
    return bool(value.value) if ok else True
