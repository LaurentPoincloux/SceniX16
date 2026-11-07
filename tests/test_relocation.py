"""Copie complète et sécurisée du dossier portable."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from scenix16.services import relocation
from scenix16.services.relocation import RelocationError, copy_portable_folder
from scenix16.storage import database
from scenix16.storage.instance_lock import InstanceLock


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


@pytest.fixture
def portable(tmp_path):
    """Faux dossier portable : exécutable, _internal, UserData avec base."""
    root = tmp_path / "source" / "SceniX16"
    (root / "_internal" / "PySide6").mkdir(parents=True)
    (root / "SceniX16.exe").write_bytes(b"MZ" + b"\x00" * 2048)
    (root / "_internal" / "python315.dll").write_bytes(b"dll" * 1000)
    (root / "_internal" / "PySide6" / "Qt6Core.dll").write_bytes(b"qt" * 1000)
    userdata = root / "UserData"
    (userdata / "media" / "band-logo").mkdir(parents=True)
    (userdata / "media" / "band-logo" / "logo.png").write_bytes(b"\x89PNG" + b"1" * 500)
    (userdata / "backups").mkdir()
    (userdata / "logs").mkdir()
    (userdata / "logs" / "import.md").write_text("rapport", encoding="utf-8")
    conn = database.connect(userdata / "scenix16.db")
    with conn:
        conn.execute("INSERT INTO tracks(position, title) VALUES (1, 'MY DIGNITY')")
        conn.execute("INSERT INTO setlists(name, concert_date) VALUES ('Le Kiosque', '2026-06-21')")
    conn.close()
    return root


def test_full_copy_and_original_untouched(portable, tmp_path):
    before = snapshot(portable)
    parent = tmp_path / "accessible"
    parent.mkdir()
    result = copy_portable_folder(portable, parent)
    assert result.destination == parent / "SceniX16"
    copied = snapshot(result.destination)
    # mêmes fichiers ; contenu identique hors base (copiée par SQLite)
    assert set(copied) == set(before)
    for name, digest in before.items():
        if not name.endswith("scenix16.db"):
            assert copied[name] == digest
    conn = sqlite3.connect(result.destination / "UserData" / "scenix16.db")
    assert conn.execute("SELECT title FROM tracks").fetchone()[0] == "MY DIGNITY"
    assert conn.execute("SELECT name FROM setlists").fetchone()[0] == "Le Kiosque"
    conn.close()
    assert snapshot(portable) == before  # original intact
    assert result.files == len(before)


def test_copy_while_database_open_and_locked(portable, tmp_path):
    """Situation réelle : l'application tourne (verrou tenu, base ouverte)."""
    userdata = portable / "UserData"
    lock = InstanceLock(userdata)
    assert lock.acquire()
    conn = database.connect(userdata / "scenix16.db")
    parent = tmp_path / "dest"
    parent.mkdir()
    try:
        result = copy_portable_folder(portable, parent)
    finally:
        conn.close()
        lock.release()
    assert not (result.destination / "UserData" / ".scenix16.lock").exists()
    assert (result.destination / "UserData" / "scenix16.db").is_file()


def test_existing_destination_refused_nothing_written(portable, tmp_path):
    parent = tmp_path / "dest"
    (parent / "SceniX16").mkdir(parents=True)
    (parent / "SceniX16" / "autre.txt").write_text("à garder")
    before = snapshot(parent)
    with pytest.raises(RelocationError) as err:
        copy_portable_folder(portable, parent)
    assert "existe déjà" in str(err.value)
    assert err.value.partial is None
    assert snapshot(parent) == before


def test_destination_inside_source_refused(portable):
    with pytest.raises(RelocationError):
        copy_portable_folder(portable, portable / "_internal")


def test_insufficient_space_refused_before_writing(portable, tmp_path, monkeypatch):
    parent = tmp_path / "dest"
    parent.mkdir()
    monkeypatch.setattr(relocation.shutil, "disk_usage",
                        lambda p: type("U", (), {"free": 1024})())
    with pytest.raises(RelocationError) as err:
        copy_portable_folder(portable, parent)
    assert "Espace libre insuffisant" in str(err.value)
    assert list(parent.iterdir()) == []


def test_failure_during_copy_keeps_original_and_reports_partial(portable, tmp_path, monkeypatch):
    before = snapshot(portable)
    parent = tmp_path / "dest"
    parent.mkdir()
    real_copy = relocation.shutil.copy2
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("disque retiré")
        return real_copy(src, dst)

    monkeypatch.setattr(relocation.shutil, "copy2", flaky)
    with pytest.raises(RelocationError) as err:
        copy_portable_folder(portable, parent)
    assert err.value.partial == (parent / "SceniX16").resolve()
    assert err.value.partial.exists()          # copie partielle signalée, non supprimée
    assert snapshot(portable) == before        # original intact


def test_corrupted_copy_detected(portable, tmp_path, monkeypatch):
    parent = tmp_path / "dest"
    parent.mkdir()
    real_copy = relocation.shutil.copy2

    def corrupt(src, dst):
        real_copy(src, dst)
        if Path(dst).name == "python315.dll":
            Path(dst).write_bytes(b"abime")

    monkeypatch.setattr(relocation.shutil, "copy2", corrupt)
    with pytest.raises(RelocationError) as err:
        copy_portable_folder(portable, parent)
    assert "différent" in str(err.value)
    assert err.value.partial is not None
