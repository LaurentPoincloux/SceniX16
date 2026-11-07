"""Règles du dashboard : jour SceniX16, états, sélection, classement, compteurs.

Aucun test ne dépend de l'heure réelle : l'instant est toujours fourni.
"""

from datetime import date, datetime

import pytest

from scenix16.domain.dashboard import (
    BASE_KEYS, ConcertState, DEFAULT_SORT, SortOrder, build_dashboard,
    concert_state, countdown_days, key_group, scenix16_day,
)
from scenix16.domain.models import ConcertSummary, SetlistStatus

M, C = SetlistStatus.MAINTAINED, SetlistStatus.CANCELLED


def concert(id, name, day, status=M, tracks=10):
    return ConcertSummary(id, name, day, None, status, tracks)


def names(view):
    return [k.concert.name for k in view.keys]


# --- Jour SceniX16 (D2, D10) --------------------------------------------------

@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 6, 21, 6, 0), date(2026, 6, 21)),      # début du jour
    (datetime(2026, 6, 21, 21, 30), date(2026, 6, 21)),
    (datetime(2026, 6, 21, 23, 59, 59), date(2026, 6, 21)),
    (datetime(2026, 6, 22, 0, 0), date(2026, 6, 21)),      # minuit : encore le 21
    (datetime(2026, 6, 22, 5, 59, 59), date(2026, 6, 21)),  # dernière seconde du jour
    (datetime(2026, 6, 22, 6, 0), date(2026, 6, 22)),      # bascule à 6 h
    (datetime(2027, 1, 1, 2, 0), date(2026, 12, 31)),      # changement d'année
])
def test_scenix16_day_switches_at_six(now, expected):
    assert scenix16_day(now) == expected


def test_concert_stays_today_until_5h59_next_day():
    kiosque = concert(3, "Le Kiosque", date(2026, 6, 21))
    for now in (datetime(2026, 6, 21, 20, 0), datetime(2026, 6, 22, 5, 59)):
        view = build_dashboard([kiosque], now)
        assert names(view) == ["Le Kiosque"]
        assert view.keys[0].state is ConcertState.TODAY
        assert view.keys[0].countdown == 0


def test_concert_becomes_past_at_6h_next_day():
    kiosque = concert(3, "Le Kiosque", date(2026, 6, 21))
    view = build_dashboard([kiosque], datetime(2026, 6, 22, 6, 0))
    assert view.is_empty
    assert view.counters.past == 1


def test_concert_of_the_day_before_6h_is_still_tomorrow():
    """À 5 h du matin, le jour SceniX16 est encore la veille : J-1."""
    early = concert(1, "Matinale", date(2026, 6, 21))
    view = build_dashboard([early], datetime(2026, 6, 21, 5, 0))
    assert view.keys[0].state is ConcertState.NEXT
    assert view.keys[0].countdown == 1


# --- États (D4, D5, D11) -----------------------------------------------------

def test_states():
    day = date(2026, 11, 7)
    nxt = date(2026, 11, 19)
    assert concert_state(concert(1, "A", None), day, nxt) is ConcertState.UNDATED
    assert concert_state(concert(1, "A", date(2026, 12, 1), C), day, nxt) is ConcertState.CANCELLED
    assert concert_state(concert(1, "A", date(2026, 1, 1), C), day, nxt) is ConcertState.CANCELLED
    assert concert_state(concert(1, "A", date(2026, 11, 6)), day, nxt) is ConcertState.PAST
    assert concert_state(concert(1, "A", day), day, nxt) is ConcertState.TODAY
    assert concert_state(concert(1, "A", nxt), day, nxt) is ConcertState.NEXT
    assert concert_state(concert(1, "A", date(2026, 12, 17)), day, nxt) is ConcertState.UPCOMING


def test_undated_cancelled_is_still_undated():
    """D5 : une setlist sans date n'est jamais considérée comme annulée."""
    assert concert_state(concert(1, "A", None, C), date(2026, 1, 1), None) is ConcertState.UNDATED


def test_next_is_the_earliest_maintained_upcoming_date():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([
        concert(1, "Annulé tôt", date(2026, 11, 10), C),
        concert(2, "B", date(2026, 11, 19)),
        concert(3, "D", date(2026, 12, 17)),
    ], now)
    assert [(k.concert.name, k.state) for k in view.keys] == [
        ("B", ConcertState.NEXT), ("D", ConcertState.UPCOMING)]


def test_today_takes_precedence_over_next():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(1, "Ce soir", date(2026, 11, 7)),
                            concert(2, "Plus tard", date(2026, 11, 19))], now)
    assert [k.state for k in view.keys] == [ConcertState.TODAY, ConcertState.UPCOMING]


def test_several_concerts_on_next_date_are_all_next():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(1, "Y", date(2026, 11, 19)),
                            concert(2, "X", date(2026, 11, 19))], now)
    assert {k.state for k in view.keys} == {ConcertState.NEXT}


# --- Sélection du dashboard (D2, D4, D5) -------------------------------------

def test_only_maintained_dated_today_or_later_get_keys():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([
        concert(1, "Antipode", date(2025, 11, 14)),          # passé
        concert(2, "Annulé", date(2026, 12, 5), C),         # annulé à venir
        concert(3, "Nouvelle setlist", None),               # sans date
        concert(4, "A", date(2026, 11, 7)),                 # aujourd'hui
        concert(5, "B", date(2026, 11, 19)),                # à venir
    ], now)
    assert names(view) == ["A", "B"]
    assert view.counters.past == 1
    assert view.counters.cancelled == 1
    assert view.counters.undated == 1


def test_counters_count_all_cancelled_past_or_future():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(1, "C1", date(2025, 1, 1), C),
                            concert(2, "C2", date(2027, 1, 1), C)], now)
    assert view.counters.cancelled == 2 and view.counters.past == 0


def test_empty_dashboard():
    view = build_dashboard([], datetime(2026, 11, 7, 12, 0))
    assert view.is_empty and view.free_slots == BASE_KEYS
    assert view.counters.past == view.counters.cancelled == view.counters.undated == 0


# --- Classement (D1, D6, D7) --------------------------------------------------

def test_default_sort_is_oldest_first():
    assert DEFAULT_SORT is SortOrder.OLDEST_FIRST
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(1, "Loin", date(2027, 3, 1)),
                            concert(2, "Proche", date(2026, 11, 20))], now)
    assert names(view) == ["Proche", "Loin"]
    assert view.keys[0].number == 1


def test_newest_first_puts_furthest_on_key_1():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(1, "Proche", date(2026, 11, 20)),
                            concert(2, "Loin", date(2027, 3, 1))], now, SortOrder.NEWEST_FIRST)
    assert names(view) == ["Loin", "Proche"]
    assert view.order is SortOrder.NEWEST_FIRST


def test_same_date_alphabetical_case_insensitive_in_both_orders():
    now = datetime(2026, 11, 7, 12, 0)
    same = date(2026, 12, 1)
    concerts = [concert(1, "zénith", same), concert(2, "Arena", same),
                concert(3, "le Kiosque", same), concert(4, "Bataclan", date(2026, 12, 2))]
    asc = build_dashboard(concerts, now, SortOrder.OLDEST_FIRST)
    assert names(asc) == ["Arena", "le Kiosque", "zénith", "Bataclan"]
    desc = build_dashboard(concerts, now, SortOrder.NEWEST_FIRST)
    assert names(desc) == ["Bataclan", "Arena", "le Kiosque", "zénith"]


def test_same_date_alphabetical_ignores_accents():
    """« Élysée » se classe avec les E, pas après « Zénith » (D6)."""
    now = datetime(2026, 11, 7, 12, 0)
    same = date(2026, 12, 1)
    concerts = [concert(1, "Zénith", same), concert(2, "Élysée Montmartre", same),
                concert(3, "Arena", same), concert(4, "Eden", same), concert(5, "Ébène", same)]
    assert names(build_dashboard(concerts, now)) == [
        "Arena", "Ébène", "Eden", "Élysée Montmartre", "Zénith"]
    assert names(build_dashboard(concerts, now, SortOrder.NEWEST_FIRST)) == [
        "Arena", "Ébène", "Eden", "Élysée Montmartre", "Zénith"]


@pytest.mark.parametrize("names_in, expected", [
    (["été", "Ete", "ETE"], ["ETE", "Ete", "été"]),       # même base : le nom exact départage
    (["Ça va", "Cabaret", "Ciel"], ["Ça va", "Cabaret", "Ciel"]),
    (["Noël", "Noel", "Nœud"], ["Noel", "Noël", "Nœud"]),
])
def test_alphabetical_key_tiebreak_on_exact_name(names_in, expected):
    from scenix16.domain.dashboard import alphabetical_key
    assert sorted(names_in, key=alphabetical_key) == expected


def test_same_base_name_tiebreak_on_exact_name():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(3, "set", date(2026, 12, 1)),
                            concert(9, "Set", date(2026, 12, 1))], now)
    assert [k.concert.name for k in view.keys] == ["Set", "set"]


def test_identical_names_same_date_order_is_stable():
    now = datetime(2026, 11, 7, 12, 0)
    view = build_dashboard([concert(9, "Set", date(2026, 12, 1)),
                            concert(3, "Set", date(2026, 12, 1))], now)
    assert [k.concert.id for k in view.keys] == [3, 9]


# --- 16 touches de base, zone défilante (D22, D31, Q2) -----------------------

def many(n, start=date(2026, 12, 1)):
    return [concert(i, f"Concert {i:02d}", date.fromordinal(start.toordinal() + i))
            for i in range(1, n + 1)]


def test_sixteen_base_keys_and_overflow_continuous():
    view = build_dashboard(many(20), datetime(2026, 11, 7, 12, 0))
    assert len(view.base_keys) == 16 and len(view.overflow_keys) == 4
    assert [k.number for k in view.keys] == list(range(1, 21))
    assert view.overflow_keys[0].concert.name == "Concert 17"
    assert view.free_slots == 0
    assert {k.state for k in view.overflow_keys} <= {ConcertState.UPCOMING}


def test_overflow_follows_reverse_order():
    view = build_dashboard(many(20), datetime(2026, 11, 7, 12, 0), SortOrder.NEWEST_FIRST)
    assert view.keys[0].concert.name == "Concert 20"
    assert view.overflow_keys[-1].concert.name == "Concert 01"


def test_free_slots_when_fewer_than_sixteen():
    view = build_dashboard(many(3), datetime(2026, 11, 7, 12, 0))
    assert view.free_slots == 13


@pytest.mark.parametrize("number, group", [
    (1, 0), (4, 0), (5, 1), (8, 1), (9, 2), (12, 2), (13, 3), (16, 3),
    (17, 0), (20, 0), (21, 1), (32, 3), (33, 0),
])
def test_key_group_color_cycle(number, group):
    assert key_group(number) == group


# --- Compte à rebours ---------------------------------------------------------

def test_countdown():
    assert countdown_days(date(2026, 11, 19), date(2026, 11, 7)) == 12
    view = build_dashboard([concert(1, "B", date(2026, 11, 19))], datetime(2026, 11, 8, 3, 0))
    assert view.keys[0].countdown == 12        # à 3 h, le jour SceniX16 est encore le 7
