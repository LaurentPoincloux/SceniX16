"""Squelette du dashboard : barre supérieure, rail, zone centrale, barre d'état."""

from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from scenix16.importer.service import import_into_userdata
from scenix16.storage.userdata import check_writable
from scenix16.ui.main_window import MainWindow
from scenix16.ui.shell.nav_rail import NEW_SETLIST_LABEL, NavItem
from scenix16.ui.shell.status_line import StatusLine
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.theme.stylesheet import application_stylesheet

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"
NOW = datetime(2026, 11, 7, 12, 0)


@pytest.fixture(scope="module")
def userdata(tmp_path_factory):
    path = tmp_path_factory.mktemp("shell") / "UserData"
    check_writable(path)
    import_into_userdata(WORKBOOK, path)
    return path


@pytest.fixture
def window(qtbot, qapp, userdata):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(userdata, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# --- barre supérieure ---------------------------------------------------------

def test_top_bar_height_and_order(window):
    bar = window.top_bar
    assert bar.height() == t.TOP_BAR_HEIGHT
    xs = [w.mapTo(bar, w.rect().topLeft()).x()
          for w in (bar.logo, bar.concerts_chip, bar.date_chip, bar.gear_button)]
    assert xs == sorted(xs)                       # logo à gauche … engrenage à droite
    assert bar.gear_button.geometry().right() > bar.width() - 40


def test_top_bar_chips_are_compact_and_no_initial_focus_ring(window):
    for chip in (window.top_bar.concerts_chip, window.top_bar.date_chip):
        assert chip.height() < t.TOP_BAR_HEIGHT - 20          # pastilles, pas toute la hauteur
        middle = chip.y() + chip.height() / 2
        assert abs(middle - t.TOP_BAR_HEIGHT / 2) <= 1
    assert not window.gear_button.hasFocus()


def test_top_bar_markers(window):
    assert window.top_bar.concerts_chip.text() == "0 à venir · 3 passés"
    assert window.top_bar.date_chip.text() == "07/11/2026"


def test_top_bar_markers_with_other_clock(qtbot, qapp, userdata):
    win = MainWindow(userdata, clock=lambda: datetime(2026, 6, 22, 2, 30))
    qtbot.addWidget(win)
    assert win.top_bar.concerts_chip.text() == "1 à venir · 2 passés"   # Kiosque encore du jour
    assert win.top_bar.date_chip.text() == "22/06/2026"                 # date calendaire


# --- rail ---------------------------------------------------------------------

def test_rail_width_and_order(window):
    rail = window.rail
    assert rail.width() == t.RAIL_WIDTH
    assert [i.text() for i in rail.items.values()] == ["MAIN", "OUTPUT", "TRACKS", "SETLISTS"]
    ys = [i.y() for i in rail.items.values()] + [rail.new_setlist.y()]
    assert ys == sorted(ys)                       # NEW SETLIST juste après SETLISTS
    assert rail.new_setlist.text() == NEW_SETLIST_LABEL


def test_main_active_on_dashboard(window):
    assert window.rail.items["main"].active
    assert not any(window.rail.items[k].active for k in ("output", "tracks", "setlists"))


@pytest.mark.parametrize("key", ["output", "tracks", "setlists"])
def test_unavailable_sections_inactive(window, qtbot, key):
    item = window.rail.items[key]
    assert not item.isEnabled()
    assert item.focusPolicy() == Qt.NoFocus
    assert item.toolTip() == ""
    page_before = window.pages.currentWidget()
    qtbot.mouseClick(item, Qt.LeftButton)
    assert window.pages.currentWidget() is page_before


def test_new_setlist_inactive_but_orange(window, qtbot):
    button = window.rail.new_setlist
    assert not button.isEnabled() and button.focusPolicy() == Qt.NoFocus
    assert button.menu() is None                  # aucun comportement de menu
    image = button.grab().toImage()
    text_colors = {QColor(image.pixel(x, y)).name()
                   for x in range(image.width()) for y in range(image.height())}
    assert t.BRAND.lower() in text_colors          # identité orange conservée
    bg = QColor(image.pixel(4, image.height() // 2)).name()
    assert bg == t.BRAND_INACTIVE_BG.lower()       # pas d'aplat orange


def test_inactive_section_label_is_grey(window):
    item = window.rail.items["tracks"]
    image = item.grab().toImage()
    colors = {QColor(image.pixel(x, y)).name()
              for x in range(30, image.width()) for y in range(image.height())}
    assert QColor(t.TEXT).name() not in colors


# --- navigation avec PARAMÈTRES ----------------------------------------------

def test_settings_no_section_active_gear_active(window, qtbot):
    qtbot.mouseClick(window.gear_button, Qt.LeftButton)
    assert window.pages.currentWidget() is window.settings_page
    assert not any(i.active for i in window.rail.items.values())
    assert window.gear_button.property("active") is True
    assert window.rail.isVisible()


def test_main_in_rail_returns_from_settings(window, qtbot):
    window.show_settings()
    qtbot.mouseClick(window.rail.items["main"], Qt.LeftButton)
    assert window.pages.currentWidget() is window.main_page
    assert window.rail.items["main"].active
    assert window.gear_button.property("active") is False


def test_back_and_escape_still_work(window, qtbot):
    window.show_settings()
    qtbot.mouseClick(window.settings_page.back_button, Qt.LeftButton)
    assert window.pages.currentWidget() is window.main_page
    window.show_settings()
    qtbot.keyClick(window.settings_page, Qt.Key_Escape)
    assert window.pages.currentWidget() is window.main_page


# --- zone centrale ------------------------------------------------------------

def test_content_capped_and_centered_on_wide_window(window, qtbot):
    window.resize(2560, 1400)
    qtbot.wait(50)
    content = window.main_page.content
    assert content.width() <= t.CONTENT_MAX_WIDTH
    left = content.x()
    right = window.main_page.width() - content.x() - content.width()
    assert abs(left - right) <= 2


def test_content_fills_at_minimum_size(window, qtbot):
    window.resize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
    qtbot.wait(50)
    assert window.width() == t.WINDOW_MIN_WIDTH
    content = window.main_page.content
    assert content.width() == window.main_page.width() - 56     # marges 28 + 28
    assert window.pages.width() == t.WINDOW_MIN_WIDTH - t.RAIL_WIDTH


# --- barre d'état -------------------------------------------------------------

def test_status_line_content(window):
    assert window.status_line.height() == t.STATUS_BAR_HEIGHT
    assert window.status_line.texts() == ["SceniX16", "37 titres au catalogue", "3 setlists"]


def test_no_diagnostic_in_portable_mode(qtbot, qapp, userdata, monkeypatch):
    from scenix16.ui.shell import status_line
    monkeypatch.setattr(status_line, "is_frozen", lambda: True)
    line = StatusLine()
    qtbot.addWidget(line)
    assert line.diagnostic is None


def test_diagnostic_in_development_only(qtbot, qapp):
    line = StatusLine(show_diagnostic=True)
    qtbot.addWidget(line)
    line.update_diagnostic(1.5)
    assert line.diagnostic.text().startswith("dév.")


# --- actualisation après import ----------------------------------------------

def test_counts_refresh_when_returning_to_main(qtbot, qapp, tmp_path):
    from scenix16.storage import database
    from scenix16.storage.userdata import database_path
    ud = tmp_path / "UserData"
    check_writable(ud)
    database.connect(database_path(ud)).close()
    win = MainWindow(ud, clock=lambda: NOW)
    qtbot.addWidget(win)
    assert win.status_line.texts()[1] == "0 titre au catalogue"
    win.show_settings()
    import_into_userdata(WORKBOOK, ud)             # import fait depuis PARAMÈTRES
    win.show_main()
    assert win.status_line.texts()[1:] == ["37 titres au catalogue", "3 setlists"]
    assert win.top_bar.concerts_chip.text() == "0 à venir · 3 passés"
