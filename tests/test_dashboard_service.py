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
    assert ds.concerts_label(s) == "0 à venir · 3 passés"
    assert ds.status_parts(s) == ["SceniX16", "37 titres au catalogue", "3 setlists"]


def test_real_data_on_kiosque_night(userdata):
    s = ds.load_summary(userdata, datetime(2026, 6, 21, 20, 0))
    assert ds.concerts_label(s) == "1 à venir · 2 passés"


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
    assert ds.concerts_label(s) == "0 à venir · 0 passé"
    assert ds.status_parts(s) == ["SceniX16", "0 titre au catalogue", "0 setlist"]


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 11, 7, 12, 0), "07/11/2026"),
    (datetime(2026, 11, 8, 2, 30), "08/11/2026"),   # date calendaire entre 0 h et 6 h
])
def test_date_label_is_calendar_date(now, expected):
    assert ds.date_label(now) == expected


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
