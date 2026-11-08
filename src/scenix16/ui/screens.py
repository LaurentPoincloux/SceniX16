"""Écran de lancement : choix unique pour l'écran de démarrage et la fenêtre CONCERTS (2.8d, B6).

Règle validée : l'écran sous le pointeur au lancement ; si le pointeur n'est sur aucun écran,
l'écran principal. L'écran de démarrage y est centré dans la zone disponible ; avec plusieurs
écrans, la fenêtre CONCERTS y est aussi centrée, réduite si nécessaire (jamais sous 1024 × 640,
calée en haut à gauche si l'écran est plus petit). Avec un seul écran, la fenêtre CONCERTS
garde le placement de Windows, comme avant (comportement inchangé).
Chaque fenêtre est créée directement sur l'écran choisi (setScreen avant l'affichage) : elle
prend son facteur de mise à l'échelle sans changer d'écran après coup.

Les calculs sont des fonctions pures, sur des rectangles (x, y, largeur, hauteur) logiques.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QCursor, QGuiApplication, QScreen

from scenix16.ui.theme import tokens as t

Rect = tuple[int, int, int, int]


def contains(rect: Rect, point: tuple[int, int]) -> bool:
    x, y, w, h = rect
    px, py = point
    return x <= px < x + w and y <= py < y + h


def choose_screen_index(screens: Sequence[Rect], primary: int, pointer: tuple[int, int] | None) -> int:
    """Indice de l'écran sous le pointeur, sinon de l'écran principal."""
    if pointer is not None:
        for index, rect in enumerate(screens):
            if contains(rect, pointer):
                return index
    return primary


def centered_geometry(available: Rect, size: tuple[int, int],
                      minimum: tuple[int, int] = (0, 0)) -> Rect:
    """Rectangle centré dans la zone disponible ; taille réduite à la zone, jamais sous `minimum` ;
    s'il ne tient pas, calé en haut à gauche de la zone."""
    ax, ay, aw, ah = available
    width = max(minimum[0], min(size[0], aw))
    height = max(minimum[1], min(size[1], ah))
    x = ax + (aw - width) // 2 if width <= aw else ax
    y = ay + (ah - height) // 2 if height <= ah else ay
    return x, y, width, height


def rect_of(qrect) -> Rect:
    return qrect.x(), qrect.y(), qrect.width(), qrect.height()


def launch_screen() -> QScreen | None:
    """Écran de lancement (B6) : sous le pointeur, sinon l'écran principal."""
    screens = QGuiApplication.screens()
    primary = QGuiApplication.primaryScreen()
    if not screens:
        return primary
    pos = QCursor.pos()
    index = choose_screen_index([rect_of(s.geometry()) for s in screens],
                                screens.index(primary) if primary in screens else 0,
                                (pos.x(), pos.y()))
    return screens[index]


def place_main_window(window, screen: QScreen | None) -> bool:
    """Avec plusieurs écrans : CONCERTS créée sur `screen`, centrée dans sa zone disponible.

    Avec un seul écran (ou sans écran connu), rien n'est changé : placement de Windows.
    Renvoie True si la fenêtre a été placée."""
    if screen is None or len(QGuiApplication.screens()) < 2:
        return False
    x, y, width, height = centered_geometry(
        rect_of(screen.availableGeometry()),
        (t.WINDOW_DEFAULT_WIDTH, t.WINDOW_DEFAULT_HEIGHT),
        (t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT))
    window.setScreen(screen)
    window.resize(width, height)
    window.move(x, y)
    return True
