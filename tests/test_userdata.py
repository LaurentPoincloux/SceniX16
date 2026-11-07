"""UserData à côté de l'application et contrôle d'écriture (décision 2)."""

from pathlib import Path

from scenix16.storage import userdata as ud


def test_default_userdata_is_next_to_application():
    assert ud.default_userdata_dir() == ud.application_dir() / "UserData"


def test_application_dir_in_development_is_project_root():
    root = ud.application_dir()
    assert (root / "pyproject.toml").is_file()
    assert (root / "reference").is_dir()


def test_check_writable_creates_structure(tmp_path):
    target = tmp_path / "SceniX16" / "UserData"
    result = ud.check_writable(target)
    assert result.writable and result.error is None
    for name in ud.SUBFOLDERS:
        assert (target / name).is_dir()
    # l'essai d'écriture ne laisse aucun fichier
    assert not list(target.glob(".write-test-*"))


def test_check_writable_keeps_existing_files(tmp_path):
    target = tmp_path / "UserData"
    target.mkdir()
    existing = target / "scenix16.db"
    existing.write_bytes(b"donnees existantes")
    assert ud.check_writable(target).writable
    assert existing.read_bytes() == b"donnees existantes"


def test_check_writable_reports_failure_without_fallback(tmp_path):
    blocker = tmp_path / "pas-un-dossier"
    blocker.write_text("fichier")
    target = blocker / "UserData"  # impossible : le parent est un fichier
    result = ud.check_writable(target)
    assert not result.writable
    assert result.error
    assert result.path == target
    # aucun dossier de repli créé à côté
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pas-un-dossier"]


def test_database_path():
    assert ud.database_path(Path("X")) == Path("X") / "scenix16.db"
