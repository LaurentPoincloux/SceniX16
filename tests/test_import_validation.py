"""Fichiers non conformes refusés proprement ; jamais de données partielles."""

import shutil
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from scenix16.importer.excel import (
    EntryRow, SetlistSheet, TrackRow, WorkbookData, WorkbookFormatError, read_workbook,
)
from scenix16.importer.service import ImportFailed, ImportRefused, import_into, import_workbook
from scenix16.storage import database

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"


def assert_db_empty(path: Path):
    conn = database.connect(path)
    try:
        assert database.is_empty(conn)
        assert conn.execute("SELECT count(*) FROM setlist_entries").fetchone()[0] == 0
    finally:
        conn.close()


def make_xlsx(path: Path, build) -> Path:
    wb = openpyxl.Workbook()
    build(wb)
    wb.save(path)
    return path


def test_text_file_with_xlsx_extension_refused(tmp_path):
    fake = tmp_path / "notes.xlsx"
    fake.write_text("ceci n'est pas un classeur", encoding="utf-8")
    with pytest.raises(ImportRefused) as err:
        import_workbook(fake, tmp_path / "scenix16.db")
    assert "pas un classeur Excel" in str(err.value)
    assert_db_empty(tmp_path / "scenix16.db")


def test_empty_file_refused(tmp_path):
    empty = tmp_path / "vide.xlsx"
    empty.write_bytes(b"")
    with pytest.raises(ImportRefused):
        import_workbook(empty, tmp_path / "scenix16.db")


def test_missing_file_refused(tmp_path):
    with pytest.raises(WorkbookFormatError):
        read_workbook(tmp_path / "absent.xlsx")


def test_unrelated_workbook_refused(tmp_path):
    path = make_xlsx(tmp_path / "compta.xlsx", lambda wb: wb.active.append(["Date", "Montant"]))
    with pytest.raises(ImportRefused) as err:
        import_workbook(path, tmp_path / "scenix16.db")
    assert "feuille(s) absente(s)" in str(err.value)
    assert_db_empty(tmp_path / "scenix16.db")


def test_wrong_tracks_headers_refused(tmp_path):
    def build(wb):
        wb.active.title = "MAIN"
        wb.create_sheet("SETLISTS")["A1"] = "SHOWS ▾"
        tracks = wb.create_sheet("TRACKS")
        tracks.append(["Nom", "Tonalité", "", "Patch", "Statut"])
    path = make_xlsx(tmp_path / "presque.xlsx", build)
    with pytest.raises(ImportRefused) as err:
        import_workbook(path, tmp_path / "scenix16.db")
    assert "TRACKS!A1" in str(err.value)


def test_listed_sheet_without_expected_columns_refused(tmp_path):
    def build(wb):
        wb.active.title = "MAIN"
        setlists = wb.create_sheet("SETLISTS")
        setlists.append(["SHOWS ▾", "DATE ▾"])
        setlists.append(["SETLIST_X", None])
        wb.create_sheet("TRACKS").append(["Title", "Key", "   ", "Virus|TI", "Virus Status"])
        wb.create_sheet("SETLIST_X").append(["#", "Morceau"])
    path = make_xlsx(tmp_path / "x.xlsx", build)
    with pytest.raises(ImportRefused) as err:
        import_workbook(path, tmp_path / "scenix16.db")
    assert "SETLIST_X" in str(err.value)


def test_reference_workbook_still_valid(tmp_path):
    copy = shutil.copy(WORKBOOK, tmp_path / "ref.xlsx")
    assert len(read_workbook(Path(copy)).tracks) == 37


def test_failure_during_write_leaves_no_partial_data(tmp_path):
    """Une erreur au milieu de l'écriture annule toute la transaction."""
    data = WorkbookData(
        source_path=Path("x.xlsx"), sha256="0" * 64,
        tracks=[TrackRow(1, "A", None, None, None, None, 2)],
        setlists=[SetlistSheet("SETLIST_X", "X", "MAIN!D10", date(2026, 1, 1), None,
                               [EntryRow(1, "A", "SETLIST_X!B2"),
                                EntryRow(2, "INCONNU", "SETLIST_X!B3")])],
        findings=[],
    )
    db_path = tmp_path / "scenix16.db"
    conn = database.connect(db_path)
    with pytest.raises(KeyError):
        import_into(conn, data)
    conn.close()
    assert_db_empty(db_path)


def test_service_reports_technical_failure_without_data(tmp_path, monkeypatch):
    from scenix16.importer import service

    def broken(connection, data):
        with connection:
            connection.execute("INSERT INTO tracks(position, title) VALUES (1, 'A')")
            raise RuntimeError("panne simulée")

    monkeypatch.setattr(service, "import_into", broken)
    with pytest.raises(ImportFailed) as err:
        import_workbook(WORKBOOK, tmp_path / "scenix16.db")
    assert "aucune donnée n'a été enregistrée" in str(err.value)
    assert_db_empty(tmp_path / "scenix16.db")
