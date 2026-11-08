"""Incrément 2.6 : banques dans le dashboard, clavier et focus (D44 à D48, arbitrages 1 à 8).

Toutes les données sont dans une base temporaire ; la base réelle n'est jamais ouverte.
"""

import sqlite3
from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import Qt

from scenix16.domain.dashboard import ConcertState, build_dashboard
from scenix16.domain.models import ConcertSummary, SetlistStatus
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

NOW = datetime(2026, 11, 7, 20, 0)
UPCOMING = 20                                     # A : 16 concerts, B : 4 concerts


def rows(n=UPCOMING):
    data = [(f"Concert {i:02d}", (date(2026, 11, 7) + timedelta(days=7 * (i - 1))).isoformat(),
             f"Salle {i:02d}", "maintained") for i in range(1, n + 1)]
    data += [("Antipode", "2025-11-14", None, "maintained"), ("Nouvelle setlist", None, None, "maintained")]
    return data


@pytest.fixture
def ud(tmp_path):
    folder = tmp_path / "UserData"
    check_writable(folder)
    conn = connect(database_path(folder))
    with conn:
        conn.executemany("INSERT INTO setlists(name, concert_date, venue, status) VALUES (?,?,?,?)", rows())
    conn.close()
    return folder


def delete_concerts(ud, names):
    conn = sqlite3.connect(database_path(ud))
    with conn:
        conn.executemany("DELETE FROM setlists WHERE name = ?", [(n,) for n in names])
    conn.close()


def open_window(qtbot, qapp, userdata, size=(1280, 800), clock=None, animations=False):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(userdata, clock=clock or (lambda: NOW))
    win.main_page.animations = animations
    qtbot.addWidget(win)
    win.resize(*size)
    win.show()
    qtbot.waitExposed(win)
    return win


def names(page):
    return [s.name_text() for s in page.slot_grid.slots if not s.is_init]


def focus(qtbot, win, widget):
    win.activateWindow()
    widget.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus)


# --- affichage d'une banque (D44, D45) -----------------------------------------------------

def test_launch_on_bank_a_with_tabs(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page, tabs = win.main_page, win.main_page.bank_tabs
    assert page.bank == 0 and names(page)[0] == "Concert 01" and len(names(page)) == 16
    assert [t.text() for t in tabs.visible_tabs()] == list("ABCDEFGH")
    assert tabs.tab(0).selected and tabs.tab(1).isEnabled()
    assert not any(t.isEnabled() for t in tabs.visible_tabs()[2:])
    assert tabs.tab(1).accessibleName() == "Banque B : 4 concerts"
    assert tabs.tab(2).accessibleName() == "Banque C : vide"


def test_bank_b_shows_positions_1_to_4_then_init(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)
    assert page.bank == 1 and page.bank_tabs.tab(1).selected
    assert names(page) == ["Concert 17", "Concert 18", "Concert 19", "Concert 20"]
    assert [k.is_init for k in page.sequencer.keys] == [False] * 4 + [True] * 12
    assert page.key(1).toolTip() == ""                                    # D64
    assert page.key(1).accessibleDescription().startswith("B01, À venir. Concert 17. Salle 17.")
    assert page.sequencer.accessibleName() == "Touches, banque B"
    assert page.key(1).accessibleName() == "Touche B01 : Concert 17"
    assert page.slot(3).accessibleName() == "Emplacement B03 : Concert 19"
    assert page.key(5).accessibleName() == "Touche B05 : libre (INIT)"
    assert [page.key(n).group for n in (1, 5, 9, 13)] == [0, 1, 2, 3]      # mêmes couleurs
    assert page.slot(1).state is ConcertState.UPCOMING


def test_indicator_and_top_bar_unchanged_by_bank(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    before = (page.indicator.left.text(), page.indicator.link.text(), win.top_bar.info.readout)
    page.select_bank(1)
    assert (page.indicator.left.text(), page.indicator.link.text(),
            win.top_bar.info.readout) == before
    assert before[0] == "20 concerts à venir sur le dashboard"


def test_pairing_and_click_in_bank_b(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    page.select_bank(1)
    requests = []
    page.concert_requested.connect(requests.append)
    concert_18 = page.slot(2).key.concert.id
    qtbot.mouseClick(page.slot(2), Qt.LeftButton)
    qtbot.mouseClick(page.key(2), Qt.LeftButton, pos=page.key(2).body_rect().center().toPoint())
    assert requests == [concert_18, concert_18]
    qtbot.mouseClick(page.key(6), Qt.LeftButton)                # INIT de la banque B
    assert len(requests) == 2


def test_bank_change_is_instant_without_glide(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=True)
    page = win.main_page
    page.select_bank(1)
    assert page.reorder is None                                  # arbitrage 7
    win.toggle_sort()
    assert page.reorder is not None                              # 2.5 : glissement au changement de tri
    page.select_bank(0)
    assert page.reorder is None


def test_inactive_tab_click_does_nothing(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    qtbot.mouseClick(win.main_page.bank_tabs.tab(4), Qt.LeftButton)
    assert win.main_page.bank == 0
    assert not win.main_page.select_bank(4)


# --- tri et banques (D48) --------------------------------------------------------------------

def test_sort_toggle_keeps_bank_and_repaginates(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    page.select_bank(1)
    win.toggle_sort()
    assert page.bank == 1                                        # D47 : banque conservée
    assert names(page) == ["Concert 04", "Concert 03", "Concert 02", "Concert 01"]
    assert page.slot(4).state is ConcertState.TODAY              # état inchangé, banque B
    page.select_bank(0)
    assert names(page)[0] == "Concert 20"


# --- banque affichée (D47) -----------------------------------------------------------------------

def test_bank_kept_through_settings_and_day_change(qtbot, qapp, ud):
    now = [NOW]
    win = open_window(qtbot, qapp, ud, clock=lambda: now[0])
    page = win.main_page
    page.select_bank(1)
    win.show_settings()
    win.show_main()
    assert page.bank == 1
    now[0] = NOW + timedelta(days=1)                            # Concert 01 devient passé
    win.refresh()
    assert page.bank == 1
    assert names(page) == ["Concert 18", "Concert 19", "Concert 20"]   # B01 a glissé en A16
    page.select_bank(0)
    assert page.slot(16).name_text() == "Concert 17"


def test_new_window_starts_on_a(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    win.main_page.select_bank(1)
    win2 = open_window(qtbot, qapp, ud)
    assert win2.main_page.bank == 0


def test_emptied_bank_falls_back_to_last_occupied_then_a(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    page.select_bank(1)
    delete_concerts(ud, [f"Concert {i:02d}" for i in range(17, 21)])
    win.refresh()
    assert page.bank == 0 and page.bank_tabs.tab(0).selected
    assert not page.bank_tabs.tab(1).isEnabled()
    delete_concerts(ud, [f"Concert {i:02d}" for i in range(1, 17)])
    win.refresh()
    assert page.bank == 0 and page.empty_state.isVisible()
    a = page.bank_tabs.tab(0)
    assert a.selected and not a.isEnabled() and a.focusPolicy() == Qt.NoFocus   # arbitrage 8


def test_return_from_sheet_shows_concert_bank(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    concert_19 = page.view.bank(1)[2].concert.id
    assert page.show_concert_bank(concert_19) and page.bank == 1
    assert not page.show_concert_bank(999_999) and page.bank == 1   # plus sur le dashboard : D47


# --- clavier : ← → entre banques (D46) ------------------------------------------------------------

def test_arrows_cross_banks_both_ways_without_wrapping(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus(qtbot, win, page.key(16))
    qtbot.keyClick(page.key(16), Qt.Key_Right)                   # A16 → B01
    assert page.bank == 1 and page.key(1).hasFocus()
    qtbot.keyClick(page.key(1), Qt.Key_Left)                     # B01 → A16
    assert page.bank == 0 and page.key(16).hasFocus()
    qtbot.keyClick(page.key(16), Qt.Key_Right)
    qtbot.keyClick(page.key(1), Qt.Key_Right)
    qtbot.keyClick(page.key(2), Qt.Key_Right)
    qtbot.keyClick(page.key(3), Qt.Key_Right)
    assert page.key(4).hasFocus()
    qtbot.keyClick(page.key(4), Qt.Key_Right)                    # B04 : dernière active, pas de bouclage
    assert page.bank == 1 and page.key(4).hasFocus()
    page.select_bank(0)
    focus(qtbot, win, page.key(1))
    qtbot.keyClick(page.key(1), Qt.Key_Left)                     # A01 : rien
    assert page.bank == 0 and page.key(1).hasFocus()


# --- clavier : Page précédente / suivante (D46, arbitrage 5) ----------------------------------------

@pytest.mark.parametrize("start", ["key", "slot", "sort", "tab", "page"])
def test_page_keys_from_anywhere_in_dashboard(qtbot, qapp, ud, start):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    widget = {"key": page.key(3), "slot": page.slot(5), "sort": page.sort_button,
              "tab": page.bank_tabs.tab(0), "page": page}[start]
    focus(qtbot, win, widget)
    qtbot.keyClick(widget, Qt.Key_PageDown)
    assert page.bank == 1 and page.key(1).hasFocus()             # première touche active
    qtbot.keyClick(page.key(1), Qt.Key_PageDown)                 # pas d'autre banque occupée
    assert page.bank == 1 and page.key(1).hasFocus()
    qtbot.keyClick(page.key(1), Qt.Key_PageUp)
    assert page.bank == 0 and page.key(1).hasFocus()
    qtbot.keyClick(page.key(1), Qt.Key_PageUp)
    assert page.bank == 0


def test_page_keys_do_not_scroll_the_dashboard(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, size=(1024, 640))
    page = win.main_page
    bar = page.scroll.verticalScrollBar()
    assert bar.maximum() > 0
    focus(qtbot, win, page.key(2))
    qtbot.keyClick(page.key(2), Qt.Key_PageDown)
    assert bar.value() == 0 and page.bank == 1


def test_page_keys_inactive_outside_dashboard(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    win.show_settings()
    qtbot.keyClick(win.settings_page, Qt.Key_PageDown)
    assert win.main_page.bank == 0


# --- onglets au clavier (arbitrages 3 et 4) --------------------------------------------------------------

def test_tab_enters_selected_tab_then_keys(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    page.select_bank(1)
    tabs = page.bank_tabs
    assert [t.focusPolicy() for t in tabs.visible_tabs()][:2] == [Qt.NoFocus, Qt.TabFocus]
    focus(qtbot, win, tabs.tab(1))
    win.focusNextChild()
    assert page.key(1).hasFocus()                                 # la rangée ne compte qu'un arrêt
    win.focusPreviousChild()
    assert tabs.tab(1).hasFocus()


def test_tab_row_arrows_then_enter_selects(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page, tabs = win.main_page, win.main_page.bank_tabs
    focus(qtbot, win, tabs.tab(0))
    qtbot.keyClick(tabs.tab(0), Qt.Key_Right)
    assert tabs.tab(1).hasFocus() and page.bank == 0              # focus ≠ sélection
    qtbot.keyClick(tabs.tab(1), Qt.Key_Right)                     # C vide : rien, pas de bouclage
    assert tabs.tab(1).hasFocus()
    qtbot.keyClick(tabs.tab(1), Qt.Key_Return)
    assert page.bank == 1 and tabs.tab(1).hasFocus() and tabs.tab(1).selected


# --- focus après rafraîchissement (arbitrage 6) ---------------------------------------------------------

def test_focused_key_becoming_init_moves_to_first_active_key(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    page.select_bank(1)
    focus(qtbot, win, page.key(4))
    delete_concerts(ud, ["Concert 20"])                           # B04 devient INIT
    win.refresh()
    assert page.bank == 1 and page.key(4).is_init
    assert page.key(1).hasFocus()


def test_focused_slot_becoming_init_on_empty_dashboard_focuses_page(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus(qtbot, win, page.slot(2))
    delete_concerts(ud, [f"Concert {i:02d}" for i in range(1, 21)])
    win.refresh()
    assert page.view.is_empty
    assert page.hasFocus()


def test_focused_key_still_active_keeps_focus(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus(qtbot, win, page.key(5))
    win.refresh()
    assert page.key(5).hasFocus()


# --- nombreuses banques : AA et débordement de la rangée ------------------------------------------------------

def test_twenty_seven_banks_at_minimum_width(qtbot, qapp):
    win = open_window(qtbot, qapp, None, size=(1024, 640))
    page = win.main_page
    concerts = [ConcertSummary(i, f"C{i:03d}", date(2026, 11, 8) + timedelta(days=i), None,
                               SetlistStatus.MAINTAINED, 1) for i in range(1, 418)]
    page.set_view(build_dashboard(concerts, NOW))
    tabs = page.bank_tabs
    assert len(tabs.visible_tabs()) == 27 and tabs.tab(26).text() == "AA"
    qtbot.wait(20)
    assert tabs.overflowing()
    assert page.select_bank(26)
    assert names(page) == ["C417"] and page.key(1).accessibleName() == "Touche AA01 : C417"
    qtbot.wait(20)
    tab = tabs.tab(26)
    left = tab.mapTo(tabs.scroll.viewport(), tab.rect().topLeft()).x()
    assert 0 <= left and left + tab.width() <= tabs.scroll.viewport().width()


def test_tabs_aligned_with_first_key(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, size=(1600, 900))
    page = win.main_page
    tab_a, key_1 = page.bank_tabs.tab(0), page.key(1)
    tab_left = tab_a.mapTo(page.content, tab_a.body_rect().topLeft().toPoint()).x()
    key_left = key_1.mapTo(page.content, key_1.body_rect().topLeft().toPoint()).x()
    assert abs(tab_left - key_left) <= 1
