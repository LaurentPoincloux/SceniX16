"""Navigation de la fiche (incrément 2.7c — D8, D9, D33, D38, D39, D46, D47, D63, D69, Design Book v0.47).

Ouverture au clic et par Entrée (une seule ouverture si Entrée est maintenue), trois chemins de
retour, banque du concert, paire sélectionnée et rendu « fiche ouverte », focus selon le mode
d'ouverture, aperçu fermé, MAIN active. Données temporaires uniquement.
"""

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from scenix16.storage.database import connect
from scenix16.storage.userdata import database_path
from scenix16.ui.theme import tokens as t
from test_dashboard_selection import colors, make_userdata, open_window, pulsing


@pytest.fixture
def folder(tmp_path):
    folder = make_userdata(tmp_path, range(0, 40, 2))            # 20 concerts : A complète, B01 à B04
    conn = connect(database_path(folder))
    with conn:
        conn.execute("INSERT INTO tracks(position, title, key, mk, virus, virus_status) "
                     "VALUES (1, 'THE PASSENGER', 'G#', '-/-', 'RAM-D 71', 'ON')")
        conn.executemany("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (?, 1, 1)",
                         [(i,) for i in range(1, 21)])
    conn.close()
    return folder


@pytest.fixture
def win(qtbot, qapp, folder):
    return open_window(qtbot, qapp, folder)


def calm(page):
    for n in range(1, 17):
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)


def click(qtbot, widget):
    rect = widget.body_rect() if hasattr(widget, "body_rect") else widget.card_rect()
    qtbot.mouseClick(widget, Qt.LeftButton, pos=rect.center().toPoint())
    calm(widget.window().main_page)


def press_enter(qtbot, widget):
    widget.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus)
    qtbot.keyClick(widget, Qt.Key_Return)


def on_sheet(win):
    return win.pages.currentWidget() is win.sheet_page


def concert_at(page, n):
    return page.slot(n).key.concert.id


# --- ouverture ------------------------------------------------------------------------------------------

def test_click_on_key_opens_sheet(win, qtbot):
    page = win.main_page
    chosen = concert_at(page, 3)
    click(qtbot, page.key(3))
    assert on_sheet(win) and win.sheet_page.sheet.id == chosen
    assert win.sheet_page.heading_label.text() == "Touche A03 · Consultation"
    assert win._sheet_origin == (chosen, False)                       # ouverte à la souris
    assert not page.preview_visible()


def test_click_on_card_opens_same_sheet(win, qtbot):
    page = win.main_page
    chosen = concert_at(page, 5)
    click(qtbot, page.slot(5))
    assert on_sheet(win) and win.sheet_page.sheet.id == chosen and win._sheet_origin == (chosen, False)


@pytest.mark.parametrize("kind", ["key", "slot"])
def test_enter_opens_sheet_in_keyboard_mode(win, qtbot, kind):
    page = win.main_page
    widget = page.key(4) if kind == "key" else page.slot(4)
    press_enter(qtbot, widget)
    assert on_sheet(win) and win._sheet_origin == (concert_at(page, 4), True)


def test_held_enter_opens_only_once(win, qtbot):
    page = win.main_page
    opened = []
    page.concert_requested.connect(opened.append)
    page.key(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.key(2).hasFocus)
    repeat = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r", True)   # répétition seule
    QApplication.sendEvent(page.key(2), repeat)
    QApplication.sendEvent(page.slot(2), QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r", True))
    assert opened == [] and not on_sheet(win)                         # répétitions ignorées
    qtbot.keyPress(page.key(2), Qt.Key_Return)                        # premier appui : ouverture
    for _ in range(5):                                                # Entrée maintenue
        target = QApplication.focusWidget() or win
        QApplication.sendEvent(target, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r", True))
    win.open_concert(concert_at(page, 2))                             # nouvelle demande : déjà ouverte
    assert opened == [concert_at(page, 2)] and on_sheet(win)


def test_preview_closed_when_opening(win, qtbot):
    page = win.main_page
    page.key(6).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    qtbot.keyClick(page.key(6), Qt.Key_Return)
    assert on_sheet(win) and not page.preview_visible()


def test_main_stays_active_during_sheet(win, qtbot):
    click(qtbot, win.main_page.key(1))
    assert on_sheet(win)
    assert win.rail.items["main"].active
    assert not any(win.rail.items[k].active for k in ("output", "tracks", "setlists"))


def test_unknown_concert_keeps_dashboard(win):
    win.open_concert(999)
    assert win.pages.currentWidget() is win.main_page and win._sheet_origin is None


# --- retour ----------------------------------------------------------------------------------------------

def back(win, qtbot, path):
    if path == "button":
        win.sheet_page.back_button.click()
    elif path == "escape":
        qtbot.keyClick(QApplication.focusWidget() or win.sheet_page, Qt.Key_Escape)
    else:
        qtbot.mouseClick(win.rail.items["main"], Qt.LeftButton)


@pytest.mark.parametrize("path", ["button", "escape", "rail"])
def test_three_ways_back_restore_pair(win, qtbot, path):
    page = win.main_page
    chosen = concert_at(page, 7)
    click(qtbot, page.key(7))
    back(win, qtbot, path)
    assert win.pages.currentWidget() is page and win._sheet_origin is None
    assert page.selected_concert == chosen and page.open_concert == chosen
    assert page.key(7).selected and page.slot(7).selected                # filet crème, bordure de groupe
    assert pulsing(page) == [7]
    assert win.rail.items["main"].active


def test_return_to_bank_of_concert_other_than_a(win, qtbot):
    page = win.main_page
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)            # banque B
    calm(page)
    chosen = concert_at(page, 2)
    click(qtbot, page.key(2))
    assert win.sheet_page.heading_label.text() == "Touche B02 · Consultation"
    win.sheet_page.back_button.click()
    assert page.bank == 1 and page.selected_concert == chosen          # D46
    assert page.key(2).selected and page.slot(2).selected


def test_return_when_concert_left_dashboard_applies_d47(win, qtbot, folder):
    page = win.main_page
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)
    chosen = concert_at(page, 1)
    click(qtbot, page.key(1))
    conn = connect(database_path(folder))
    with conn:                                                         # annulé pendant la consultation
        conn.execute("UPDATE setlists SET status = 'cancelled' WHERE id = ?", (chosen,))
    conn.close()
    win.sheet_page.back_button.click()
    assert win.pages.currentWidget() is page
    assert page.open_concert is None and page.selected_concert != chosen
    assert not any(page.key(n).selected for n in range(1, 17))


def test_open_rendering_disappears_when_another_pair_is_selected(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(3))
    win.sheet_page.back_button.click()
    assert page.key(3).selected
    page.key(5).setFocus(Qt.TabFocusReason)                            # navigation clavier : autre paire
    qtbot.waitUntil(page.key(5).hasFocus)
    assert page.selected_concert == concert_at(page, 5)
    assert page.open_concert is None and not page.key(3).selected and not page.slot(3).selected


def test_open_rendering_follows_its_concert_when_sorting(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(2))
    win.sheet_page.back_button.click()
    chosen = page.open_concert
    win.toggle_sort()
    flagged = [n for n in range(1, 17) if page.slot(n).selected]
    assert all(concert_at(page, n) == chosen for n in flagged)          # jamais sur un autre concert


# --- focus au retour --------------------------------------------------------------------------------------

def test_keyboard_opening_returns_focus_with_ring(win, qtbot):
    page = win.main_page
    press_enter(qtbot, page.key(6))
    qtbot.keyClick(QApplication.focusWidget() or win.sheet_page, Qt.Key_Escape)
    assert page.key(6).hasFocus()
    assert t.BRAND.lower() in colors(page.key(6))                       # anneau orange
    qtbot.wait(500)
    assert not page.preview_visible()                                   # pas d'aperçu automatique


def test_mouse_opening_returns_without_focus_ring(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(6))
    win.sheet_page.back_button.click()
    assert not any(page.key(n).hasFocus() or page.slot(n).hasFocus() for n in range(1, 17))
    assert t.BRAND.lower() not in colors(page.key(6))
    qtbot.wait(500)
    assert not page.preview_visible()


def test_keyboard_opening_from_card_returns_focus_to_key(win, qtbot):
    page = win.main_page
    press_enter(qtbot, page.slot(8))
    win.sheet_page.back_button.click()
    assert page.key(8).hasFocus()                                       # touche correspondante (D69)
