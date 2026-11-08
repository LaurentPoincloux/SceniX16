"""Banques de concerts : domaine et libellés (D44 à D48, incrément 2.6)."""

from datetime import date, datetime

import pytest

from scenix16.domain.dashboard import (
    BANK_SIZE, MIN_TABS, ConcertState, SortOrder, address, bank_label, bank_of_rank,
    build_dashboard, fallback_bank, occupied_bank_count, position_of_rank, step_bank, tab_count,
)
from scenix16.domain.models import ConcertSummary, SetlistStatus

NOW = datetime(2026, 11, 7, 20, 0)


def concert(i, name, d, venue=None, status=SetlistStatus.MAINTAINED):
    return ConcertSummary(i, name, d, venue, status, 10)


def many(n, start=date(2026, 12, 1)):
    return [concert(i, f"Concert {i:03d}", date.fromordinal(start.toordinal() + i))
            for i in range(1, n + 1)]


# --- nomenclature et adresses (D45) -------------------------------------------------

@pytest.mark.parametrize("index, label", [
    (0, "A"), (1, "B"), (7, "H"), (8, "I"), (25, "Z"), (26, "AA"), (27, "AB"),
    (51, "AZ"), (52, "BA"), (701, "ZZ"), (702, "AAA"),
])
def test_bank_labels_like_spreadsheet_columns(index, label):
    assert bank_label(index) == label


def test_bank_label_rejects_negative():
    with pytest.raises(ValueError):
        bank_label(-1)


@pytest.mark.parametrize("rank, bank, position, addr", [
    (1, 0, 1, "A01"), (16, 0, 16, "A16"), (17, 1, 1, "B01"), (35, 2, 3, "C03"),
    (16 * 26 + 12, 26, 12, "AA12"),
])
def test_rank_to_bank_position_and_address(rank, bank, position, addr):
    assert bank_of_rank(rank) == bank and position_of_rank(rank) == position
    assert address(bank, position) == addr


def test_key_address_and_group_identical_in_each_bank():
    view = build_dashboard(many(40), NOW)
    b1, b2 = view.bank(1), view.bank(2)
    assert [k.position for k in b1] == list(range(1, 17))
    assert [k.address for k in b1][:3] == ["B01", "B02", "B03"]
    assert [k.group for k in b1] == [k.group for k in view.bank(0)]   # couleurs par position
    assert [k.address for k in b2] == [f"C{p:02d}" for p in range(1, 9)]


# --- découpage (D44) ---------------------------------------------------------------------

@pytest.mark.parametrize("n, occupied, last_bank_size", [
    (0, 0, 0), (1, 1, 1), (16, 1, 16), (17, 2, 1), (32, 2, 16), (33, 3, 1),
    (128, 8, 16), (129, 9, 1), (417, 27, 1),
])
def test_banks_of_sixteen(n, occupied, last_bank_size):
    view = build_dashboard(many(n), NOW)
    assert view.occupied_banks == occupied == occupied_bank_count(n)
    if occupied:
        assert len(view.bank(occupied - 1)) == last_bank_size
        assert all(len(view.bank(i)) == BANK_SIZE for i in range(occupied - 1))
    assert view.bank(occupied) == ()
    assert sum(len(view.bank(i)) for i in range(occupied)) == n


@pytest.mark.parametrize("occupied, tabs", [(0, 8), (1, 8), (8, 8), (9, 9), (27, 27)])
def test_tabs_a_to_h_always_then_only_occupied(occupied, tabs):
    assert MIN_TABS == 8
    assert tab_count(occupied) == tabs


def test_bank_occupancy_and_bank_of_concert():
    view = build_dashboard(many(20), NOW)
    assert view.bank_occupancy() == [True, True] + [False] * 6
    assert view.bank_of_concert(1) == 0 and view.bank_of_concert(17) == 1
    assert view.bank_of_concert(999) is None


# --- tri et banques (D48) ------------------------------------------------------------------

def test_sort_applies_before_banks():
    concerts = many(20) + [concert(100, "Ce soir", date(2026, 11, 7))]
    asc = build_dashboard(concerts, NOW)
    desc = build_dashboard(concerts, NOW, SortOrder.NEWEST_FIRST)
    assert asc.bank(0)[0].concert.name == "Ce soir"                 # A = plus proches
    assert desc.bank(0)[0].concert.name == "Concert 020"           # A = plus lointains
    assert desc.bank(1)[-1].concert.name == "Ce soir"
    # états indépendants de la banque et du sens
    assert asc.bank(0)[0].state is desc.bank(1)[-1].state is ConcertState.TODAY
    states = {k.concert.id: k.state for k in asc.keys}
    assert all(states[k.concert.id] is k.state for k in desc.keys)


# --- Page précédente / suivante (D46) et repli (D47) ------------------------------------------

def test_step_bank_skips_empty_banks():
    occupied = [True, False, True, False, False, False, False, False]   # A, B vide, C
    assert step_bank(occupied, 0, +1) == 2                              # A → C
    assert step_bank(occupied, 2, -1) == 0                              # C → A
    assert step_bank(occupied, 2, +1) == 2                              # rien après C
    assert step_bank(occupied, 0, -1) == 0                              # rien avant A


def test_step_bank_contiguous_and_single():
    assert step_bank([True, True, True] + [False] * 5, 1, +1) == 2
    assert step_bank([True] + [False] * 7, 0, +1) == 0


@pytest.mark.parametrize("selected, occupied, expected", [
    (0, 3, 0), (2, 3, 2), (3, 3, 2), (5, 1, 0), (2, 0, 0), (0, 0, 0),
])
def test_fallback_bank(selected, occupied, expected):
    assert fallback_bank(selected, occupied) == expected


# --- libellés (D45, arbitrages 1 et 2 de 2.6) ---------------------------------------------

def test_preview_content_with_address():
    """D64 (remplace l'info-bulle de 2.6) : adresse, état, nom, lieu, date, compte à rebours, titres."""
    from scenix16.services import dashboard_service as ds
    view = build_dashboard([concert(100, "Le Kiosque", date(2026, 11, 21), "Le Kiosque\r\nChauvigny (86)")]
                           + many(19), NOW)
    p = ds.preview_content(view.bank(0)[0])
    assert (p.address, p.tag, p.emphasized) == ("A01", "PROCHAIN", True)
    assert p.name == "Le Kiosque" and p.venue == "Le Kiosque\nChauvigny (86)"
    assert (p.date, p.countdown, p.tracks) == ("samedi 21 novembre 2026", "J-14", "10 titres")
    q = ds.preview_content(view.bank(1)[2])
    assert q.address == "B03" and q.tag == "À VENIR" and not q.emphasized and q.venue == ""
    assert ds.preview_description(view.bank(1)[2]).startswith("B03, À venir. Concert ")


@pytest.mark.parametrize("d, text", [
    (date(2026, 11, 7), "samedi 7 novembre 2026"), (date(2026, 12, 1), "mardi 1er décembre 2026"),
    (date(2027, 8, 15), "dimanche 15 août 2027"),
])
def test_long_date_in_french(d, text):
    from scenix16.services import dashboard_service as ds
    assert ds.long_date(d) == text


def test_tracks_label():
    from scenix16.services import dashboard_service as ds
    assert [ds.tracks_label(n) for n in (0, 1, 2)] == ["0 titre", "1 titre", "2 titres"]


def test_accessible_names_with_address():
    from scenix16.services import dashboard_service as ds
    view = build_dashboard(many(18), NOW)
    k = view.bank(1)[1]
    assert ds.key_accessible_name(1, 2, k) == f"Touche B02 : {k.concert.name}"
    assert ds.slot_accessible_name(1, 2, k) == f"Emplacement B02 : {k.concert.name}"
    assert ds.key_accessible_name(1, 5, None) == "Touche B05 : libre (INIT)"
    assert ds.slot_accessible_name(0, 16, None) == "Emplacement A16 : libre (INIT)"


@pytest.mark.parametrize("index, count, name", [
    (1, 4, "Banque B : 4 concerts"), (0, 1, "Banque A : 1 concert"),
    (2, 0, "Banque C : vide"), (26, 16, "Banque AA : 16 concerts"),
])
def test_bank_accessible_names(index, count, name):
    from scenix16.services import dashboard_service as ds
    assert ds.bank_accessible_name(index, count) == name
