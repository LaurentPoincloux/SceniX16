"""Paire sélectionnée et pulsation (D8, D11, D57, D63 — Design Book v0.45, incrément 2.6e).

La pulsation suit la paire sélectionnée (dernier clic ou navigation au clavier), et non le
concert du jour ; un clic ne donne jamais le focus clavier ni l'anneau orange ; la sélection
suit le concert lors d'un tri ou d'un changement de banque. Données temporaires uniquement.
"""

from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from scenix16.domain.dashboard import ConcertState, SortOrder, build_dashboard
from scenix16.domain.models import ConcertSummary, SetlistStatus
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.dashboard.page import initial_selection
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.theme.stylesheet import application_stylesheet

NOW = datetime(2026, 11, 7, 20, 0)


# --- présélection au lancement (fonction pure) -------------------------------------------------

def concerts(days, start=date(2026, 11, 7)):
    return [ConcertSummary(i + 1, f"Concert {i + 1:02d}", start + timedelta(days=d), None,
                           SetlistStatus.MAINTAINED, 0) for i, d in enumerate(days)]


def view(days, order=SortOrder.OLDEST_FIRST, now=NOW):
    return build_dashboard(concerts(days), now, order)


def test_preselect_today_in_bank_a():
    v = view([0, 3, 6])
    assert v.bank(0)[0].state is ConcertState.TODAY
    assert initial_selection(v.bank(0)) == 1


def test_preselect_next_when_no_concert_today():
    v = view([2, 5, 9])
    assert initial_selection(v.bank(0)) == 1 and v.bank(0)[0].state is ConcertState.NEXT


def test_preselect_today_even_if_not_first_key():
    v = view([0, 3, 6], order=SortOrder.NEWEST_FIRST)            # le jour en dernière touche
    today = [k for k in v.bank(0) if k.state is ConcertState.TODAY][0]
    assert today.position == 3 and initial_selection(v.bank(0)) == today.concert.id


def test_preselect_first_active_key_when_today_and_next_are_outside_bank_a():
    v = view(range(0, 40), order=SortOrder.NEWEST_FIRST)           # jour et prochain en banque C
    assert all(k.state is ConcertState.UPCOMING for k in v.bank(0))
    first = min(v.bank(0), key=lambda k: k.position)
    assert initial_selection(v.bank(0)) == first.concert.id


def test_no_preselection_when_bank_a_is_empty():
    assert initial_selection(()) is None


# --- dans la fenêtre ---------------------------------------------------------------------------

def make_userdata(tmp_path, days):
    folder = tmp_path / "UserData"
    check_writable(folder)
    conn = connect(database_path(folder))
    with conn:
        conn.executemany(
            "INSERT INTO setlists(name, concert_date, venue, status) VALUES (?,?,?,?)",
            [(f"Concert {i + 1:02d}", (date(2026, 11, 7) + timedelta(days=d)).isoformat(), f"Salle {i + 1}",
              "maintained") for i, d in enumerate(days)])
    conn.close()
    return folder


class RealPointerBlocker(QObject):
    """Écarte les événements d'entrée, de sortie et de survol envoyés par le vrai pointeur."""

    BLOCKED = (QEvent.Type.Enter, QEvent.Type.Leave, QEvent.Type.HoverEnter, QEvent.Type.HoverLeave,
               QEvent.Type.HoverMove)

    def eventFilter(self, obj, event):
        return event.type() in self.BLOCKED


def ignore_real_pointer(page):
    """2.9 : sur un écran réel, le pointeur de la souris peut survoler la fenêtre de test et
    ajouter une paire mise en évidence. Ces tests ne portent pas sur le survol réel : les
    événements du pointeur sont écartés sur les 16 touches et les 16 cartes, et underMouse()
    répond toujours faux. Le survol simulé (appel direct de _pair_source) reste possible.
    L'application elle-même n'est pas modifiée."""
    page._real_pointer_blocker = blocker = RealPointerBlocker(page)
    for n in range(1, 17):
        for widget in (page.key(n), page.slot(n)):
            widget.installEventFilter(blocker)
            widget.underMouse = lambda: False


def open_window(qtbot, qapp, folder, animations=True, isolate_pointer=False):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(folder, clock=lambda: NOW)
    win.main_page.animations = animations
    win.main_page.set_view(win.main_page.view)              # réapplique le réglage d'animation
    qtbot.addWidget(win)
    win.resize(1280, 800)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow)
    page = win.main_page
    if isolate_pointer:
        ignore_real_pointer(page)
    page.setFocus(Qt.OtherFocusReason)
    for n in range(1, 17):                                    # le vrai curseur ne doit pas interférer
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)
    qtbot.wait(30)
    return win


@pytest.fixture
def win(qtbot, qapp, tmp_path):
    return open_window(qtbot, qapp, make_userdata(tmp_path, range(0, 40, 2)),   # 20 concerts, jour en A01
                       isolate_pointer=True)


def pulsing(page):
    return [n for n in range(1, 17) if page.key(n).pulse_running() or page.slot(n).pulse_running()]


def pulsing_pairs(page):
    return [n for n in range(1, 17) if page.key(n).pulse_running() and page.slot(n).pulse_running()]


def emphasized(page):
    return [n for n in range(1, 17) if page.key(n).highlighted and page.slot(n).highlighted]


def colors(widget):
    image = widget.grab().toImage()
    return {QColor(image.pixel(x, y)).name() for x in range(image.width()) for y in range(image.height())}


def click(qtbot, widget):
    rect = widget.body_rect() if hasattr(widget, "body_rect") else widget.card_rect()
    qtbot.mouseClick(widget, Qt.LeftButton, pos=rect.center().toPoint())
    win = widget.window()
    if win.pages.currentWidget() is win.sheet_page:           # le clic ouvre la fiche (2.7) : retour
        win.show_main()                                       # sur CONCERTS, où la pulsation est visible (2.8c)
    page = win.main_page
    for n in range(1, 17):                                    # la souris repart (survol simulé)
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)


def test_launch_preselects_today_and_only_it_pulses(win):
    page = win.main_page
    assert page.bank == 0 and page.selected_concert == page.slot(1).key.concert.id
    assert page.slot(1).key.state is ConcertState.TODAY
    assert pulsing_pairs(page) == [1] and pulsing(page) == [1]
    assert emphasized(page) == [1]


def test_click_on_key_selects_pair_without_focus_ring(win, qtbot):
    page = win.main_page
    requests = []
    page.concert_requested.connect(requests.append)
    click(qtbot, page.key(2))
    assert pulsing(page) == [2] and emphasized(page) == [2]           # A02 et sa carte, seuls
    assert not page.key(2).hasFocus() and not page.slot(2).hasFocus()
    assert t.BRAND.lower() not in colors(page.key(2))                 # pas d'anneau orange au clic
    assert requests == [page.slot(2).key.concert.id]                  # D8 : demande d'ouverture
    assert not page.preview_visible()                                 # D64 : pas d'aperçu au clic
    click(qtbot, page.key(5))
    assert pulsing(page) == [5] and emphasized(page) == [5]


def test_click_on_card_has_same_effect_as_key(win, qtbot):
    page = win.main_page
    requests = []
    page.concert_requested.connect(requests.append)
    click(qtbot, page.slot(7))
    assert pulsing(page) == [7] and emphasized(page) == [7]
    assert not page.slot(7).hasFocus() and not page.key(7).hasFocus()
    assert requests == [page.slot(7).key.concert.id]
    click(qtbot, page.key(3))
    assert pulsing(page) == [3] and requests[-1] == page.slot(3).key.concert.id


def card_border(slot):
    image = slot.grab().toImage()
    r = image.devicePixelRatio()
    c = slot.card_rect()
    return QColor(image.pixel(round((c.left() + 1) * r), round(c.center().y() * r))).name()


def test_today_card_has_no_orange_border_selected_or_not(win, qtbot):
    """D11, D63 (v0.46) : plus de bordure orange « Aujourd'hui » ; libellé, « Ce soir » et point cerclé gardés."""
    page = win.main_page
    today = page.slot(1)
    assert today.key.state is ConcertState.TODAY
    assert today.tag_text() == "AUJOURD'HUI" and today.foot_text() == "Ce soir"
    assert page.key(1).led.name == "HALO"                                   # point cerclé (D11)
    click(qtbot, page.key(4))                                               # A01 non sélectionnée
    assert card_border(today) != t.BRAND.lower()
    assert card_border(today) == card_border(page.slot(6))                  # bordure d'une carte au repos
    assert not page.key(1).pulse_running() and not today.highlighted
    click(qtbot, today)                                                     # A01 sélectionnée
    assert card_border(today) != t.BRAND.lower()
    assert today.highlighted and pulsing(page) == [1]


def test_selected_today_card_looks_like_any_selected_card(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(1))
    today_border = card_border(page.slot(1))
    click(qtbot, page.key(3))
    assert card_border(page.slot(3)) == today_border                         # même mise en évidence


def test_next_card_keeps_its_orange_border(qtbot, qapp, tmp_path):
    folder = make_userdata(tmp_path, range(0, 40, 2))
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(folder, clock=lambda: datetime(2026, 11, 8, 10, 0))   # le concert du 07/11 est passé
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    page = win.main_page
    assert page.slot(1).key.state is ConcertState.NEXT
    assert card_border(page.slot(1)) == t.BRAND.lower()                    # « Prochain » : inchangé
    assert page.slot(1).tag_text() == "PROCHAIN"


def test_hover_never_changes_selection_or_pulse(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(3))
    page._pair_source(9, "key-hover", True)
    assert pulsing(page) == [3] and page.is_emphasized(9) and page.is_emphasized(3)
    page._pair_source(9, "key-hover", False)
    page._pair_source(11, "slot-hover", True)
    page._pair_source(11, "slot-hover", False)
    assert pulsing(page) == [3] and emphasized(page) == [3]


def test_keyboard_navigation_moves_selection_and_ring(win, qtbot):
    page = win.main_page
    page.key(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.key(2).hasFocus)
    assert pulsing(page) == [2] and t.BRAND.lower() in colors(page.key(2))   # anneau au clavier
    qtbot.keyClick(page.key(2), Qt.Key_Right)
    qtbot.waitUntil(page.key(3).hasFocus)
    assert pulsing(page) == [3] and emphasized(page) == [3]
    page.slot(6).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.slot(6).hasFocus)
    assert pulsing(page) == [6]


def test_selection_stays_when_focus_leaves_keys(win, qtbot):
    page = win.main_page
    page.key(4).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.key(4).hasFocus)
    page.sort_button.setFocus(Qt.TabFocusReason)                      # vers le bouton de tri
    qtbot.waitUntil(page.sort_button.hasFocus)
    assert pulsing(page) == [4] and emphasized(page) == [4]
    page.bank_tabs.tab(0).setFocus(Qt.TabFocusReason)                 # vers les banques
    assert pulsing(page) == [4]


def test_selection_follows_concert_when_sorting(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(2))
    chosen = page.selected_concert
    win.toggle_sort()                                                 # « plus récent d'abord »
    qtbot.wait(50)
    assert page.selected_concert == chosen
    position = page.selected_position()
    if position is None:                                              # concert passé dans une autre banque
        assert pulsing(page) == []
        page.show_concert_bank(chosen)
        position = page.selected_position()
    assert page.slot(position).key.concert.id == chosen and pulsing(page) == [position]


def test_selection_follows_concert_across_banks(win, qtbot):
    page = win.main_page
    click(qtbot, page.key(5))
    chosen = page.selected_concert
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)            # banque B à la souris
    assert page.bank == 1 and pulsing(page) == [] and emphasized(page) == []
    assert page.selected_concert == chosen                            # la sélection reste sur son concert
    qtbot.mouseClick(page.bank_tabs.tab(0), Qt.LeftButton)
    assert page.bank == 0 and pulsing(page) == [5]


def test_page_down_with_keyboard_moves_selection_to_new_bank(win, qtbot):
    page = win.main_page
    page.key(1).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.key(1).hasFocus)
    qtbot.keyClick(page.key(1), Qt.Key_PageDown)
    assert page.bank == 1 and page.key(1).hasFocus()
    assert page.selected_concert == page.slot(1).key.concert.id and pulsing(page) == [1]


def test_selection_dropped_when_concert_leaves_dashboard(qtbot, qapp, tmp_path):
    folder = make_userdata(tmp_path, [0, 2, 4])
    win = open_window(qtbot, qapp, folder, isolate_pointer=True)
    page = win.main_page
    click(qtbot, page.key(2))
    chosen = page.selected_concert
    conn = connect(database_path(folder))
    with conn:
        conn.execute("UPDATE setlists SET status = 'cancelled' WHERE id = ?", (chosen,))
    conn.close()
    win.refresh()
    assert page.selected_concert is None and pulsing(page) == []


def test_reduced_animations_keep_selection_visible_without_pulse(qtbot, qapp, tmp_path):
    win = open_window(qtbot, qapp, make_userdata(tmp_path, range(0, 20, 2)), animations=False,
                      isolate_pointer=True)
    page = win.main_page
    click(qtbot, page.key(3))
    assert pulsing(page) == [] and emphasized(page) == [3]            # mise en évidence seule


def test_empty_dashboard_has_no_selection(qtbot, qapp, tmp_path):
    win = open_window(qtbot, qapp, make_userdata(tmp_path, []), isolate_pointer=True)
    page = win.main_page
    assert page.selected_concert is None and pulsing(page) == [] and emphasized(page) == []
    assert QApplication.focusWidget() is not page.key(1)


def test_real_pointer_events_are_ignored_in_these_tests(win, qapp):
    """L'isolement du pointeur (2.9) : un survol réel n'ajoute aucune paire mise en évidence."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent
    page = win.main_page
    qapp.sendEvent(page.slot(13), QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    qapp.sendEvent(page.key(9), QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert emphasized(page) == [1] and not page.is_highlighted(13) and not page.is_highlighted(9)
    page._pair_source(9, "key-hover", True)                         # survol simulé : toujours possible
    assert page.is_highlighted(9)
    page._pair_source(9, "key-hover", False)
