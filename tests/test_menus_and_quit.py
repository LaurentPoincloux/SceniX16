"""Barre de menus (D59) et Quitter (D66) — Design Book v0.43.

Événements Qt simulés ; le comportement natif de Windows (Alt, F10, soulignés, Ctrl+Q sous
une boîte modale) a été vérifié par un prototype avec de vraies frappes avant 2.6c.
"""

from datetime import datetime

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog

from scenix16.ui.main_window import MainWindow
from scenix16.ui.shell.menu_bar import ABOUT_ITEM, FILE_MENU, HELP_MENU, QUIT_ITEM
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

NOW = datetime(2026, 11, 7, 12, 0)


@pytest.fixture
def window(qtbot, qapp):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow)
    win.main_page.setFocus(Qt.OtherFocusReason)
    return win


def focus_widget(win):
    return QApplication.focusWidget() or win


def close_popups():
    for _ in range(3):
        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.close()


# --- contenu ------------------------------------------------------------------------------

def test_menus_content(window):
    bar = window.menu_bar
    assert [a.text() for a in bar.actions()] == [FILE_MENU, HELP_MENU] == ["&Fichier", "&Aide"]
    assert [a.text() for a in bar.file_menu.actions()] == [QUIT_ITEM]
    assert bar.quit_action.shortcut().toString() == "Ctrl+Q"
    assert bar.quit_action.shortcutContext() == Qt.WindowShortcut
    assert [a.text() for a in bar.help_menu.actions()] == [ABOUT_ITEM]
    assert ABOUT_ITEM.replace("&", "") == "À propos de SceniX16"


def test_menu_bar_not_in_tab_chain(window):
    assert window.menu_bar.focusPolicy() == Qt.NoFocus


# --- clavier selon Windows ---------------------------------------------------------------------

def test_mnemonics_hidden_at_rest(window):
    assert not window.menu_bar.mnemonics_visible()


def test_alt_highlights_file_without_opening_and_shows_mnemonics(window, qtbot):
    bar = window.menu_bar
    rest = bar.grab().toImage()
    qtbot.keyPress(focus_widget(window), Qt.Key_Alt)
    assert bar.mnemonics_visible()
    assert bar.grab().toImage() != rest                         # lettres soulignées dessinées
    qtbot.keyRelease(focus_widget(window), Qt.Key_Alt)
    qtbot.wait(50)
    assert bar.activeAction() is not None and bar.activeAction().text() == FILE_MENU
    assert QApplication.activePopupWidget() is None
    assert bar.mnemonics_visible()
    qtbot.keyClick(focus_widget(window), Qt.Key_Escape)
    qtbot.wait(50)
    assert bar.activeAction() is None and not bar.mnemonics_visible()


def test_f10_follows_alt_path(window, qtbot):
    bar = window.menu_bar
    qtbot.keyClick(focus_widget(window), Qt.Key_F10)
    qtbot.wait(50)
    assert bar.activeAction() is not None and bar.activeAction().text() == FILE_MENU
    assert QApplication.activePopupWidget() is None             # en évidence, sans ouvrir
    assert bar.mnemonics_visible()
    qtbot.keyClick(focus_widget(window), Qt.Key_Escape)
    qtbot.wait(50)
    assert bar.activeAction() is None and not bar.mnemonics_visible()


@pytest.mark.parametrize("key, menu", [(Qt.Key_F, "file_menu"), (Qt.Key_A, "help_menu")])
def test_alt_letter_opens_menu(window, qtbot, key, menu):
    qtbot.keyClick(focus_widget(window), key, Qt.AltModifier)
    qtbot.waitUntil(lambda: getattr(window.menu_bar, menu).isVisible(), timeout=1000)
    assert window.menu_bar.mnemonics_visible()
    close_popups()


def test_mouse_opening_has_no_mnemonics(window, qtbot):
    bar = window.menu_bar
    rect = bar.actionGeometry(bar.actions()[0])
    qtbot.mouseClick(bar, Qt.LeftButton, pos=rect.center())
    qtbot.waitUntil(bar.file_menu.isVisible, timeout=1000)
    assert not bar.mnemonics_visible()
    close_popups()


# --- Quitter : un seul chemin (D66) -----------------------------------------------------------

def counting_close(window, accept=True):
    calls = []

    def confirm():
        calls.append(1)
        return accept

    window.confirm_close = confirm
    return calls


def test_ctrl_q_closes_through_close_event(window, qtbot):
    calls = counting_close(window)
    qtbot.keyClick(focus_widget(window), Qt.Key_Q, Qt.ControlModifier)
    assert calls == [1] and not window.isVisible()


@pytest.mark.parametrize("gesture", ["menu", "close", "ctrl_q"])
def test_every_gesture_uses_the_same_hook(window, qtbot, gesture):
    calls = counting_close(window, accept=False)              # « Continuer l'édition » (D38)
    if gesture == "menu":
        window.menu_bar.quit_action.trigger()
    elif gesture == "close":
        window.close()                                        # bouton Fermer, Alt+F4
    else:
        qtbot.keyClick(focus_widget(window), Qt.Key_Q, Qt.ControlModifier)
    assert calls == [1] and window.isVisible()                # fermeture annulée


def test_close_accepted_by_default(window):
    assert window.confirm_close() is True                     # aucun écran d'édition en 2.6c
    window.menu_bar.quit_action.trigger()
    assert not window.isVisible()


def test_ctrl_q_and_f10_inactive_under_modal_dialog(window, qtbot):
    calls = counting_close(window)
    seen = {}

    def inside():
        dialog = QApplication.activeModalWidget()
        qtbot.keyClick(QApplication.focusWidget() or dialog, Qt.Key_Q, Qt.ControlModifier)
        qtbot.keyClick(QApplication.focusWidget() or dialog, Qt.Key_F10)
        seen["dialog_open"] = dialog.isVisible()
        seen["bar_active"] = window.menu_bar.activeAction()
        dialog.reject()

    dialog = QDialog(window)
    dialog.setModal(True)
    QTimer.singleShot(150, inside)
    dialog.exec()
    assert seen == {"dialog_open": True, "bar_active": None}
    assert calls == [] and window.isVisible()


def test_about_opens_from_help_menu_and_ctrl_q_inactive(window, qtbot):
    calls = counting_close(window)
    seen = {}

    def inside():
        about = QApplication.activeModalWidget()
        seen["title"] = about.windowTitle()
        qtbot.keyClick(QApplication.focusWidget() or about, Qt.Key_Q, Qt.ControlModifier)
        seen["still_open"] = about.isVisible()
        qtbot.keyClick(QApplication.focusWidget() or about, Qt.Key_Escape)   # D39
        seen["closed_by_escape"] = not about.isVisible()

    QTimer.singleShot(200, inside)
    window.menu_bar.about_action.trigger()
    assert seen == {"title": "À propos de SceniX16", "still_open": True, "closed_by_escape": True}
    assert calls == [] and window.isVisible()


# --- 2.6d : couleurs des menus déroulants (texte lisible au repos, au survol, sélectionné) ----------

def _menu_colors(menu, qtbot, inset=0):
    """Couleurs du menu ; avec inset, seulement l'intérieur (les coins arrondis sont transparents)."""
    from PySide6.QtGui import QColor
    image = menu.grab().toImage()
    r = image.devicePixelRatio()
    m = round(inset * r)
    return {QColor(image.pixel(x, y)).name()
            for x in range(m, image.width() - m) for y in range(m, image.height() - m)}


@pytest.mark.parametrize("menu_name", ["file_menu", "help_menu"])
def test_menu_items_readable_in_every_state(window, qtbot, menu_name):
    from PySide6.QtGui import QColor
    from scenix16.ui.theme import tokens as t
    bar = window.menu_bar
    menu = getattr(bar, menu_name)
    menu.popup(bar.mapToGlobal(bar.rect().bottomLeft()))
    qtbot.waitUntil(menu.isVisible, timeout=1000)
    menu.setActiveAction(None)
    qtbot.wait(50)
    rest = _menu_colors(menu, qtbot)
    assert t.RAISED.lower() in rest and t.LINE_STRONG.lower() in rest     # panneau et bordure (D59)
    text_like = [QColor(c) for c in rest if QColor(c).lightness() > 200]
    assert text_like, "texte clair attendu au repos"
    inside = _menu_colors(menu, qtbot, inset=6)
    assert not any(QColor(c).lightness() < 20 for c in inside)           # aucun texte noir
    menu.setActiveAction(menu.actions()[0])                               # survolé / sélectionné
    qtbot.wait(50)
    selected = _menu_colors(menu, qtbot)
    assert t.CELL.lower() in selected                                     # surbrillance (D59)
    assert any(QColor(c).lightness() > 200 for c in selected)
    if menu_name == "file_menu":
        assert t.MUTED.lower() in rest                                    # raccourci gris
    close_popups()
