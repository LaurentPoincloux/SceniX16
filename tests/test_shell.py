"""Squelette du dashboard : barre supérieure, rail, zone centrale, barre d'état."""

from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from scenix16.importer.service import import_into_userdata
from scenix16.storage.userdata import check_writable
from scenix16.ui.main_window import MainWindow
from scenix16.ui.shell.nav_rail import NEW_SETLIST_LABEL
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
    xs = [w.mapTo(bar, w.rect().topLeft()).x() for w in (bar.menu_bar, bar.info, bar.gear_button)]
    assert xs == sorted(xs)                       # menus à gauche … afficheur … engrenage à droite
    assert bar.gear_button.geometry().right() > bar.width() - 40
    assert not hasattr(bar, "logo")               # D58 : le logo n'est plus dans la barre supérieure


def test_info_display_geometry_and_no_initial_focus_ring(window):
    info = window.top_bar.info
    assert info.height() == 36                    # D60
    middle = info.y() + info.height() / 2
    assert abs(middle - t.TOP_BAR_HEIGHT / 2) <= 1
    assert info.focusPolicy() == Qt.NoFocus
    assert not window.gear_button.hasFocus()


def test_info_display_content(window):
    r = window.top_bar.info.readout
    assert (r.upcoming, r.upcoming_label, r.past, r.past_label, r.date) ==         ("0", "À VENIR", "3", "PASSÉS", "07/11/2026")
    assert window.top_bar.info.accessibleName() ==         "0 concert à venir, 3 passés, date de référence 7 novembre 2026"


def test_info_display_uses_scenix16_day(qtbot, qapp, userdata):
    win = MainWindow(userdata, clock=lambda: datetime(2026, 6, 22, 2, 30))
    qtbot.addWidget(win)
    r = win.top_bar.info.readout
    assert (r.upcoming, r.past) == ("1", "2")                     # Kiosque encore du jour
    assert r.date == "21/06/2026"                                 # D60, Q12 : jour SceniX16, la veille


def test_info_display_flat_panel_without_glow(window):
    info = window.top_bar.info
    image = info.grab().toImage()
    colors = {QColor(image.pixel(x, y)).name() for x in range(image.width()) for y in range(image.height())}
    assert t.LCD_BG.lower() in colors and t.SILK.lower() in colors
    # ni vert ni lueur (les franges ClearType du texte, bleutées, ne comptent pas)
    assert not any(QColor(c).green() > max(QColor(c).red(), QColor(c).blue()) + 40 for c in colors)
    corner = QColor(image.pixel(4, info.height() // 2)).name()
    assert corner == t.LCD_BG.lower()                                    # aplat, sans dégradé


# --- rail ---------------------------------------------------------------------

def test_rail_width_and_order(window):
    rail = window.rail
    assert rail.width() == t.RAIL_WIDTH
    assert [i.text() for i in rail.items.values()] == ["CONCERTS", "OUTPUT", "TRACKS", "SETLISTS"]   # v0.48
    assert rail.items["main"].accessibleName() == "CONCERTS"                 # clé interne inchangée
    ys = [i.y() for i in rail.items.values()] + [rail.new_setlist.y()]
    assert ys == sorted(ys)                       # NEW SETLIST juste après SETLISTS
    assert rail.new_setlist.text() == NEW_SETLIST_LABEL


def test_rail_logo_rule_and_menu_label(window):
    rail = window.rail
    assert window.logo is rail.logo and rail.logo.source_is_valid()
    assert rail.logo.height() == 40                                    # D58 (v0.44)
    assert rail.group_label.text() == "MENU"
    ys = [w.mapTo(rail, w.rect().topLeft()).y() for w in (rail.logo, rail.rule, rail.group_label)]
    assert ys == sorted(ys)                                            # logo, filet, puis MENU
    assert rail.rule.height() == 1 and rail.rule.width() == rail.width()   # filet pleine largeur
    left = rail.logo.mapTo(rail, rail.logo.rect().topLeft()).x()
    right = rail.width() - (left + rail.logo.width())
    assert abs(left - right) <= 1                                      # centré (D58, v0.44)
    assert left >= 28 and right >= 28                                  # marges latérales ≈ 30 px
    source = rail.logo._source
    assert abs(rail.logo.width() - source.width() * 40 / source.height()) <= 1   # proportions
    top = rail.logo.mapTo(rail, rail.logo.rect().topLeft()).y()
    rule_y = rail.rule.mapTo(rail, rail.rule.rect().topLeft()).y()
    assert top == 20 and rule_y - (top + rail.logo.height()) == 18     # 20 px au-dessus, 18 au-dessous
    image = rail.grab().toImage()
    y = rail.rule.mapTo(rail, rail.rule.rect().topLeft()).y()
    assert QColor(image.pixel(rail.width() // 2, y)).name() == t.LINE_SOFT.lower()


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
    assert content.width() == window.main_page.scroll.viewport().width() - 56   # marges 28 + 28, hors barre de défilement
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
    assert (win.top_bar.info.readout.upcoming, win.top_bar.info.readout.past) == ("0", "3")
