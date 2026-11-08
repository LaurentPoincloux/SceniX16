"""Préférences système utiles à l'interface."""

from __future__ import annotations

import ctypes
import sys

SPI_GETCLIENTAREAANIMATION = 0x1042
SPI_SETCLIENTAREAANIMATION = 0x1043
WM_SETTINGCHANGE = 0x001A          # diffusé par Windows à chaque changement de réglage (2.8c)


def _read_client_area_animation() -> bool | None:
    """Réglage Windows « Afficher les animations » ; None si la lecture échoue."""
    value = ctypes.c_bool(True)
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0)
    return bool(value.value) if ok else None


def animations_enabled() -> bool:
    """Faux si Windows demande de réduire les animations (« Afficher les animations »).

    Commande la pulsation de la paire sélectionnée (D63), le fondu de l'aperçu (D64) et le
    glissement du tri (section 06). En cas d'échec de lecture, les animations sont conservées.
    """
    if sys.platform != "win32":
        return True
    try:
        value = _read_client_area_animation()
    except Exception:                          # API indisponible : on garde les animations
        return True
    return True if value is None else value
