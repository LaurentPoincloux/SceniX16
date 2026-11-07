"""Dashboard : 16 touches, 16 emplacements, couplage, clavier, indicateur, état vide."""

from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent

from scenix16.domain.dashboard import ConcertState, build_dashboard
from scenix16.domain.models import ConcertSummary, SetlistStatus
from scenix16.importer.service import import_into_userdata
from scenix16.storage.userdata import check_writable
from scenix16.ui.dashboard.page import CONCERTS_TITLE, KEYS_TITLE, DashboardPage
from scenix16.ui.dashboard.sequencer import GROUP_GAP, KEY_GAP, key_columns
from scenix16.ui.dashboard.slot_grid import COMPACT_BELOW
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.theme.stylesheet import application_stylesheet
from scenix16.ui.widgets.step_key import ASPECT, MAX_WIDTH, GROUP_COLORS

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"
NOW = datetime(2026, 11, 7, 20, 0)
M, C = SetlistStatus.MAINTAINED, SetlistStatus.CANCELLED


def concert(i, name, d, status=M, venue=None):
    return ConcertSummary(i, name, d, venue, status, 10)


def demo_view(extra=0):
    concerts = [
        concert(1, "Concert A", date(2026, 11, 7), venue="Paris\nAntipode"),   # aujourd'hui
        concert(2, "Concert B", date(2026, 11, 19)),
        concert(3, "Concert D", date(2026, 12, 17)),
        concert(4, "Antipode", date(2025, 11, 14)),                            # passé
        concert(5, "Concert C", date(2026, 12, 5), C),                         # annulé
        concert(6, "Nouvelle setlist", None),                                  # sans date
    ]
    concerts += [concert(10 + i, f"Suite {i:02d}", date(2027, 1, 1 + i)) for i in range(extra)]
    return build_dashboard(concerts, NOW)


@pytest.fixture
def page(qtbot, qapp):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    p = DashboardPage(animations=False)
    qtbot.addWidget(p)
    p.resize(1100, 700)
    p.set_view(demo_view())
    p.show()
    qtbot.waitExposed(p)
    p.setFocusPolicy(Qt.ClickFocus)      # comme MainWindow : la page garde le focus initial
    p.activateWindow()
    p.setFocus()
    qtbot.waitUntil(p.hasFocus)
    return p


def hover(widget, inside: bool):
    if inside:
        widget.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    else:
        widget.leaveEvent(QEvent(QEvent.Leave))


# --- touches ------------------------------------------------------------------

def test_sixteen_keys_numbered_and_grouped(page):
    keys = page.sequencer.keys
    assert [k.number for k in keys] == list(range(1, 17))
    assert [k.group for k in keys] == [0] * 4 + [1] * 4 + [2] * 4 + [3] * 4
    assert page.keys_title.text() == KEYS_TITLE and page.concerts_title.text() == CONCERTS_TITLE


def test_keys_reflect_domain_view(page):
    states = [(k.is_init, k.led.value) for k in page.sequencer.keys[:4]]
    assert states == [(False, "halo"), (False, "on"), (False, "on"), (True, "off")]  # D11 : pas de PROCHAIN si concert ce jour
    assert page.key(1).pulsing is False                          # animations désactivées en test
    assert all(k.is_init for k in page.sequencer.keys[3:])


def test_key_tooltip_name_venue_date(page):
    assert page.key(1).toolTip() == "Concert A\nParis\nAntipode\n07/11/2026"


@pytest.mark.parametrize("width", [760, 1016, 1392, 1600])
def test_keys_ratio_and_gaps(width):
    cols = key_columns(width)
    assert cols.body_width <= MAX_WIDTH
    assert cols.left[1] - cols.right(0) == pytest.approx(KEY_GAP)
    assert cols.left[4] - cols.right(3) == pytest.approx(GROUP_GAP)


def test_key_bodies_keep_three_five(page, qtbot):
    for width in (900, 1300, 1700):
        page.resize(width, 800)
        qtbot.wait(20)
        body = page.key(1).body_rect()
        assert body.height() / body.width() == pytest.approx(ASPECT, abs=0.03)


def test_keys_at_minimum_window_stay_readable(qtbot, qapp):
    """Arbitrage A : à 1024 px, touches sous 44 px mais sans débordement ni chevauchement."""
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.resize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
    win.show()
    qtbot.waitExposed(win)
    seq = win.main_page.sequencer
    bodies = [k.mapTo(seq, k.body_rect().topLeft().toPoint()).x() for k in seq.keys]
    widths = [k.body_rect().width() for k in seq.keys]
    assert 30 < widths[0] < 44
    assert bodies == sorted(bodies)
    assert bodies[-1] + widths[-1] <= seq.width()
    assert seq.keys[0].number_font().pixelSize() >= 10


# --- emplacements -------------------------------------------------------------

def test_slots_follow_keys(page):
    assert page.slot(1).name_text() == "Concert A"
    assert page.slot(1).state is ConcertState.TODAY
    assert page.slot(2).state is ConcertState.UPCOMING
    assert page.slot(4).is_init and page.slot(16).is_init
    assert page.slot(1).venue_text() == "Paris Antipode"


def test_mode_2x8_slots_span_two_keys(qtbot, qapp):
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.resize(1600, 900)
    win.show()
    qtbot.waitExposed(win)
    page = win.main_page
    page.set_view(demo_view())
    grid, seq = page.slot_grid, page.sequencer
    assert grid.mode == "2x8"
    cols = key_columns(seq.width())
    rects = grid.card_rects()
    for j in range(8):
        assert rects[j].left() == pytest.approx(cols.left[2 * j])
        assert rects[j].right() == pytest.approx(cols.right(2 * j + 1))
    assert rects[8].top() > rects[0].top()                       # 9 à 16 sur la 2e rangée
    assert rects[8].left() == pytest.approx(rects[0].left())


def test_mode_4x4_below_1360(qtbot, qapp):
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.resize(COMPACT_BELOW - 1, 900)
    win.show()
    qtbot.waitExposed(win)
    grid = win.main_page.slot_grid
    assert grid.mode == "4x4"
    rects = grid.card_rects()
    rows = sorted({round(r.top()) for r in rects})
    assert len(rows) == 4
    assert all(round(rects[i].top()) == rows[i // 4] for i in range(16))   # une rangée par groupe
    win.resize(COMPACT_BELOW, 900)
    qtbot.wait(20)
    assert grid.mode == "2x8"


def test_slot_group_colors(page):
    assert [page.slot(n).group for n in (1, 5, 9, 13)] == [0, 1, 2, 3]
    assert GROUP_COLORS[page.slot(16).group] == t.KEY_WHITE


# --- couplage touche / emplacement ---------------------------------------------

def test_hover_key_highlights_pair_once(page):
    events = []
    page.slot(1).set_highlighted = (lambda orig: (lambda v: (events.append(v), orig(v))))(page.slot(1).set_highlighted)
    hover(page.key(1), True)
    assert page.key(1).highlighted and page.slot(1).highlighted
    hover(page.key(1), False)
    assert not page.key(1).highlighted and not page.slot(1).highlighted
    assert events == [True, False]                               # un seul déclenchement par transition


def test_hover_slot_highlights_key(page):
    hover(page.slot(2), True)
    assert page.key(2).highlighted and page.slot(2).highlighted
    hover(page.slot(2), False)
    assert not page.key(2).highlighted


def test_overlapping_sources_no_flicker(page):
    hover(page.key(3), True)
    hover(page.slot(3), True)                 # souris passe de la touche à l'emplacement
    hover(page.key(3), False)
    assert page.is_highlighted(3) and page.key(3).highlighted
    hover(page.slot(3), False)
    assert not page.is_highlighted(3)


def test_init_pair_never_highlighted(page):
    hover(page.key(10), True)
    hover(page.slot(10), True)
    assert not page.key(10).highlighted and not page.slot(10).highlighted


# --- clic : demande d'ouverture (D8, arbitrage B) ------------------------------

def test_click_key_or_slot_emits_same_request(page, qtbot):
    requests = []
    page.concert_requested.connect(requests.append)
    qtbot.mouseClick(page.key(2), Qt.LeftButton, pos=page.key(2).body_rect().center().toPoint())
    qtbot.mouseClick(page.slot(2), Qt.LeftButton)
    assert requests == [2, 2]


def test_click_init_does_nothing(page, qtbot):
    requests = []
    page.concert_requested.connect(requests.append)
    qtbot.mouseClick(page.key(12), Qt.LeftButton)
    qtbot.mouseClick(page.slot(12), Qt.LeftButton)
    assert requests == []


def test_open_concert_ring(page):
    page.set_open_concert(2)
    assert page.key(2).selected and page.slot(2).selected
    assert not page.key(1).selected


# --- clavier (D9, arbitrage E) --------------------------------------------------

def test_arrows_skip_init_and_stop_at_ends(page, qtbot):
    page.activateWindow()
    page.key(1).setFocus()
    qtbot.waitUntil(page.key(1).hasFocus)
    qtbot.keyClick(page.key(1), Qt.Key_Right)
    assert page.key(2).hasFocus()
    qtbot.keyClick(page.key(2), Qt.Key_Right)
    assert page.key(3).hasFocus()
    qtbot.keyClick(page.key(3), Qt.Key_Right)                    # 4 à 16 : INIT
    assert page.key(3).hasFocus()
    qtbot.keyClick(page.key(3), Qt.Key_Left)
    assert page.key(2).hasFocus()
    qtbot.keyClick(page.key(2), Qt.Key_Up)
    qtbot.keyClick(page.key(2), Qt.Key_Down)
    assert page.key(2).hasFocus()                                # ↑ ↓ sans effet


def test_enter_and_space_open(page, qtbot):
    requests = []
    page.concert_requested.connect(requests.append)
    page.activateWindow()
    page.key(1).setFocus()
    qtbot.waitUntil(page.key(1).hasFocus)
    qtbot.keyClick(page.key(1), Qt.Key_Return)
    qtbot.keyClick(page.key(1), Qt.Key_Space)
    assert requests == [1, 1]


def test_active_slots_reachable_by_tab_then_enter(page, qtbot):
    requests = []
    page.concert_requested.connect(requests.append)
    assert page.slot(1).focusPolicy() == Qt.TabFocus
    assert page.slot(9).focusPolicy() == Qt.NoFocus              # INIT
    page.activateWindow()
    page.slot(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.slot(2).hasFocus)
    assert page.key(2).highlighted                               # couplage aussi au focus
    qtbot.keyClick(page.slot(2), Qt.Key_Return)
    assert requests == [2]


# --- indicateur et état vide (arbitrage F) ---------------------------------------

def test_indicator_texts(page):
    assert page.indicator.isVisible() and not page.empty_state.isVisible()
    assert page.indicator.left.text() == "3 concerts à venir sur le dashboard"
    assert page.indicator.link.text() == "1 sans date · 1 passé · 1 annulé dans SETLISTS →"


def test_indicator_hidden_when_nothing_to_report(page):
    page.set_view(build_dashboard([concert(1, "A", date(2026, 12, 1))], NOW))
    assert not page.indicator.isVisible()


def test_empty_state_on_real_database(qtbot, qapp, tmp_path):
    """Base issue du classeur réel : état vide au 07/11/2026."""
    ud = tmp_path / "UserData"
    check_writable(ud)
    import_into_userdata(WORKBOOK, ud)
    win = MainWindow(ud, clock=lambda: datetime(2026, 11, 7, 12, 0))
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    page = win.main_page
    assert page.empty_state.isVisible() and not page.indicator.isVisible()
    assert page.empty_state.text.text() == \
        "Les 16 touches sont libres (INIT). 3 setlists passées sont conservées dans SETLISTS."
    assert page.empty_state.link.text() == "Ouvrir SETLISTS →"
    assert all(k.is_init for k in page.sequencer.keys)
    assert all(s.is_init for s in page.slot_grid.slots)


def test_setlists_link_inactive(page):
    page.set_view(None)
    link = page.empty_state.link
    assert link.text() == "Ouvrir SETLISTS →"
    assert link.focusPolicy() == Qt.NoFocus and not link.openExternalLinks()


def test_overflow_keys_not_shown_before_2_6(page):
    view = demo_view(extra=20)
    page.set_view(view)
    assert len(view.overflow_keys) > 0
    assert not any(k.is_init for k in page.sequencer.keys)        # 16 de base remplies
    assert page.indicator.left.text() == f"{view.upcoming_count} concerts à venir sur le dashboard"


# --- hauteur insuffisante : défilement vertical, jamais de chevauchement -------------

@pytest.mark.parametrize("view_factory", [demo_view, lambda: None])
def test_short_window_scrolls_without_overlap(qtbot, qapp, view_factory):
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.resize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
    win.show()
    qtbot.waitExposed(win)
    page = win.main_page
    page.set_view(view_factory())
    qtbot.wait(30)
    blocks = [w for w in (page.keys_title, page.sequencer, page.concerts_title, page.slot_grid,
                          page.indicator, page.empty_state) if w.isVisible()]
    spans = sorted((w.mapTo(page.content, w.rect().topLeft()).y(), w.height()) for w in blocks)
    for (top_a, h_a), (top_b, _) in zip(spans, spans[1:]):
        assert top_a + h_a <= top_b                              # aucun bloc ne recouvre le suivant
    bar = page.scroll.verticalScrollBar()
    assert bar.maximum() > 0                                     # le contenu dépasse : il défile
    assert page.scroll.horizontalScrollBar().maximum() == 0
    page.scroll.ensureWidgetVisible(page.slot(16))
    assert page.slot(16).visibleRegion().boundingRect().height() > 0


# --- ordre d'affichage : état vide au-dessus des 16 emplacements INIT ------------------

def _top(page, w):
    return w.mapTo(page.content, w.rect().topLeft()).y()


def _window(qtbot, width, height):
    win = MainWindow(None, clock=lambda: NOW)
    qtbot.addWidget(win)
    win.resize(width, height)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_empty_state_above_init_grid_and_fully_visible_at_1280x800(qtbot, qapp):
    win = _window(qtbot, 1280, 800)
    page = win.main_page
    page.set_view(None)
    qtbot.wait(30)
    order = [page.keys_title, page.sequencer, page.concerts_title, page.empty_state, page.slot_grid]
    tops = [_top(page, w) for w in order]
    assert tops == sorted(tops)
    assert _top(page, page.empty_state) + page.empty_state.height() <= _top(page, page.slot_grid)
    # message entier lisible sans défilement
    assert page.scroll.verticalScrollBar().value() == 0
    visible = page.empty_state.visibleRegion().boundingRect()
    assert visible.height() == page.empty_state.height()
    assert all(s.is_init for s in page.slot_grid.slots) and len(page.slot_grid.slots) == 16


def test_order_unchanged_when_concerts_present(qtbot, qapp):
    win = _window(qtbot, 1280, 800)
    page = win.main_page
    page.set_view(demo_view())
    qtbot.wait(30)
    assert not page.empty_state.isVisible()
    order = [page.keys_title, page.sequencer, page.concerts_title, page.slot_grid, page.indicator]
    tops = [_top(page, w) for w in order]
    assert tops == sorted(tops)
    assert _top(page, page.slot_grid) + page.slot_grid.height() <= _top(page, page.indicator)


@pytest.mark.parametrize("size", [(1024, 640), (1280, 800), (1440, 900)])
def test_empty_state_title_and_text_visible_without_scrolling(qtbot, qapp, size):
    win = _window(qtbot, *size)
    page = win.main_page
    page.set_view(None)
    qtbot.wait(30)
    for label in (page.empty_state.title, page.empty_state.text, page.empty_state.link):
        assert label.visibleRegion().boundingRect().height() == label.height()
