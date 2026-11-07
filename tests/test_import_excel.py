"""Fidélité et intégrité de l'import du classeur de référence."""

import hashlib
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from scenix16.importer.excel import read_workbook
from scenix16.importer.service import ImportRefused, import_workbook
from scenix16.storage import database

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"
WORKBOOK_SHA256 = "775f9b54ca16ac0f51d897f260f8ad4b037d9f3423b65db6ccc9627eb124a464"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def data():
    return read_workbook(WORKBOOK)


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    base = tmp_path_factory.mktemp("import")
    result = import_workbook(WORKBOOK, base / "scenix16.db", base / "logs")
    conn = sqlite3.connect(base / "scenix16.db")
    conn.row_factory = sqlite3.Row
    yield result, conn, base
    conn.close()


def findings_by_code(data, code):
    return [f for f in data.findings if f.code == code]


# --- Classeur original intact ----------------------------------------------

def test_workbook_is_the_reference_file():
    assert sha256(WORKBOOK) == WORKBOOK_SHA256


def test_workbook_unchanged_after_read_and_import(imported):
    assert sha256(WORKBOOK) == WORKBOOK_SHA256
    assert imported[0].data.sha256 == WORKBOOK_SHA256


# --- Morceaux (TRACKS) -----------------------------------------------------

def test_track_count_and_order(data):
    assert len(data.tracks) == 37
    assert data.tracks[0].title == "NO SURRENDER (Intro)"
    assert data.tracks[-1].title == "MAD WORLD"
    assert [t.position for t in data.tracks] == list(range(1, 38))


@pytest.mark.parametrize("row, title, key, mk, virus, status", [
    (2, "NO SURRENDER (Intro)", "G#", "-/-", "-/-", "OFF"),
    (3, "MY DIGNITY", "F", "A62", "RAM-D 75", "ON"),
    (4, "(HAVE WE) LOST IT ALL", "F#/G#/A#", None, "RAM-D 72", "OFF"),
    (8, "CARGO DE NUIT", "A", "B63 (ARP) \nSync Int", "RAM-D 83", "OFF"),
    (9, "ONE", None, None, "RAM-D 47", "OFF"),
    (25, "SMALLTOWN BOY", "C", "A13", None, "OFF"),
    (27, "ENJOY THE SILENCE \n(BOOKHOUSE BOYS)", "C", None, "RAM-D 87", "ON"),
    (38, "MAD WORLD", "F#", None, "RAM-D96", "OFF"),
])
def test_track_values_verbatim(data, row, title, key, mk, virus, status):
    track = next(t for t in data.tracks if t.source_row == row)
    assert (track.title, track.key, track.mk, track.virus, track.virus_status) == \
        (title, key, mk, virus, status)


# --- Setlists ---------------------------------------------------------------

def test_setlists_listed_in_setlists_sheet(data):
    assert [s.sheet for s in data.setlists] == [
        "SETLIST_ANTIPODE", "SETLIST_SYNTHFINITY_2", "SETLIST_LE_KIOSQUE"]


def test_setlist_identity_from_main_k2_i2(data):
    got = [(s.name, s.name_source, s.concert_date, s.venue) for s in data.setlists]
    assert got == [
        ("Antipode", "MAIN!D10", date(2025, 11, 14), "Paris\nAntipode"),
        ("Synthfinity 2", "MAIN!H10", date(2026, 5, 16), "Alicante\nSynthfinity 2"),
        ("Le Kiosque", "MAIN!L10", date(2026, 6, 21), "Le Kiosque \nChauvigny (86)"),
    ]


def test_setlist_entries_order(data):
    counts = [len(s.entries) for s in data.setlists]
    assert counts == [23, 15, 26]
    antipode, synth, kiosque = data.setlists
    assert [e.title for e in antipode.entries[:3]] == [
        "NO SURRENDER (Intro)", "MY DIGNITY", "(HAVE WE) LOST IT ALL"]
    assert antipode.entries[-1].title == "DEVIL INSIDE"
    assert synth.entries[1].title == "TAKE IT AS MY PRIDE"
    assert kiosque.entries[0].title == "THE PASSENGER"
    assert kiosque.entries[-1].title == "MAD WORLD"
    assert kiosque.entries[0].source_cell == "SETLIST_LE_KIOSQUE!B2"


def test_template_sheet_not_imported(data):
    assert "SETLIST_INIT" not in [s.sheet for s in data.setlists]
    finding, = findings_by_code(data, "feuille-non-listee")
    assert "SETLIST_INIT" in finding.title


# --- Particularités recensées (plan technique) ------------------------------

def test_finding_venue_on_two_lines(data):
    finding, = findings_by_code(data, "lieu-deux-lignes")
    assert [c for c, _ in finding.cells] == [
        "SETLIST_ANTIPODE!I2", "SETLIST_SYNTHFINITY_2!I2", "SETLIST_LE_KIOSQUE!I2"]


def test_finding_zero_shown_in_empty_mk(data):
    mk = next(f for f in findings_by_code(data, "zero-affiche") if "MK" in f.title)
    cells = [c for c, _ in mk.cells]
    assert "SETLIST_ANTIPODE!D4" in cells and "SETLIST_ANTIPODE!D5" in cells
    assert all(c.split("!")[1].startswith("D") for c in cells)


def test_finding_shared_ram_d_51(data):
    finding, = [f for f in findings_by_code(data, "patch-partage") if "RAM-D 51" in f.title]
    assert finding.cells == [("TRACKS!D13", "LA VOIX DES OMBRES"), ("TRACKS!D26", "NATACHA")]


def test_finding_ram_d96_without_space(data):
    finding, = findings_by_code(data, "format-patch")
    assert finding.cells[0][0] == "TRACKS!D38"
    assert "MAD WORLD" in finding.cells[0][1]


def test_finding_mk_header_blank(data):
    finding, = findings_by_code(data, "entete-vide")
    assert finding.cells[0][0] == "TRACKS!C1"


def test_findings_never_alter_values(data):
    # les particularités sont signalées, les valeurs restent celles du classeur
    titles = {t.title for t in data.tracks}
    assert "ENJOY THE SILENCE \n(BOOKHOUSE BOYS)" in titles
    assert next(t for t in data.tracks if t.title == "MAD WORLD").virus == "RAM-D96"


# --- Base de données --------------------------------------------------------

def test_database_counts(imported):
    result, conn, _ = imported
    assert (result.tracks, result.setlists, result.entries) == (37, 3, 64)
    assert conn.execute("SELECT count(*) FROM tracks").fetchone()[0] == 37
    assert conn.execute("SELECT count(*) FROM setlists").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM setlist_entries").fetchone()[0] == 64
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_database_values_match_workbook(imported, data):
    _, conn, _ = imported
    rows = conn.execute("SELECT title, key, mk, virus, virus_status FROM tracks ORDER BY position").fetchall()
    assert [tuple(r) for r in rows] == [
        (t.title, t.key, t.mk, t.virus, t.virus_status) for t in data.tracks]
    setlists = conn.execute(
        "SELECT name, concert_date, venue, status FROM setlists ORDER BY id").fetchall()
    assert [tuple(r) for r in setlists] == [
        ("Antipode", "2025-11-14", "Paris\nAntipode", "maintained"),
        ("Synthfinity 2", "2026-05-16", "Alicante\nSynthfinity 2", "maintained"),
        ("Le Kiosque", "2026-06-21", "Le Kiosque \nChauvigny (86)", "maintained"),
    ]


def test_database_setlist_order(imported, data):
    _, conn, _ = imported
    for setlist_id, sheet in enumerate(data.setlists, start=1):
        titles = [r[0] for r in conn.execute(
            "SELECT t.title FROM setlist_entries e JOIN tracks t ON t.id = e.track_id "
            "WHERE e.setlist_id = ? ORDER BY e.position", (setlist_id,))]
        assert titles == [e.title for e in sheet.entries]


def test_database_records_source(imported):
    _, conn, _ = imported
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["import_sha256"] == WORKBOOK_SHA256
    assert meta["import_source"] == WORKBOOK.name


def test_report_written(imported):
    result, _, base = imported
    report = result.report_path.read_text(encoding="utf-8")
    assert result.report_path.parent == base / "logs"
    for expected in ("TRACKS!D13", "TRACKS!D26", "TRACKS!D38", "TRACKS!C1",
                     "SETLIST_ANTIPODE!I2", "SETLIST_ANTIPODE!D4", "SETLIST_INIT",
                     "aucune valeur n'a été corrigée"):
        assert expected in report, expected


def test_import_refused_when_database_not_empty(imported):
    _, _, base = imported
    with pytest.raises(ImportRefused):
        import_workbook(WORKBOOK, base / "scenix16.db")
    conn = database.connect(base / "scenix16.db")
    assert conn.execute("SELECT count(*) FROM tracks").fetchone()[0] == 37  # rien de doublé
    conn.close()
