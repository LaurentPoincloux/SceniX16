"""Barre de titre native sombre — option A de D61, repli de l'incrément 2.8e.

Le cadre, les boutons, le menu système et tous les comportements de Windows sont conservés :
seule la couleur de la barre native change, par l'attribut public DWMWA_USE_IMMERSIVE_DARK_MODE
(20) de DwmSetWindowAttribute. Aucun drapeau de fenêtre, aucune géométrie n'est modifié.

- Fenêtres concernées : fenêtre principale (QMainWindow) et boîtes de dialogue Qt (QDialog :
  À propos, Licences, boîtes de démarrage…), à chaque affichage. Exclus : écran de démarrage,
  fenêtres sans cadre, menus et info-bulles, boîtes natives de Windows (choix de dossier).
- Moment : à l'événement Show, avant la première peinture de la barre (posé après coup, l'attribut
  n'est pas redessiné). Après un changement de thème Windows, il est reposé puis la barre est
  redessinée par WM_NCACTIVATE (message documenté).
- Systèmes : Windows 11 (attribut documenté) et Windows 10 à partir du build 19041, où le même
  attribut fonctionne, y compris en mode clair. Avant 19041, rien n'est tenté (l'ancien attribut
  19, non documenté, n'est pas utilisé). Tout refus de Windows est silencieux.
- Désactivation : ENABLED = False (ou ne pas appeler install) rend le comportement natif initial.
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QDialog, QMainWindow, QSplashScreen

ENABLED = True                         # interrupteur unique de l'option A
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
MIN_WINDOWS_10_BUILD = 19041           # Windows 10 version 2004
WM_NCACTIVATE = 0x0086


def supported() -> bool:
    """Windows 10 (build 19041 et plus) ou Windows 11."""
    if sys.platform != "win32":
        return False
    try:
        version = sys.getwindowsversion()
    except Exception:
        return False
    return (version.major, version.build) >= (10, MIN_WINDOWS_10_BUILD)


def _dwm_set_dark(hwnd: int) -> int:
    """Appel DWM ; renvoie le HRESULT (0 = accepté)."""
    from ctypes import wintypes
    value = ctypes.c_int(1)
    return ctypes.windll.dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))


def _redraw_frame(hwnd: int, active: bool) -> None:
    """Redessine la barre d'une fenêtre déjà affichée (WM_NCACTIVATE, état d'activation conservé)."""
    from ctypes import wintypes
    send = ctypes.windll.user32.SendMessageW
    send(wintypes.HWND(hwnd), WM_NCACTIVATE, int(not active), 0)
    send(wintypes.HWND(hwnd), WM_NCACTIVATE, int(active), 0)


def concerned(widget) -> bool:
    """Fenêtre principale ou boîte de dialogue Qt avec cadre natif (jamais l'écran de démarrage)."""
    if not isinstance(widget, (QMainWindow, QDialog)) or isinstance(widget, QSplashScreen):
        return False
    if not widget.isWindow():
        return False
    flags = widget.windowFlags()
    return not flags & Qt.FramelessWindowHint and (flags & Qt.WindowType_Mask) in (Qt.Window, Qt.Dialog)


def apply_dark_title_bar(widget, refresh: bool = False) -> bool:
    """Pose l'attribut sombre ; True si Windows l'accepte. Jamais d'exception, jamais d'effet ailleurs."""
    if not ENABLED or not supported():
        return False
    try:
        hwnd = int(widget.winId())
        if not hwnd or _dwm_set_dark(hwnd) != 0:
            return False
        if refresh:
            _redraw_frame(hwnd, widget.isActiveWindow())
        return True
    except Exception:
        return False


class DarkTitleBarFilter(QObject):
    """Filtre d'application : applique l'option A à chaque affichage d'une fenêtre concernée."""

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.Show or kind == QEvent.Type.ThemeChange:
            if concerned(obj):
                if kind == QEvent.Type.Show:
                    apply_dark_title_bar(obj)
                elif obj.isVisible():
                    apply_dark_title_bar(obj, refresh=True)   # Windows a pu reposer la barre claire
        return False                      # n'intercepte jamais l'événement


def install(app) -> DarkTitleBarFilter | None:
    """Installe l'option A une seule fois sur l'application ; None si désactivée ou non prise en charge."""
    if not ENABLED or not supported():
        return None
    existing = getattr(app, "_dark_title_bar_filter", None)
    if existing is not None:
        return existing
    event_filter = DarkTitleBarFilter(app)
    app.installEventFilter(event_filter)
    app._dark_title_bar_filter = event_filter
    return event_filter
