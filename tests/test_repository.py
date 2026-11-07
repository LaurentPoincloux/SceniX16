"""Lecture SQLite des résumés de concerts, et règles appliquées aux données réelles."""

from datetime import date, datetime
from pathlib import Path

import pytest

from scenix16.domain.dashboard import ConcertState, build_dashboard
from scenix16.domain.models import SetlistStatus
from scenix16.importer.service import import_into_userdata
from scenix16.storage import database
from scenix16.storage.repository import read_concert_summaries
from scenix16.storage.userdata import check_writable, database_path

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"


@pytest.fixture(scope="module")
def imported_db(tmp_path_factory):
    userdata = tmp_path_factory.mktemp("repo") / "UserData"
    check_writable(userdata)
    import_into_userdata(WORKBOOK, userdata)
    conn = database.connect(database_path(userdata))
    yield conn
    conn.close()


def test_reads_imported_concerts(imported_db):
    concerts = read_concert_summaries(imported_db)
    assert [(c.name, c.concert_date, c.status, c.track_count) for c in concerts] == [
        ("Antipode", date(2025, 11, 14), SetlistStatus.MAINTAINED, 23),
        ("Synthfinity 2", date(2026, 5, 16), SetlistStatus.MAINTAINED, 15),
        ("Le Kiosque", date(2026, 6, 21), SetlistStatus.MAINTAINED, 26),
    ]
    assert concerts[2].venue == "Le Kiosque \nChauvigny (86)"


def test_reads_undated_and_cancelled(tmp_path):
    conn = database.connect(tmp_path / "scenix16.db")
    with conn:
        conn.execute("INSERT INTO setlists(name) VALUES ('Nouvelle setlist')")
        conn.execute("INSERT INTO setlists(name, concert_date, status) "
                     "VALUES ('C', '2026-12-05', 'cancelled')")
    concerts = read_concert_summaries(conn)
    conn.close()
    assert concerts[0].concert_date is None and concerts[0].track_count == 0
    assert concerts[1].status is SetlistStatus.CANCELLED


def test_real_data_today_gives_empty_dashboard(imported_db):
    """Au 07/11/2026, les trois concerts du classeur sont passés (état vide validé)."""
    view = build_dashboard(read_concert_summaries(imported_db), datetime(2026, 11, 7, 12, 0))
    assert view.is_empty
    assert (view.counters.past, view.counters.cancelled, view.counters.undated) == (3, 0, 0)


def test_real_data_on_concert_night(imported_db):
    """Le soir du Kiosque, puis jusqu'à 5 h 59 le lendemain, il est « Aujourd'hui »."""
    concerts = read_concert_summaries(imported_db)
    for now in (datetime(2026, 6, 21, 20, 0), datetime(2026, 6, 22, 5, 59)):
        view = build_dashboard(concerts, now)
        assert [(k.number, k.concert.name, k.state) for k in view.keys] == [
            (1, "Le Kiosque", ConcertState.TODAY)]
        assert view.counters.past == 2
    assert build_dashboard(concerts, datetime(2026, 6, 22, 6, 0)).is_empty


def test_real_data_reading_does_not_modify_database(imported_db):
    before = imported_db.execute("SELECT total_changes()").fetchone()[0]
    read_concert_summaries(imported_db)
    assert imported_db.execute("SELECT total_changes()").fetchone()[0] == before
