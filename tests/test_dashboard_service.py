"""Chiffres de la barre supérieure et de la barre d'état."""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from scenix16.importer.service import import_into_userdata
from scenix16.services import dashboard_service as ds
from scenix16.storage import database
from scenix16.storage.userdata import check_writable, database_path

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"


@pytest.fixture(scope="module")
def userdata(tmp_path_factory):
    path = tmp_path_factory.mktemp("svc") / "UserData"
    check_writable(path)
    import_into_userdata(WORKBOOK, path)
    return path


def test_real_data_today(userdata):
    s = ds.load_summary(userdata, datetime(2026, 11, 7, 12, 0))
    assert (s.upcoming, s.past, s.track_count, s.setlist_count) == (0, 3, 37, 3)
    r = ds.info_readout(s, datetime(2026, 11, 7, 12, 0))
    assert (r.upcoming, r.upcoming_label, r.past, r.past_label) == ("0", "À VENIR", "3", "PASSÉS")
    assert ds.status_parts(s) == ["SceniX16", "37 titres au catalogue", "3 setlists"]


def test_real_data_on_kiosque_night(userdata):
    s = ds.load_summary(userdata, datetime(2026, 6, 21, 20, 0))
    r = ds.info_readout(s, datetime(2026, 6, 21, 20, 0))
    assert (r.upcoming, r.past, r.past_label) == ("1", "2", "PASSÉS")


def test_singular_forms():
    assert ds.plural(0, "passé", "passés") == "0 passé"
    assert ds.plural(1, "passé", "passés") == "1 passé"
    assert ds.plural(2, "passé", "passés") == "2 passés"
    assert ds.plural(1, "titre", "titres") == "1 titre"


def test_empty_or_missing_database(tmp_path):
    assert ds.load_summary(None, datetime(2026, 1, 1)) == ds.EMPTY
    assert ds.load_summary(tmp_path / "absent", datetime(2026, 1, 1)) == ds.EMPTY
    userdata = tmp_path / "UserData"
    check_writable(userdata)
    database.connect(database_path(userdata)).close()
    s = ds.load_summary(userdata, datetime(2026, 1, 1))
    r = ds.info_readout(s, datetime(2026, 1, 1))
    assert (r.upcoming, r.past, r.past_label) == ("0", "0", "PASSÉ")
    assert ds.status_parts(s) == ["SceniX16", "0 titre au catalogue", "0 setlist"]


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 11, 7, 12, 0), "07/11/2026"),
    (datetime(2026, 11, 8, 5, 59), "07/11/2026"),   # D60, Q12 : jour SceniX16, encore la veille
    (datetime(2026, 11, 8, 6, 0), "08/11/2026"),    # bascule à 6 h (D10)
    (datetime(2026, 11, 8, 0, 0), "07/11/2026"),
])
def test_date_label_is_scenix16_day(now, expected):
    assert ds.date_label(now) == expected


def test_info_readout_accessible_name_and_agreement(userdata):
    s = ds.load_summary(userdata, datetime(2026, 11, 7, 12, 0))
    assert ds.info_readout(s, datetime(2026, 11, 7, 12, 0)).accessible ==         "0 concert à venir, 3 passés, date de référence 7 novembre 2026"
    r = ds.info_readout(s, datetime(2026, 12, 2, 5, 59))           # encore le 1er décembre
    assert r.date == "01/12/2026" and r.accessible.endswith("date de référence 1er décembre 2026")


def test_info_readout_singular_and_plural():
    from scenix16.domain.dashboard import build_dashboard
    from scenix16.domain.models import ConcertSummary, SetlistStatus
    from datetime import date
    concerts = [ConcertSummary(i, f"C{i}", date(2026, 11, 7 + i), None, SetlistStatus.MAINTAINED, 0)
                for i in range(1, 24)]
    concerts += [ConcertSummary(100 + i, f"P{i}", date(2026, 10, i), None, SetlistStatus.MAINTAINED, 0)
                 for i in range(1, 7)]
    now = datetime(2026, 11, 7, 20, 0)
    s = ds.DashboardSummary(build_dashboard(concerts, now), 0, len(concerts))
    r = ds.info_readout(s, now)
    assert (r.upcoming, r.past, r.past_label) == ("23", "6", "PASSÉS")
    assert r.accessible == "23 concerts à venir, 6 passés, date de référence 7 novembre 2026"
    one = ds.DashboardSummary(build_dashboard(concerts[:1] + concerts[-1:], now), 0, 2)
    assert ds.info_readout(one, now).accessible.startswith("1 concert à venir, 1 passé,")
    assert ds.info_readout(one, now).past_label == "PASSÉ"


def test_day_month_year():
    from datetime import date
    assert ds.day_month_year(date(2026, 11, 7)) == "7 novembre 2026"
    assert ds.day_month_year(date(2026, 12, 1)) == "1er décembre 2026"


def test_reading_does_not_modify_database(userdata):
    path = database_path(userdata)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    ds.load_summary(userdata, datetime(2026, 11, 7, 12, 0))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


# --- libellés du bouton de tri (D12, incrément 2.5) ---------------------------

def test_sort_labels_d12():
    from scenix16.domain.dashboard import SortOrder
    assert ds.sort_label(SortOrder.OLDEST_FIRST) == "Plus ancien d'abord"
    assert ds.sort_label(SortOrder.NEWEST_FIRST) == "Plus récent d'abord"
    assert ds.other_order(SortOrder.OLDEST_FIRST) is SortOrder.NEWEST_FIRST
    assert ds.other_order(SortOrder.NEWEST_FIRST) is SortOrder.OLDEST_FIRST


def test_sort_accessible_name_describes_action():
    from scenix16.domain.dashboard import SortOrder
    assert ds.sort_accessible_name(SortOrder.OLDEST_FIRST) == \
        "Classement « Plus ancien d'abord ». Activer pour passer à « Plus récent d'abord »."
    assert ds.sort_accessible_name(SortOrder.NEWEST_FIRST) == \
        "Classement « Plus récent d'abord ». Activer pour passer à « Plus ancien d'abord »."
