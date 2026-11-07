"""Incrément 2.5 : bouton de tri, mémorisation du sens, glissement des cartes.

D1 (défaut « Plus ancien d'abord »), D7 (mémorisé entre les sessions), D12
(libellés), D6 (à date égale, ordre alphabétique dans les deux sens), D11
(états indépendants du sens), section 06 (bouton à droite de « CONCERTS »,
glissement de 180 ms des cartes seules).
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt

from scenix16.domain.dashboard import ConcertState, SortOrder
from scenix16.importer.service import import_into_userdata
from scenix16.storage import preferences
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.dashboard.reorder_animation import DURATION_MS
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"
NOW = datetime(2026, 11, 7, 20, 0)
ROWS = [  # nom, date, lieu, statut
    ("Concert A", "2026-11-07", "Paris", "maintained"),        # aujourd'hui
    ("Concert B", "2026-11-19", None, "maintained"),
    ("Bal du 17", "2026-12-17", None, "maintained"),           # même date que Concert D (D6)
    ("Concert D", "2026-12-17", None, "maintained"),
    ("Concert C", "2026-12-05", None, "cancelled"),
    ("Antipode", "2025-11-14", None, "maintained"),
    ("Nouvelle setlist", None, None, "maintained"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def ud(tmp_path):
    folder = tmp_path / "UserData"
    check_writable(folder)
    conn = connect(database_path(folder))
    with conn:
        conn.executemany("INSERT INTO setlists(name, concert_date, venue, status) VALUES (?,?,?,?)", ROWS)
    conn.close()
    return folder


def open_window(qtbot, qapp, userdata, size=(1280, 800), animations=False):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(userdata, clock=lambda: NOW)
    win.main_page.animations = animations
    qtbot.addWidget(win)
    win.resize(*size)
    win.show()
    qtbot.waitExposed(win)
    return win


def key_names(page):
    return [k.toolTip().split("\n")[0] for k in page.sequencer.keys if not k.is_init]


# --- bouton dans la page ---------------------------------------------------------

def test_button_right_of_concerts_title(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    button, title = page.sort_button, page.concerts_title
    b = button.mapTo(page.content, QPoint(0, 0))
    ti = title.mapTo(page.content, QPoint(0, 0))
    assert b.x() > ti.x() + title.width()
    assert b.x() + button.width() <= page.content.width()
    assert page.content.width() - (b.x() + button.width()) <= 8     # calé à droite
    assert abs((b.y() + button.height() / 2) - (ti.y() + title.height() / 2)) <= 3
    assert button.isVisible() and button.isEnabled()


def test_button_visible_and_active_in_empty_state(qtbot, qapp, tmp_path):
    win = open_window(qtbot, qapp, None)
    page = win.main_page
    assert page.empty_state.isVisible()
    assert page.sort_button.isVisible() and page.sort_button.isEnabled()
    assert page.sort_button.focusPolicy() == Qt.TabFocus


# --- tri ---------------------------------------------------------------------------

def test_default_order_is_oldest_first(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    assert win.sort_order is SortOrder.OLDEST_FIRST
    assert win.main_page.sort_button.display_text() == "PLUS ANCIEN D'ABORD"
    assert key_names(win.main_page) == ["Concert A", "Concert B", "Bal du 17", "Concert D"]


def test_toggle_reverses_keys_and_slots(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    qtbot.mouseClick(page.sort_button, Qt.LeftButton)
    assert win.sort_order is SortOrder.NEWEST_FIRST
    assert page.sort_button.display_text() == "PLUS RÉCENT D'ABORD"
    # le plus lointain sur la touche 1 ; à date égale, ordre alphabétique conservé (D6)
    assert key_names(page) == ["Bal du 17", "Concert D", "Concert B", "Concert A"]
    assert [page.slot(n).name_text() for n in range(1, 5)] == key_names(page)
    qtbot.mouseClick(page.sort_button, Qt.LeftButton)
    assert key_names(page) == ["Concert A", "Concert B", "Bal du 17", "Concert D"]


def test_states_do_not_depend_on_order(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page

    def states():
        return {page.slot(n).name_text(): page.slot(n).state for n in range(1, 5)}
    before = states()
    win.toggle_sort()
    assert states() == before
    assert before["Concert A"] is ConcertState.TODAY


def test_top_bar_and_indicator_unchanged_by_order(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    chips = (win.top_bar.concerts_chip.text(), win.top_bar.date_chip.text())
    indicator = (win.main_page.indicator.left.text(), win.main_page.indicator.link.text())
    win.toggle_sort()
    assert (win.top_bar.concerts_chip.text(), win.top_bar.date_chip.text()) == chips
    assert (win.main_page.indicator.left.text(), win.main_page.indicator.link.text()) == indicator


# --- mémorisation (D7) -------------------------------------------------------------

def test_order_saved_and_restored_next_session(qtbot, qapp, ud):
    db_before = sha(database_path(ud))
    win = open_window(qtbot, qapp, ud)
    win.toggle_sort()
    data = json.loads(preferences.settings_path(ud).read_text(encoding="utf-8"))
    assert data["concerts_sort_order"] == "newest_first"
    win2 = open_window(qtbot, qapp, ud)
    assert win2.sort_order is SortOrder.NEWEST_FIRST
    assert win2.main_page.sort_button.display_text() == "PLUS RÉCENT D'ABORD"
    assert key_names(win2.main_page)[0] == "Bal du 17"
    assert sha(database_path(ud)) == db_before                 # la base n'est jamais touchée


def test_without_userdata_order_kept_for_session_only(qtbot, qapp):
    win = open_window(qtbot, qapp, None)
    win.toggle_sort()
    assert win.sort_order is SortOrder.NEWEST_FIRST
    assert win.main_page.sort_button.order is SortOrder.NEWEST_FIRST


def test_write_failure_never_blocks(qtbot, qapp, ud, monkeypatch):
    win = open_window(qtbot, qapp, ud)

    def refuse(src, dst):
        raise PermissionError("verrouillé")
    monkeypatch.setattr(preferences.os, "replace", refuse)
    win.toggle_sort()                                            # aucune exception
    assert win.sort_order is SortOrder.NEWEST_FIRST
    assert key_names(win.main_page)[0] == "Bal du 17"
    assert not preferences.settings_path(ud).exists()


def test_corrupt_settings_renamed_at_startup(qtbot, qapp, ud):
    preferences.settings_path(ud).write_text("{abîmé", encoding="utf-8")
    win = open_window(qtbot, qapp, ud)
    assert win.sort_order is SortOrder.OLDEST_FIRST
    assert (ud / "settings.corrupt-20261107-200000.json").exists()


# --- clavier -------------------------------------------------------------------------

def test_keyboard_toggle_keeps_focus_on_button(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    button = win.main_page.sort_button
    win.activateWindow()
    button.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(button.hasFocus)
    qtbot.keyClick(button, Qt.Key_Space)
    assert win.sort_order is SortOrder.NEWEST_FIRST
    assert button.hasFocus()
    qtbot.keyClick(button, Qt.Key_Return)
    assert win.sort_order is SortOrder.OLDEST_FIRST and button.hasFocus()


# --- glissement des cartes (180 ms) -------------------------------------------------------

def test_no_glide_when_animations_reduced(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=False)
    page = win.main_page
    qtbot.mouseClick(page.sort_button, Qt.LeftButton)
    assert page.reorder is None


def test_glide_cards_only_without_intercepting(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=True)
    page = win.main_page
    requests = []
    page.concert_requested.connect(requests.append)
    qtbot.mouseClick(page.sort_button, Qt.LeftButton)
    overlay = page.reorder
    assert overlay is not None and overlay.running
    assert overlay.parent() is page.slot_grid                   # cartes seulement, pas les touches
    assert overlay.geometry() == page.slot_grid.rect()
    assert overlay.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert overlay.focusPolicy() == Qt.NoFocus
    assert overlay.animation.duration() == DURATION_MS
    # touches et emplacements réels déjà dans leur état final
    assert key_names(page)[0] == "Bal du 17" and page.slot(1).name_text() == "Bal du 17"
    # un clic pendant le glissement atteint l'emplacement réel
    qtbot.mouseClick(page.slot(1), Qt.LeftButton)
    assert len(requests) == 1
    qtbot.waitUntil(lambda: page.reorder is None, timeout=2000)


def test_glide_images_have_transparent_background(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=True)
    win.toggle_sort()
    overlay = win.main_page.reorder
    images = list(overlay.before.values()) + list(overlay.after.values()) + overlay.free_after
    assert len(overlay.before) == len(overlay.after) == 4 and len(overlay.free_after) == 12
    for image in images:
        corner = image.pixmap.toImage().pixelColor(0, 0)
        assert corner.alpha() == 0                                # pas de fond clair autour des cartes


def test_glide_stops_on_refresh_and_resize(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=True)
    page = win.main_page
    win.toggle_sort()
    first = page.reorder
    assert first is not None
    win.toggle_sort()                                             # nouveau tri : l'ancien s'arrête
    assert not first.running and page.reorder is not None
    win.resize(1500, 800)
    qtbot.wait(20)
    assert page.reorder is None


def test_no_glide_on_plain_refresh(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=True)
    win.refresh()
    assert win.main_page.reorder is None


# --- base réelle : copie seulement -------------------------------------------------------------

def test_real_workbook_copy_empty_state_with_active_button(qtbot, qapp, tmp_path):
    ud = tmp_path / "UserData"
    check_writable(ud)
    import_into_userdata(WORKBOOK, ud)
    db = sha(database_path(ud))
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    assert page.empty_state.isVisible() and page.sort_button.isEnabled()
    win.toggle_sort()
    assert page.empty_state.isVisible()
    assert preferences.load_sort_order(ud) is SortOrder.NEWEST_FIRST
    assert sha(database_path(ud)) == db


# --- corrections de la revue technique de 2.5 -------------------------------------------

def _enter(widget):
    """Survol réel simulé : attribut Qt de survol, puis événement d'entrée."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent
    widget.setAttribute(Qt.WA_UnderMouse, True)
    widget.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))


def _leave(widget):
    from PySide6.QtCore import QEvent
    widget.setAttribute(Qt.WA_UnderMouse, False)
    widget.leaveEvent(QEvent(QEvent.Leave))


def test_hovered_card_ring_follows_toggle_then_clears(qtbot, qapp, ud):
    """Défaut 1 : plus d'anneau bloqué sur une carte après un changement de tri."""
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    _enter(page.slot(3))
    assert page.key(3).highlighted and page.slot(3).highlighted
    win.toggle_sort()                                     # la souris reste sur la carte 3
    assert page.slot(3).name_text() == "Concert B"        # nouveau concert sous la souris
    assert page.key(3).highlighted and page.slot(3).highlighted   # paire cohérente
    _leave(page.slot(3))
    assert not page.key(3).highlighted and not page.slot(3).highlighted
    assert not any(page.is_highlighted(n) for n in range(1, 17))


def test_hovered_key_ring_follows_refresh_then_clears(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    _enter(page.key(2))
    win.refresh()
    assert page.key(2).highlighted and page.slot(2).highlighted
    _leave(page.key(2))
    assert not page.key(2).highlighted and not page.slot(2).highlighted


def test_focused_card_ring_follows_toggle(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    win.activateWindow()
    page.slot(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.slot(2).hasFocus)
    win.toggle_sort()
    assert page.slot(2).hasFocus() and page.key(2).highlighted and page.slot(2).highlighted
    page.sort_button.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.sort_button.hasFocus)
    assert not page.key(2).highlighted and not page.slot(2).highlighted


def test_hovered_pair_becoming_init_is_not_highlighted(qtbot, qapp, ud):
    from scenix16.domain.dashboard import build_dashboard
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    _enter(page.slot(4))
    assert page.slot(4).highlighted
    page.set_view(build_dashboard([], NOW))               # la paire 4 devient INIT sous la souris
    assert not page.key(4).highlighted and not page.slot(4).highlighted
    _leave(page.slot(4))
    assert not page.is_highlighted(4)


def test_window_starts_with_pathological_settings(qtbot, qapp, ud):
    """Défaut 2 : le démarrage n'est jamais empêché par settings.json."""
    preferences.settings_path(ud).write_text("[" * 100_000, encoding="utf-8")
    win = open_window(qtbot, qapp, ud)
    assert win.sort_order is SortOrder.OLDEST_FIRST
    win.toggle_sort()
    assert preferences.load_sort_order(ud) is SortOrder.NEWEST_FIRST


def test_newer_settings_file_kept_and_session_order_works(qtbot, qapp, ud):
    """Amélioration 5 : défaut pour la session ; le tri fonctionne ; fichier intact."""
    content = b'{"version": 2, "concerts_sort_order": "newest_first", "futur": {}}'
    preferences.settings_path(ud).write_bytes(content)
    win = open_window(qtbot, qapp, ud)
    assert win.sort_order is SortOrder.OLDEST_FIRST
    win.toggle_sort()
    assert win.sort_order is SortOrder.NEWEST_FIRST and key_names(win.main_page)[0] == "Bal du 17"
    assert preferences.settings_path(ud).read_bytes() == content
