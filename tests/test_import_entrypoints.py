"""Points d'entrée de l'import : fonction commune et ligne de commande."""

from pathlib import Path

import pytest

from scenix16.importer import __main__ as cli
from scenix16.importer.service import ImportRefused, import_into_userdata
from scenix16.storage import userdata as ud
from scenix16.storage.instance_lock import InstanceLock

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"


def test_import_into_userdata_writes_db_and_report(tmp_path):
    userdata = tmp_path / "UserData"
    assert ud.check_writable(userdata).writable
    result = import_into_userdata(WORKBOOK, userdata)
    assert (result.tracks, result.setlists, result.entries) == (37, 3, 64)
    assert (userdata / "scenix16.db").is_file()
    assert result.report_path.parent == userdata / "logs"
    with pytest.raises(ImportRefused):
        import_into_userdata(WORKBOOK, userdata)


def test_cli_refuses_while_scenix16_is_open(tmp_path, monkeypatch, capsys):
    userdata = tmp_path / "UserData"
    monkeypatch.setattr(ud, "default_userdata_dir", lambda: userdata)
    ud.check_writable(userdata)
    with InstanceLock(userdata) as lock:
        assert lock.acquire()
        code = cli.main(["scenix16.importer", str(WORKBOOK)])
    assert code == cli.EXIT_ALREADY_RUNNING
    assert "fermez-le" in capsys.readouterr().out
    assert not (userdata / "scenix16.db").exists()


def test_cli_imports_and_releases_lock(tmp_path, monkeypatch):
    userdata = tmp_path / "UserData"
    monkeypatch.setattr(ud, "default_userdata_dir", lambda: userdata)
    assert cli.main(["scenix16.importer", str(WORKBOOK)]) == 0
    assert (userdata / "scenix16.db").is_file()
    with InstanceLock(userdata) as lock:
        assert lock.acquire()          # verrou bien relâché après l'import
