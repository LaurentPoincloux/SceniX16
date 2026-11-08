"""Incrément 2.8b : navigation clavier (D9, D46, D59, D65, D66, D69, Q11, Q15, section 09).

Flèches sur les cartes (← → en continu entre banques, ↑ ↓ vers la rangée voisine, ↑ depuis la
première rangée vers la touche), ↓ des touches vers les cartes, un seul arrêt de Tab par groupe
(touches, cartes) sur la paire sélectionnée, Maj+Tab symétrique, Entrée = Espace sur tous les
boutons avec une seule activation par appui, défilement de la fiche dès l'ouverture, répétition
conservée pour les touches de navigation. Données temporaires uniquement.
"""

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from scenix16.storage.database import connect
from scenix16.storage.userdata import database_path
from scenix16.ui.widgets.keyboard import enable_enter_activation, fresh_activation
from test_dashboard_selection import make_userdata, open_window

TRACKS = 40


@pytest.fixture
def folder(tmp_path):
    """20 concerts (A complète, B01 à B04) ; le concert 01 (A01) a 40 titres et une adresse."""
    folder = make_userdata(tmp_path, range(0, 40, 2))
    conn = connect(database_path(folder))
    with conn:
        conn.executemany("INSERT INTO tracks(position, title, key, mk, virus, virus_status) VALUES (?,?,?,?,?,?)",
                         [(i, f"TITRE {i:02d}", "G#", "-/-", "RAM-D 71", "ON") for i in range(1, TRACKS + 1)])
        conn.executemany("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (1, ?, ?)",
                         [(i, i) for i in range(1, TRACKS + 1)])
        conn.execute("UPDATE setlists SET address = 'Place du Marché' WHERE id = 1")
    conn.close()
    return folder


@pytest.fixture
def win(qtbot, qapp, folder):
    return open_window(qtbot, qapp, folder, animations=False)          # 1280 × 800 : 4 × 4


@pytest.fixture
def wide(qtbot, qapp, win):
    win.resize(1440, 900)                                               # 2 × 8
    qtbot.waitUntil(lambda: win.main_page.slot_grid.mode == "2x8")
    return win


def focus(qtbot, widget):
    widget.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus)


def press(qtbot, key, modifier=Qt.NoModifier):
    qtbot.keyClick(QApplication.focusWidget(), key, modifier)


def send(widget, key, auto_repeat=False, release=False, text=""):
    kind = QEvent.KeyRelease if release else QEvent.KeyPress
    QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.NoModifier, text, auto_repeat))


def hold(widget, key, repeats=3, text=""):
    """Appui maintenu, tel que Windows le transmet : un appui, puis des paires répétées."""
    send(widget, key, text=text)
    for _ in range(repeats):
        send(widget, key, auto_repeat=True, release=True, text=text)
        send(widget, key, auto_repeat=True, text=text)
    send(widget, key, release=True, text=text)


def concert_at(page, n):
    return page.slot(n).key.concert.id


def tab_policies(widgets):
    return [n for n, w in enumerate(widgets, 1) if w.focusPolicy() == Qt.TabFocus]


# --- cartes : ← → (D65, Q15) ------------------------------------------------------------------------

def test_card_arrows_follow_display_order_in_2x8(wide, qtbot):
    page = wide.main_page
    focus(qtbot, page.slot(7))
    press(qtbot, Qt.Key_Right)
    assert page.slot(8).hasFocus()
    press(qtbot, Qt.Key_Right)                                     # 2 × 8 : 08 → 09
    assert page.slot(9).hasFocus()
    press(qtbot, Qt.Key_Left)
    assert page.slot(8).hasFocus()


def test_card_arrows_cross_banks_both_ways(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(16))
    press(qtbot, Qt.Key_Right)                                     # A16 → B01, sur les cartes
    assert page.bank == 1 and page.slot(1).hasFocus()
    assert page.selected_concert == concert_at(page, 1)
    press(qtbot, Qt.Key_Left)                                      # B01 → A16
    assert page.bank == 0 and page.slot(16).hasFocus()
    assert page.selected_concert == concert_at(page, 16)


def test_card_arrows_never_wrap_nor_leave_the_grid(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(1))
    press(qtbot, Qt.Key_Left)                                      # A01 : première carte de A
    assert page.bank == 0 and page.slot(1).hasFocus()              # ni bouclage, ni bouton de tri
    page.select_bank(1)
    focus(qtbot, page.slot(4))
    press(qtbot, Qt.Key_Right)                                     # B04 : dernière carte active
    assert page.bank == 1 and page.slot(4).hasFocus()              # ni bouclage, ni paramètres


def test_card_arrows_skip_init_at_end_of_bank(win, qtbot):
    page = win.main_page
    page.select_bank(1)
    focus(qtbot, page.slot(4))
    press(qtbot, Qt.Key_Left)
    assert page.slot(3).hasFocus()
    assert page.slot(5).is_init and not page.slot(5).hasFocus()


# --- cartes : ↑ ↓ (D65, Q11) ------------------------------------------------------------------------

def test_vertical_arrows_in_2x8(wide, qtbot):
    page = wide.main_page
    focus(qtbot, page.slot(3))
    press(qtbot, Qt.Key_Down)                                      # 03 → 11
    assert page.slot(11).hasFocus()
    press(qtbot, Qt.Key_Down)                                      # dernière rangée : rien
    assert page.slot(11).hasFocus()
    press(qtbot, Qt.Key_Up)
    assert page.slot(3).hasFocus()
    press(qtbot, Qt.Key_Up)                                        # première rangée : touche 03
    assert page.key(3).hasFocus()


def test_vertical_arrows_in_4x4(win, qtbot):
    page = win.main_page
    assert page.slot_grid.mode == "4x4"
    focus(qtbot, page.slot(6))
    press(qtbot, Qt.Key_Up)                                        # 06 → 02
    assert page.slot(2).hasFocus()
    focus(qtbot, page.slot(6))
    press(qtbot, Qt.Key_Down)                                      # 06 → 10
    assert page.slot(10).hasFocus()
    focus(qtbot, page.slot(16))
    press(qtbot, Qt.Key_Down)                                      # dernière rangée : rien
    assert page.slot(16).hasFocus()
    focus(qtbot, page.slot(2))
    press(qtbot, Qt.Key_Up)                                        # première rangée : touche 02
    assert page.key(2).hasFocus()


@pytest.mark.parametrize("mode_fixture, start, target", [("wide", 3, 11), ("win", 2, 6)])
def test_init_target_keeps_focus_and_bank(request, qtbot, mode_fixture, start, target):
    win = request.getfixturevalue(mode_fixture)
    page = win.main_page
    page.select_bank(1)                                            # B01 à B04, puis INIT
    focus(qtbot, page.slot(start))
    press(qtbot, Qt.Key_Down)
    assert page.slot(target).is_init
    assert page.slot(start).hasFocus() and page.bank == 1          # aucun déplacement involontaire


def test_vertical_arrows_never_change_bank(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(16))
    press(qtbot, Qt.Key_Down)
    focus(qtbot, page.slot(1))
    press(qtbot, Qt.Key_Up)
    assert page.bank == 0 and page.key(1).hasFocus()


def test_layout_change_keeps_card_number_and_recomputes_moves(wide, qtbot):
    page = wide.main_page
    focus(qtbot, page.slot(6))
    wide.resize(1280, 800)                                         # 2 × 8 → 4 × 4
    qtbot.waitUntil(lambda: page.slot_grid.mode == "4x4")
    assert page.slot(6).hasFocus()
    press(qtbot, Qt.Key_Down)                                      # ± 4 désormais
    assert page.slot(10).hasFocus()
    wide.resize(1440, 900)
    qtbot.waitUntil(lambda: page.slot_grid.mode == "2x8")
    assert page.slot(10).hasFocus()
    press(qtbot, Qt.Key_Up)                                        # ± 8 de nouveau
    assert page.slot(2).hasFocus()


# --- touches : ↓ vers la carte ----------------------------------------------------------------------

def test_key_down_reaches_card_and_up_does_nothing(win, qtbot):
    page = win.main_page
    focus(qtbot, page.key(5))
    press(qtbot, Qt.Key_Up)
    assert page.key(5).hasFocus()
    press(qtbot, Qt.Key_Down)
    assert page.slot(5).hasFocus() and page.bank == 0


def test_card_request_on_init_pair_keeps_focus(win, qtbot):
    page = win.main_page
    page.select_bank(1)
    focus(qtbot, page.key(4))
    page.sequencer.card_requested.emit(5)                          # paire INIT : rien
    assert page.key(4).hasFocus()


# --- couplage, aperçu, Page précédente / suivante ----------------------------------------------------

def test_selection_and_preview_follow_card_focus_across_banks(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(16))
    qtbot.waitUntil(lambda: page.preview_visible() and page.preview.number == 16)
    press(qtbot, Qt.Key_Right)
    assert page.bank == 1 and page.selected_position() == 1
    qtbot.waitUntil(lambda: page.preview_visible() and page.preview.number == 1)
    assert page.key(1).highlighted                                  # couplage D63


def test_escape_dismissal_is_respected_by_card_arrows(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(2))
    qtbot.waitUntil(page.preview_visible)
    press(qtbot, Qt.Key_Escape)
    assert not page.preview_visible()
    press(qtbot, Qt.Key_Right)                                      # nouvelle paire : aperçu de nouveau
    qtbot.waitUntil(lambda: page.preview_visible() and page.preview.number == 3)


def test_page_keys_from_a_card_unchanged(win, qtbot):
    page = win.main_page
    focus(qtbot, page.slot(5))
    press(qtbot, Qt.Key_PageDown)                                   # D46 : première touche active
    assert page.bank == 1 and page.key(1).hasFocus()
    press(qtbot, Qt.Key_PageUp)
    assert page.bank == 0 and page.key(1).hasFocus()


# --- arrêts de Tab (décision 1) -----------------------------------------------------------------------

def test_single_tab_stop_per_group_on_selected_pair(win, qtbot):
    page = win.main_page
    assert page.selected_position() == 1                            # présélection : concert du jour
    keys = [page.key(n) for n in range(1, 17)]
    slots = [page.slot(n) for n in range(1, 17)]
    assert tab_policies(keys) == [1] and tab_policies(slots) == [1]
    page.select_concert(concert_at(page, 7))                        # sélection à la souris, par exemple
    assert tab_policies(keys) == [7] and tab_policies(slots) == [7]


def test_tab_and_shift_tab_cycle_symmetrically(win, qtbot):
    page = win.main_page
    page.select_concert(concert_at(page, 7))
    forward = [page.bank_tabs.tab(0), page.key(7), page.sort_button, page.slot(7),
               win.gear_button, win.rail.items["main"]]
    focus(qtbot, forward[0])
    seen = []
    for _ in forward:
        press(qtbot, Qt.Key_Tab)
        seen.append(QApplication.focusWidget())
    assert seen == forward[1:] + forward[:1]
    back = []
    for _ in forward:
        press(qtbot, Qt.Key_Tab, Qt.ShiftModifier)
        back.append(QApplication.focusWidget())
    assert back == list(reversed(forward))


def test_tab_stop_follows_arrow_navigation(win, qtbot):
    page = win.main_page
    focus(qtbot, page.key(1))
    for _ in range(4):
        press(qtbot, Qt.Key_Right)
    assert page.key(5).hasFocus()
    press(qtbot, Qt.Key_Tab)
    assert page.sort_button.hasFocus()
    press(qtbot, Qt.Key_Tab)
    assert page.slot(5).hasFocus()                                   # même paire
    press(qtbot, Qt.Key_Right)
    press(qtbot, Qt.Key_Tab, Qt.ShiftModifier)
    press(qtbot, Qt.Key_Tab, Qt.ShiftModifier)
    assert page.key(6).hasFocus()                                    # retour symétrique


def test_tab_stop_on_first_active_pair_when_selection_is_elsewhere(win, qtbot):
    page = win.main_page
    page.select_bank(1)                                              # sélection restée en A
    assert page.selected_position() is None
    assert page.tab_stop() == 1
    focus(qtbot, page.bank_tabs.tab(1))
    press(qtbot, Qt.Key_Tab)
    assert page.key(1).hasFocus() and page.bank == 1


def test_init_pairs_never_get_a_tab_stop(win, qtbot):
    page = win.main_page
    page.select_bank(1)
    for n in range(5, 17):
        assert page.key(n).focusPolicy() == Qt.NoFocus and page.slot(n).focusPolicy() == Qt.NoFocus


# --- répétition des touches et activation (décision 2) ----------------------------------------------

def counter(signal):
    calls = []
    signal.connect(lambda *a: calls.append(a))
    return calls


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Enter, "\r"), (Qt.Key_Space, " ")])
def test_held_activation_key_opens_sheet_once(win, qtbot, key, text):
    page = win.main_page
    requests = counter(page.concert_requested)
    focus(qtbot, page.key(2))
    hold(page.key(2), key, text=text)
    assert len(requests) == 1


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Space, " ")])
def test_held_activation_key_on_card_and_sort_once(win, qtbot, key, text):
    page = win.main_page
    win.open_concert = lambda _id: None                              # rester sur le dashboard
    requests = counter(page.concert_requested)
    focus(qtbot, page.slot(3))
    hold(page.slot(3), key, text=text)
    assert len(requests) == 1
    toggles = counter(page.sort_toggled)
    focus(qtbot, page.sort_button)
    hold(page.sort_button, key, text=text)
    assert len(toggles) == 1


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Space, " ")])
def test_enter_and_space_open_settings_from_gear_once(win, qtbot, key, text):
    clicks = counter(win.gear_button.clicked)
    focus(qtbot, win.gear_button)
    hold(win.gear_button, key, text=text)
    assert len(clicks) == 1 and win.pages.currentWidget() is win.settings_page


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Space, " ")])
def test_enter_and_space_on_settings_back_button(win, qtbot, key, text):
    win.show_settings()
    back = win.settings_page.back_button
    returns = counter(win.settings_page.back_requested)
    focus(qtbot, back)
    hold(back, key, text=text)
    assert len(returns) == 1 and win.pages.currentWidget() is win.main_page


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Space, " ")])
def test_enter_and_space_on_rail_concerts(win, qtbot, key, text):
    item = win.rail.items["main"]
    requests = counter(win.rail.main_requested)
    focus(qtbot, item)
    hold(item, key, text=text)
    assert len(requests) == 1


def open_sheet_by_keyboard(win, qtbot, n=1, key=Qt.Key_Return):
    page = win.main_page
    focus(qtbot, page.key(n))
    qtbot.keyClick(page.key(n), key)
    qtbot.waitUntil(lambda: win.pages.currentWidget() is win.sheet_page)
    return win.sheet_page


@pytest.mark.parametrize("key, text", [(Qt.Key_Return, "\r"), (Qt.Key_Space, " ")])
def test_enter_and_space_on_sheet_buttons(win, qtbot, key, text):
    sheet = open_sheet_by_keyboard(win, qtbot)
    focus(qtbot, sheet.info_toggle)
    hold(sheet.info_toggle, key, text=text)
    assert sheet.info_expanded()                                     # une seule bascule
    copies = counter(sheet.copy_button.clicked)
    focus(qtbot, sheet.copy_button)
    hold(sheet.copy_button, key, text=text)
    assert len(copies) == 1
    returns = counter(sheet.back_requested)
    focus(qtbot, sheet.back_button)
    hold(sheet.back_button, key, text=text)
    assert len(returns) == 1 and win.pages.currentWidget() is win.main_page


def test_space_opening_returns_focus_like_enter(win, qtbot):
    """Espace a le même effet qu'Entrée, y compris le focus rendu à la touche au retour (D69)."""
    open_sheet_by_keyboard(win, qtbot, n=2, key=Qt.Key_Space)
    qtbot.keyClick(win.sheet_page, Qt.Key_Escape)
    assert win.pages.currentWidget() is win.main_page
    assert win.main_page.key(2).hasFocus()


def test_enter_while_space_is_down_does_not_double_trigger(win, qtbot):
    clicks = counter(win.gear_button.clicked)
    focus(qtbot, win.gear_button)
    send(win.gear_button, Qt.Key_Space, text=" ")                   # bouton enfoncé
    send(win.gear_button, Qt.Key_Return, text="\r")                 # ignorée : appui en cours
    send(win.gear_button, Qt.Key_Space, release=True, text=" ")
    assert len(clicks) == 1


def test_fresh_activation_rules(win):
    button = win.gear_button
    assert fresh_activation(button, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert not fresh_activation(button, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "", True))
    button.setEnabled(False)
    assert not fresh_activation(button, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    button.setEnabled(True)
    enable_enter_activation(button)                                  # pose idempotente
    assert len([c for c in button.children() if type(c).__name__ == "EnterActivation"]) == 1


def test_escape_shortcuts_do_not_repeat(win):
    assert not win.sheet_page._escape.autoRepeat()
    assert not win.settings_page._escape.autoRepeat()


def test_held_escape_on_dashboard_has_single_effect(win, qtbot):
    page = win.main_page
    focus(qtbot, page.key(2))
    qtbot.waitUntil(page.preview_visible)
    send(page.key(2), Qt.Key_Escape)
    assert not page.preview_visible() and page._preview_suppressed == 2
    page._preview_suppressed = None
    send(page.key(2), Qt.Key_Escape, auto_repeat=True)              # répétition : aucun effet
    assert page._preview_suppressed is None


def test_navigation_keys_keep_their_repetition(win, qtbot):
    page = win.main_page
    focus(qtbot, page.key(1))
    for _ in range(3):
        send(QApplication.focusWidget(), Qt.Key_Right, auto_repeat=True)
    assert page.key(4).hasFocus()
    focus(qtbot, page.slot(1))
    for _ in range(3):
        send(QApplication.focusWidget(), Qt.Key_Right, auto_repeat=True)
    assert page.slot(4).hasFocus()


# --- clic sans focus (section 09, v0.45) -------------------------------------------------------------

def test_buttons_take_focus_only_from_keyboard(win):
    for button in (win.settings_page.back_button, win.settings_page.import_button,
                   win.sheet_page.back_button, win.gear_button, win.rail.items["main"]):
        assert button.focusPolicy() == Qt.TabFocus


def test_pressing_back_button_then_leaving_gives_no_focus(win, qtbot):
    win.show_settings()
    back = win.settings_page.back_button
    qtbot.mousePress(back, Qt.LeftButton)
    qtbot.mouseRelease(back, Qt.LeftButton, pos=QPoint(-40, -40))   # relâché hors du bouton
    assert not back.hasFocus() and win.pages.currentWidget() is win.settings_page


# --- fiche : défilement et ordre de tabulation -------------------------------------------------------

def test_sheet_scrolls_from_opening_without_tab(win, qtbot):
    sheet = open_sheet_by_keyboard(win, qtbot)
    bar = sheet.scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    press(qtbot, Qt.Key_Down)
    assert bar.value() == bar.singleStep()
    press(qtbot, Qt.Key_PageDown)
    assert bar.value() == min(bar.maximum(), bar.singleStep() + bar.pageStep())
    press(qtbot, Qt.Key_End)
    assert bar.value() == bar.maximum()
    press(qtbot, Qt.Key_PageUp)
    assert bar.value() == bar.maximum() - bar.pageStep()
    press(qtbot, Qt.Key_Home)
    assert bar.value() == 0
    for _ in range(3):                                               # répétition conservée
        send(QApplication.focusWidget(), Qt.Key_Down, auto_repeat=True)
    assert bar.value() == 3 * bar.singleStep()


def test_sheet_scrolls_while_a_button_has_focus(win, qtbot):
    sheet = open_sheet_by_keyboard(win, qtbot)
    bar = sheet.scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    focus(qtbot, sheet.back_button)
    press(qtbot, Qt.Key_End)
    assert bar.value() == bar.maximum() and sheet.back_button.hasFocus()


def test_sheet_tab_order_without_scroll_area(win, qtbot):
    sheet = open_sheet_by_keyboard(win, qtbot)
    assert sheet.scroll.focusPolicy() == Qt.NoFocus
    forward = [sheet.back_button, sheet.info_toggle, win.gear_button, win.rail.items["main"]]
    press(qtbot, Qt.Key_Tab)                                         # depuis la page elle-même
    assert QApplication.focusWidget() is forward[0]
    seen = []
    for _ in forward:
        press(qtbot, Qt.Key_Tab)
        seen.append(QApplication.focusWidget())
    assert seen == forward[1:] + forward[:1]
    back = []
    for _ in forward:
        press(qtbot, Qt.Key_Tab, Qt.ShiftModifier)
        back.append(QApplication.focusWidget())
    assert back == list(reversed(forward))


def test_settings_tab_order(win, qtbot):
    win.show_settings()
    settings = win.settings_page
    press(qtbot, Qt.Key_Tab)
    assert QApplication.focusWidget() is settings.back_button
    stops = [settings.back_button]
    for _ in range(4):
        press(qtbot, Qt.Key_Tab)
        stops.append(QApplication.focusWidget())
    expected = [settings.back_button]
    if settings.import_button.isVisible() and settings.import_button.isEnabled():
        expected.append(settings.import_button)
    expected += [win.gear_button, win.rail.items["main"]]
    assert stops[:len(expected) + 1] == expected + [settings.back_button]
