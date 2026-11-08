"""Aperçu au survol (D64, incrément 2.6b) : position, contenu, déclenchement, fermeture, Échap, 200 %.

Toutes les données sont dans une base temporaire ; la base réelle n'est jamais ouverte.
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QEnterEvent

from scenix16.services.dashboard_service import PreviewContent
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.dashboard.concert_preview import (EDGE, GAP, MAX_WIDTH, MIN_WIDTH, PREVIEW_DELAY_MS,
                                                   ConcertPreview, preview_geometry, preview_width)
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

NOW = datetime(2026, 11, 7, 20, 0)
SRC = Path(__file__).resolve().parents[1] / "src"
LONG = "Réveillon au Théâtre municipal de Châtellerault avec invités et surprises de fin d'année"


# --- position (fonction pure, coordonnées logiques) ----------------------------------------

AREA = QRect(0, 0, 1000, 600)


def test_below_card_aligned_left():
    g = preview_geometry(QRect(100, 100, 230, 104), QSize(300, 150), AREA)
    assert (g.x(), g.y()) == (100, 100 + 104 + GAP)


def test_above_when_no_room_below():
    g = preview_geometry(QRect(100, 420, 230, 104), QSize(300, 150), AREA)
    assert g.y() == 420 - GAP - 150 and g.bottom() < 420


def test_clamped_horizontally_with_margin():
    right = preview_geometry(QRect(900, 100, 90, 104), QSize(300, 150), AREA)
    assert right.right() == AREA.right() - EDGE
    left = preview_geometry(QRect(-20, 100, 90, 104), QSize(300, 150), AREA)
    assert left.left() == EDGE


def test_avoid_rect_rejects_above_placement():
    key = QRect(100, 120, 60, 100)                    # touche survolée, au-dessus de la carte
    g = preview_geometry(QRect(100, 420, 230, 104), QSize(300, 150), AREA, avoid=key)
    assert not g.intersects(key)
    assert AREA.contains(g)


def test_always_inside_area_even_when_too_tall():
    g = preview_geometry(QRect(100, 250, 230, 104), QSize(300, 560), AREA)
    assert g.top() >= EDGE and g.bottom() <= AREA.bottom()


@pytest.mark.parametrize("card, area, expected", [
    (230, 1000, MIN_WIDTH), (360, 1000, 360), (600, 1000, MAX_WIDTH), (230, 280, 280 - 2 * EDGE),
])
def test_preview_width(card, area, expected):
    assert preview_width(card, area) == expected


# --- composant --------------------------------------------------------------------

def content(name="Le Kiosque", venue="Le Kiosque\nChauvigny (86)"):
    return PreviewContent("B03", "À VENIR", False, name, venue, "samedi 21 novembre 2026", "J-14", "18 titres")


def test_widget_never_takes_focus_or_mouse(qtbot, qapp):
    w = ConcertPreview()
    qtbot.addWidget(w)
    assert w.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert w.focusPolicy() == Qt.NoFocus and not w.isVisible()


def test_long_name_wraps_instead_of_eliding(qtbot, qapp):
    fonts.load_fonts()
    w = ConcertPreview()
    qtbot.addWidget(w)
    w.set_content(content(), "#FF4E3A", 300)
    short = w.height()
    w.set_content(content(name=LONG), "#FF4E3A", 300)
    assert w.height() > short                          # nom complet sur plusieurs lignes
    assert w.content.name == LONG


# --- dans la fenêtre ----------------------------------------------------------------

def rows(n=20):
    data = [(f"Concert {i:02d}", (date(2026, 11, 7) + timedelta(days=7 * (i - 1))).isoformat(),
             f"Salle {i:02d}\nVille {i:02d}", "maintained") for i in range(1, n + 1)]
    data[2] = (LONG, data[2][1], data[2][2], "maintained")
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


def open_window(qtbot, qapp, userdata, size=(1280, 800), animations=False):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(userdata, clock=lambda: NOW)
    win.main_page.animations = animations
    qtbot.addWidget(win)
    win.resize(*size)
    away_from_cursor(win)
    win.show()
    qtbot.waitExposed(win)
    qtbot.wait(50)
    calm(win.main_page)
    return win


def away_from_cursor(win):
    """Place la fenêtre de test hors du vrai curseur, pour qu'aucun survol réel n'interfère."""
    from PySide6.QtGui import QCursor, QGuiApplication
    cursor = QCursor.pos()
    screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
    avail = screen.availableGeometry()
    x = avail.right() - win.width() + 1 if cursor.x() < avail.center().x() else avail.left()
    y = avail.bottom() - win.height() + 1 if cursor.y() < avail.center().y() else avail.top()
    win.move(x, y)


def calm(page):
    """Neutralise le survol réel (le vrai curseur peut se trouver au-dessus de la fenêtre de test)
    et le focus initial, qui peut tomber sur la touche 01 à l'activation de la fenêtre."""
    page.setFocus(Qt.OtherFocusReason)
    for n in range(1, 17):
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)
    page.hide_preview()


def _pair(widget):
    """Page, numéro de la paire et source de survol du widget (touche ou carte)."""
    page = widget.window().main_page
    for n in range(1, 17):
        if widget is page.key(n):
            return page, n, "key-hover"
        if widget is page.slot(n):
            return page, n, "slot-hover"
    raise AssertionError("widget hors dashboard")


def enter(widget):
    """Survol simulé par le couplage de la page : déterministe, sans déplacer le vrai curseur."""
    page, n, source = _pair(widget)
    if not widget.is_init:
        page._pair_source(n, source, True)


def leave(widget):
    page, n, source = _pair(widget)
    page._pair_source(n, source, False)


def rect_in_page(page, widget, rect):
    return QRect(widget.mapTo(page, rect.topLeft().toPoint()), rect.size().toSize())


def area_of(page):
    vp = page.scroll.viewport()
    return QRect(vp.mapTo(page, vp.rect().topLeft()), vp.size())


def test_appears_after_delay_under_the_card(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    enter(page.slot(2))
    qtbot.wait(PREVIEW_DELAY_MS // 3)
    assert not page.preview_visible()                  # pas avant 350 ms
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    card = rect_in_page(page, page.slot(2), page.slot(2).card_rect())
    g = page.preview.geometry()
    assert g.top() == card.bottom() + 1 + GAP and g.left() == card.left()
    assert area_of(page).contains(g)
    assert page.preview.content.address == "A02" and page.preview.content.name == "Concert 02"


def test_hovering_key_attaches_preview_to_card_without_covering_key(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    enter(page.key(3))
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.preview.number == 3 and page.preview.content.name == LONG   # nom complet
    key = rect_in_page(page, page.key(3), page.key(3).body_rect())
    assert not page.preview.geometry().intersects(key)


def test_leave_click_and_init(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    enter(page.slot(1))
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    leave(page.slot(1))
    assert not page.preview_visible()                  # disparaît dès la sortie
    enter(page.slot(1))
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    qtbot.mouseClick(page.slot(1), Qt.LeftButton)
    assert not page.preview_visible()                  # clic
    page.select_bank(1)
    enter(page.slot(10))                               # INIT en banque B
    qtbot.wait(PREVIEW_DELAY_MS + 150)
    assert not page.preview_visible()


def test_escape_closes_and_suppresses_until_new_highlight(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    win.activateWindow()
    page.slot(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.slot(2).hasFocus)
    qtbot.waitUntil(page.preview_visible, timeout=1500)   # focus clavier : aperçu aussi
    qtbot.keyClick(page.slot(2), Qt.Key_Escape)
    assert not page.preview_visible()
    qtbot.wait(PREVIEW_DELAY_MS + 200)
    assert not page.preview_visible()                  # ne revient pas sans nouvelle mise en évidence
    assert page.slot(2).hasFocus() and page.bank == 0  # Échap n'a rien fait d'autre
    page.slot(3).setFocus(Qt.TabFocusReason)           # nouvelle mise en évidence
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.preview.number == 3


def test_escape_without_preview_does_nothing(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    win.activateWindow()
    page.key(1).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.key(1).hasFocus)
    page.hide_preview()
    qtbot.keyClick(page.key(1), Qt.Key_Escape)
    assert page.key(1).hasFocus() and page.bank == 0 and win.pages.currentWidget() is page


def test_bank_sort_scroll_and_refresh_close_preview(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, size=(1024, 640))
    page = win.main_page

    def show(n):
        leave(page.slot(n))
        enter(page.slot(n))
        qtbot.waitUntil(page.preview_visible, timeout=1500)

    show(1)
    page.select_bank(1)
    assert not page.preview_visible()                  # changement de banque
    page.select_bank(0)
    show(1)
    win.toggle_sort()
    assert not page.preview_visible()                  # changement de tri
    show(1)
    page.scroll.verticalScrollBar().setValue(40)
    assert not page.preview_visible()                  # défilement
    show(1)
    win.refresh()
    assert not page.preview_visible()                  # rafraîchissement


def test_bottom_row_above_and_inside_at_minimum_size(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, size=(1024, 640))
    page = win.main_page
    page.scroll.ensureWidgetVisible(page.slot(16))
    qtbot.wait(20)
    enter(page.slot(15))
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    g, area = page.preview.geometry(), area_of(page)
    card = rect_in_page(page, page.slot(15), page.slot(15).card_rect())
    assert area.contains(g) and not g.intersects(card)


def test_fade_only_when_animations_enabled(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud, animations=False)
    page = win.main_page
    enter(page.slot(1))
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert not page.preview.fading() and page.preview.graphicsEffect().opacity() == 1.0
    win2 = open_window(qtbot, qapp, ud, animations=True)
    page2 = win2.main_page
    enter(page2.slot(1))
    qtbot.waitUntil(page2.preview_visible, timeout=1500)
    assert page2.preview.fading() or page2.preview.graphicsEffect().opacity() == 1.0
    qtbot.waitUntil(lambda: not page2.preview.fading(), timeout=1000)
    assert page2.preview.graphicsEffect().opacity() == 1.0


# --- 200 % : coordonnées logiques Qt, dans un processus séparé ------------------------------------

SCRIPT_200 = textwrap.dedent('''
    import json, sys
    from datetime import datetime
    from pathlib import Path
    from PySide6.QtCore import QEvent, QPointF, QRect, Qt
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtTest import QTest
    from scenix16.app import create_application
    from scenix16.ui.main_window import MainWindow
    app = create_application(sys.argv[:1])
    win = MainWindow(Path(sys.argv[1]), clock=lambda: datetime(2026, 11, 7, 20, 0), show_diagnostic=False)
    win.main_page.animations = False
    win.resize(1024, 640); win.show(); QTest.qWaitForWindowExposed(win)
    page = win.main_page
    out = {"dpr": win.devicePixelRatioF(), "cases": []}
    for n in (1, 4, 13, 16):
        page.hide_preview()
        page.scroll.ensureWidgetVisible(page.slot(n)); QTest.qWait(30)
        s = page.slot(n)
        s.setAttribute(Qt.WA_UnderMouse, True)
        s.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
        QTest.qWait(500)
        vp = page.scroll.viewport()
        area = QRect(vp.mapTo(page, vp.rect().topLeft()), vp.size())
        g = page.preview.geometry()
        card = QRect(s.mapTo(page, s.card_rect().topLeft().toPoint()), s.card_rect().size().toSize())
        out["cases"].append({"n": n, "visible": page.preview.isVisible(), "inside": area.contains(g),
                             "overlaps_card": g.intersects(card), "g": [g.x(), g.y(), g.width(), g.height()],
                             "area": [area.x(), area.y(), area.width(), area.height()],
                             "window": [win.width(), win.height()]})
        s.setAttribute(Qt.WA_UnderMouse, False); s.leaveEvent(QEvent(QEvent.Leave))
    print(json.dumps(out))
''')


def test_preview_inside_window_at_200_percent(tmp_path, ud):
    script = tmp_path / "preview_200.py"
    script.write_text(SCRIPT_200, encoding="utf-8")
    env = dict(os.environ, QT_SCALE_FACTOR="2", PYTHONPATH=str(SRC))
    done = subprocess.run([sys.executable, str(script), str(ud)], capture_output=True, text=True,
                          env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["dpr"] == 2.0
    for case in result["cases"]:
        assert case["visible"], case
        assert case["inside"], case                     # entièrement visible, en coordonnées logiques
        assert not case["overlaps_card"], case
        assert MIN_WIDTH <= case["g"][2] <= MAX_WIDTH


# --- stabilité de la mise en page (défaut trouvé en 2.6b) -----------------------------------------

def test_column_width_independent_of_scrollbar(qtbot, qapp, ud):
    """La barre de défilement ne change pas la largeur de la colonne : pas d'oscillation sans fin."""
    win = open_window(qtbot, qapp, ud, size=(1280, 800))
    page = win.main_page
    resizes = []
    original = type(page.sequencer).resizeEvent
    page.sequencer.resizeEvent = lambda e: (resizes.append(e.size().toTuple()), original(page.sequencer, e))
    qtbot.wait(400)
    assert resizes == []                                  # aucun redimensionnement au repos
    widths = set()
    for height in (640, 700, 760, 800, 860):              # barre présente, puis absente
        win.resize(1280, height)
        qtbot.wait(60)
        widths.add(page.content.width())
    assert len(widths) == 1


# --- l'aperçu suit le focus après un rendu (correction F1 de 2.6b) ---------------------------------

def focus_and_wait(qtbot, page, widget):
    calm(page)                                          # aucun survol réel ne doit interférer
    widget.window().activateWindow()
    widget.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus)
    qtbot.waitUntil(page.preview_visible, timeout=1500)


def test_page_down_from_key_01_reschedules_preview(qtbot, qapp, ud):
    """Page suivante depuis la touche 01 : le focus reste sur le même widget, l'aperçu suit."""
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus_and_wait(qtbot, page, page.key(1))
    assert page.preview.content.address == "A01"
    qtbot.keyClick(page.key(1), Qt.Key_PageDown)
    assert page.bank == 1 and page.key(1).hasFocus()
    assert not page.preview_visible()                  # fermé au changement de banque…
    qtbot.waitUntil(page.preview_visible, timeout=1500)  # …puis reprogrammé pour la paire focalisée
    assert page.preview.number == 1 and page.preview.content.address == "B01"
    qtbot.keyClick(page.key(1), Qt.Key_PageUp)
    assert page.bank == 0 and not page.preview_visible()
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.preview.content.address == "A01"


def test_page_down_from_card_keeps_focus_and_preview(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus_and_wait(qtbot, page, page.slot(1))
    page.page_bank(+1)                                  # focus sur la première touche active de B
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.bank == 1 and page.key(1).hasFocus() and page.preview.content.address == "B01"


def test_refresh_reschedules_preview_for_focused_pair(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    for widget in (page.key(2), page.slot(3)):          # touche, puis carte
        focus_and_wait(qtbot, page, widget)
        win.refresh()
        assert widget.hasFocus() and not page.preview_visible()
        qtbot.waitUntil(page.preview_visible, timeout=1500)
        assert page.preview.number == widget.number


def test_refresh_without_focused_pair_does_not_show_preview(qtbot, qapp, ud):
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    enter(page.slot(4))                                 # survol seul : fermé, pas reprogrammé
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    win.refresh()
    qtbot.wait(PREVIEW_DELAY_MS + 200)
    assert not page.preview_visible()


def test_escape_still_respected_after_refresh(qtbot, qapp, ud):
    """Échap, puis rafraîchissement sans changement de focus : pas de réapparition."""
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus_and_wait(qtbot, page, page.key(3))
    qtbot.keyClick(page.key(3), Qt.Key_Escape)
    win.refresh()
    qtbot.wait(PREVIEW_DELAY_MS + 200)
    assert not page.preview_visible() and page.key(3).hasFocus()
    qtbot.keyClick(page.key(3), Qt.Key_Right)          # le focus change : l'aperçu revient
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.preview.number == 4


def test_escape_then_page_down_shows_new_bank_preview(qtbot, qapp, ud):
    """Après Échap, Page suivante affiche un autre concert sur la paire focalisée : nouvel aperçu."""
    win = open_window(qtbot, qapp, ud)
    page = win.main_page
    focus_and_wait(qtbot, page, page.key(1))
    qtbot.keyClick(page.key(1), Qt.Key_Escape)
    assert not page.preview_visible()
    qtbot.keyClick(page.key(1), Qt.Key_PageDown)
    qtbot.waitUntil(page.preview_visible, timeout=1500)
    assert page.bank == 1 and page.preview.content.address == "B01"
