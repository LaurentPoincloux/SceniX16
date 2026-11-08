"""Bascule de journée en direct (incrément 2.8a — D73, complétée par D10, D60, D63, D69 ; Design Book v0.51).

La journée SceniX16 commence à 06:00. Minuterie au passage de 06:00, vérification périodique
(sortie de veille, horloge modifiée), recalcul du dashboard, de l'afficheur et de la barre d'état,
sélection conservée par concert, fiche ouverte conservée. Horloge simulée, données temporaires.
"""

from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from scenix16.domain.dashboard import ConcertState, next_day_switch, scenix16_day
from scenix16.ui.day_watch import CHECK_INTERVAL_MS, MIN_SWITCH_DELAY_MS, DayWatcher, ms_until_switch
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet
from test_dashboard_selection import make_userdata, pulsing


class Clock:
    """Horloge simulée : l'heure ne change que quand le test la règle."""

    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


EVENING = datetime(2026, 11, 7, 20, 0)              # concert 01 (le 07/11) est le concert du jour


# --- domaine : prochain passage de 06:00 ------------------------------------------------------------

@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 11, 8, 5, 59, 59), datetime(2026, 11, 8, 6, 0)),
    (datetime(2026, 11, 8, 6, 0), datetime(2026, 11, 9, 6, 0)),
    (datetime(2026, 11, 8, 6, 0, 1), datetime(2026, 11, 9, 6, 0)),
    (datetime(2026, 11, 7, 23, 59, 59), datetime(2026, 11, 8, 6, 0)),
    (datetime(2026, 11, 8, 0, 0), datetime(2026, 11, 8, 6, 0)),
    (datetime(2026, 12, 31, 7, 0), datetime(2027, 1, 1, 6, 0)),
    (datetime(2028, 2, 28, 12, 0), datetime(2028, 2, 29, 6, 0)),
])
def test_next_day_switch(now, expected):
    assert next_day_switch(now) == expected
    assert scenix16_day(expected) == scenix16_day(now) + timedelta(days=1)


def test_delay_until_switch():
    assert ms_until_switch(datetime(2026, 11, 8, 5, 59, 59)) == 1001          # jamais avant 06:00
    assert ms_until_switch(datetime(2026, 11, 8, 6, 0)) == 24 * 3600 * 1000 + 1
    assert ms_until_switch(datetime(2026, 11, 8, 5, 59, 59, 999_990)) == MIN_SWITCH_DELAY_MS


# --- surveillance du jour -----------------------------------------------------------------------------

@pytest.fixture
def watcher(qapp):
    clock = Clock(datetime(2026, 11, 8, 5, 59, 59))
    w = DayWatcher(clock)
    w.test_clock = clock
    yield w
    w.stop()


def emitted(qtbot, watcher):
    days = []
    watcher.day_changed.connect(days.append)
    return days


def test_timers_are_armed(watcher):
    assert watcher.switch_timer.isActive() and watcher.switch_timer.isSingleShot()
    assert watcher.switch_timer.timerType() == Qt.PreciseTimer
    assert watcher.switch_timer.interval() == 1001                            # 05:59:59 → 06:00
    assert watcher.check_timer.isActive() and watcher.check_timer.interval() == CHECK_INTERVAL_MS == 60_000


def test_just_before_at_and_after_six(watcher, qtbot):
    days = emitted(qtbot, watcher)
    assert not watcher.check() and days == []                                 # 05:59:59
    watcher.test_clock.now = datetime(2026, 11, 8, 6, 0)
    assert watcher.check() and days == [date(2026, 11, 8)]                    # 06:00:00
    watcher.test_clock.now = datetime(2026, 11, 8, 6, 0, 30)
    assert not watcher.check() and days == [date(2026, 11, 8)]                # après : une seule fois
    assert watcher.switch_timer.interval() == 24 * 3600 * 1000 - 30_000 + 1  # réarmée pour le 9 à 06:00


def test_midnight_does_not_switch(qapp, qtbot):
    clock = Clock(datetime(2026, 11, 7, 23, 59, 59))
    w = DayWatcher(clock)
    days = emitted(qtbot, w)
    for now in (datetime(2026, 11, 8, 0, 0), datetime(2026, 11, 8, 0, 0, 1), datetime(2026, 11, 8, 5, 59, 59)):
        clock.now = now
        assert not w.check()
    assert days == [] and w.day == date(2026, 11, 7)
    w.stop()


def test_wake_from_sleep_after_six(qapp, qtbot):
    clock = Clock(datetime(2026, 11, 7, 23, 0))
    w = DayWatcher(clock)
    days = emitted(qtbot, w)
    clock.now = datetime(2026, 11, 8, 9, 15)          # veille : aucune minuterie n'a progressé
    w.check_timer.setInterval(20)                     # première vérification périodique après le réveil
    qtbot.waitUntil(lambda: days == [date(2026, 11, 8)], timeout=2000)
    assert w.switch_timer.interval() == ms_until_switch(clock.now)            # 9 à 06:00
    w.stop()


def test_switch_timer_fires_at_six(qapp, qtbot):
    clock = Clock(datetime(2026, 11, 8, 5, 59, 59, 900_000))
    w = DayWatcher(clock)                             # minuterie de 101 ms
    clock.now = datetime(2026, 11, 8, 6, 0, 0, 1000)
    with qtbot.waitSignal(w.day_changed, timeout=2000) as blocker:
        pass
    assert blocker.args == [date(2026, 11, 8)]
    w.stop()


def test_timer_fired_early_rearms_without_switching(watcher, qtbot):
    days = emitted(qtbot, watcher)
    watcher.test_clock.now = datetime(2026, 11, 8, 5, 59, 59, 500_000)        # 0,5 s trop tôt
    watcher.switch_timer.timeout.emit()
    assert days == [] and watcher.switch_timer.interval() == 501


@pytest.mark.parametrize("jump, expected_days", [
    (datetime(2026, 11, 7, 22, 0), [date(2026, 11, 7)]),                      # horloge reculée d'un jour
    (datetime(2026, 11, 12, 10, 0), [date(2026, 11, 12)]),                    # avancée de plusieurs jours
    (datetime(2026, 11, 8, 15, 0), []),                                       # même jour : rien
])
def test_system_clock_change(qapp, qtbot, jump, expected_days):
    clock = Clock(datetime(2026, 11, 8, 7, 0))
    w = DayWatcher(clock)
    days = emitted(qtbot, w)
    clock.now = jump
    w.check()
    assert days == expected_days
    assert w.switch_timer.interval() == ms_until_switch(jump)                 # réarmée d'après la nouvelle heure
    w.stop()


# --- fenêtre : dashboard, afficheur, sélection, fiche ----------------------------------------------------

def open_at(qtbot, qapp, folder, now):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    clock = Clock(now)
    win = MainWindow(folder, clock=clock)
    win.test_clock = clock
    win.main_page.animations = True
    win.main_page.set_view(win.main_page.view)
    qtbot.addWidget(win)
    win.resize(1280, 800)
    win.show()
    qtbot.waitExposed(win)
    page = win.main_page
    for n in range(1, 17):                            # le vrai curseur ne doit pas interférer
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)
    return win


def switch_to(win, now):
    win.test_clock.now = now
    return win.day_watch.check()


@pytest.fixture
def folder(tmp_path):
    return make_userdata(tmp_path, range(20))         # concerts 01 à 20 du 07/11 au 26/11 : A complète, B01 à B04


@pytest.fixture
def win(qtbot, qapp, folder):
    window = open_at(qtbot, qapp, folder, EVENING)
    yield window
    window.day_watch.stop()


def concert_at(page, n):
    return page.slot(n).key.concert.id


def test_window_watches_the_day(win):
    assert isinstance(win.day_watch, DayWatcher) and win.day_watch.day == date(2026, 11, 7)
    assert win.day_watch.switch_timer.isActive() and win.day_watch.check_timer.isActive()


def test_dashboard_just_before_and_at_six(win):
    page = win.main_page
    assert not switch_to(win, datetime(2026, 11, 8, 5, 59, 59))
    assert concert_at(page, 1) == 1 and page.slot(1).key.state is ConcertState.TODAY
    assert win.top_bar.info.readout.date == "07/11/2026" and win.top_bar.info.readout.past == "0"
    assert switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert concert_at(page, 1) == 2 and page.slot(1).key.state is ConcertState.TODAY   # A01 : le 08/11
    assert page.view.key_of_concert(1) is None                                         # 01 est passé
    assert win.top_bar.info.readout.date == "08/11/2026"
    assert (win.top_bar.info.readout.upcoming, win.top_bar.info.readout.past) == ("19", "1")
    assert win.status_line.texts()[2] == "20 setlists"                                # barre d'état recalculée


def test_midnight_keeps_the_dashboard(win):
    before = [concert_at(win.main_page, n) for n in range(1, 17)]
    assert not switch_to(win, datetime(2026, 11, 8, 0, 0, 30))
    assert [concert_at(win.main_page, n) for n in range(1, 17)] == before
    assert win.top_bar.info.readout.date == "07/11/2026"


def test_no_refresh_without_day_change(win, monkeypatch):
    calls = []
    monkeypatch.setattr(win, "refresh", lambda *a, **k: calls.append(1))
    switch_to(win, datetime(2026, 11, 7, 23, 0))
    assert calls == []


def test_selection_follows_its_concert(win):
    page = win.main_page
    page.select_pair(5)                                                       # concert 05 en A05
    assert page.selected_concert == 5
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert page.selected_concert == 5 and page.selected_position() == 4       # même concert, A04
    assert pulsing(page) == [4]


def test_selection_fallback_when_selected_concert_becomes_past(win):
    page = win.main_page
    assert page.selected_concert == 1                                         # présélection : le concert du jour
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert page.selected_concert == 2 and page.selected_position() == 1       # D63 : nouveau concert du jour
    assert page.slot(1).key.state is ConcertState.TODAY and pulsing(page) == [1]


def test_displayed_bank_is_kept(win, qtbot):
    page = win.main_page
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)
    page.select_pair(2)                                                       # B02 : concert 18
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert page.bank == 1 and page.selected_concert == 18 and page.selected_position() == 1   # B01


def test_bank_fallback_when_displayed_bank_empties(qtbot, qapp, tmp_path):
    window = open_at(qtbot, qapp, make_userdata(tmp_path, range(17)), EVENING)    # B01 seul en banque B
    page = window.main_page
    qtbot.mouseClick(page.bank_tabs.tab(1), Qt.LeftButton)
    assert page.bank == 1
    switch_to(window, datetime(2026, 11, 8, 6, 0))
    assert page.bank == 0 and page.view.occupied_banks == 1                   # repli D47 : banque A
    window.day_watch.stop()


def test_clock_moved_back_restores_previous_day(win):
    page = win.main_page
    switch_to(win, datetime(2026, 11, 8, 7, 0))
    page.select_pair(3)                                                       # concert 04
    switch_to(win, datetime(2026, 11, 7, 21, 0))                              # horloge reculée
    assert concert_at(page, 1) == 1 and page.slot(1).key.state is ConcertState.TODAY
    assert page.selected_concert == 4 and page.selected_position() == 4
    assert win.top_bar.info.readout.date == "07/11/2026"


def test_wake_from_sleep_updates_window(win, qtbot):
    win.test_clock.now = datetime(2026, 11, 8, 9, 15)                         # réveil après 06:00
    win.day_watch.check_timer.setInterval(20)
    qtbot.waitUntil(lambda: win.top_bar.info.readout.date == "08/11/2026", timeout=2000)
    assert concert_at(win.main_page, 1) == 2


def on_sheet(win):
    return win.pages.currentWidget() is win.sheet_page


def test_open_sheet_stays_and_heading_is_updated(win):
    win.open_concert(5)
    card = win.sheet_page.card
    assert win.sheet_page.heading_label.text() == "Touche A05 · Consultation"
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert on_sheet(win) and win.sheet_page.sheet.id == 5                     # même concert, fiche ouverte
    assert win.sheet_page.card is card                                        # pas reconstruite
    assert win.sheet_page.heading_label.text() == "Touche A04 · Consultation"
    assert win.top_bar.info.readout.date == "08/11/2026"                      # afficheur à jour pendant la fiche
    assert win.rail.items["main"].active                                     # CONCERTS reste active
    win.sheet_page.back_button.click()
    page = win.main_page
    assert page.selected_concert == 5 and page.selected_position() == 4 and page.open_concert == 5
    assert page.key(4).selected and page.slot(4).selected


def test_open_sheet_of_concert_that_became_past(win):
    win.open_concert(1)                                                       # concert du jour, A01
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert on_sheet(win) and win.sheet_page.sheet.id == 1                     # ni perdu ni remplacé
    assert win.sheet_page.heading_label.text() == "Consultation"              # plus de touche
    win.sheet_page.back_button.click()
    page = win.main_page
    assert win.pages.currentWidget() is page
    assert page.open_concert is None and page.selected_concert == 2           # repli D63
    assert not any(page.key(n).selected for n in range(1, 17))


def test_open_sheet_kept_when_database_unreadable(win, monkeypatch):
    win.open_concert(5)
    from scenix16.services import concert_service
    monkeypatch.setattr(concert_service, "load_concert_sheet", lambda *a, **k: None)
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert on_sheet(win) and win.sheet_page.sheet.id == 5
    assert win.sheet_page.heading_label.text() == "Touche A05 · Consultation"


def test_other_concert_sheet_is_never_substituted(win):
    win.open_concert(5)
    other = win.sheet_page.sheet.__class__(**{**win.sheet_page.sheet.__dict__, "id": 6})
    assert not win.sheet_page.update_day_context(other)
    assert win.sheet_page.sheet.id == 5


def test_settings_page_stays_open(win):
    win.show_settings()
    switch_to(win, datetime(2026, 11, 8, 6, 0))
    assert win.pages.currentWidget() is win.settings_page
    assert win.top_bar.info.readout.date == "08/11/2026"
    win.show_main()
    assert concert_at(win.main_page, 1) == 2


def test_no_setting_for_switch_hour(win):
    texts = " ".join(w.text() for w in win.settings_page.findChildren(QLabel))
    assert "06:00" not in texts and "6 h" not in texts and "bascule" not in texts.lower()
