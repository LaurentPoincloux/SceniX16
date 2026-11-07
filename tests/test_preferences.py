"""Préférences utilisateur : sens de tri (D1, D7), arbitrage 4 de l'incrément 2.5."""

import json
from datetime import datetime

import pytest

from scenix16.domain.dashboard import DEFAULT_SORT, SortOrder
from scenix16.storage import preferences as prefs

NOW = datetime(2026, 11, 7, 20, 30, 15)


def clock():
    return NOW


@pytest.fixture
def ud(tmp_path):
    folder = tmp_path / "UserData"
    folder.mkdir()
    return folder


def test_default_when_no_userdata_or_no_file(ud):
    assert DEFAULT_SORT is SortOrder.OLDEST_FIRST
    assert prefs.load_sort_order(None) is DEFAULT_SORT
    assert prefs.load_sort_order(ud) is DEFAULT_SORT
    assert not prefs.settings_path(ud).exists()        # la lecture ne crée rien


def test_round_trip(ud):
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST)
    assert prefs.load_sort_order(ud) is SortOrder.NEWEST_FIRST
    data = json.loads(prefs.settings_path(ud).read_text(encoding="utf-8"))
    assert data == {"version": 1, "concerts_sort_order": "newest_first"}
    assert prefs.save_sort_order(ud, SortOrder.OLDEST_FIRST)
    assert prefs.load_sort_order(ud) is SortOrder.OLDEST_FIRST


def test_unknown_keys_are_kept(ud):
    prefs.settings_path(ud).write_text('{"future": {"a": 1}, "version": 1}', encoding="utf-8")
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST)
    data = json.loads(prefs.settings_path(ud).read_text(encoding="utf-8"))
    assert data["future"] == {"a": 1} and data["concerts_sort_order"] == "newest_first"


@pytest.mark.parametrize("content", ['{"concerts_sort_order": "sideways"}',
                                     '{"concerts_sort_order": 3}', '{"version": 1}'])
def test_unknown_value_falls_back_without_renaming(ud, content):
    prefs.settings_path(ud).write_text(content, encoding="utf-8")
    assert prefs.load_sort_order(ud) is DEFAULT_SORT
    assert prefs.settings_path(ud).read_text(encoding="utf-8") == content


@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b"\xff\xfe\x00garbage", b""])
def test_unreadable_file_is_renamed_with_timestamp(ud, content):
    prefs.settings_path(ud).write_bytes(content)
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert not prefs.settings_path(ud).exists()
    renamed = ud / "settings.corrupt-20261107-203015.json"
    assert renamed.read_bytes() == content                 # contenu conservé tel quel


def test_corrupt_rename_never_overwrites(ud):
    existing = ud / "settings.corrupt-20261107-203015.json"
    existing.write_text("ancien", encoding="utf-8")
    prefs.settings_path(ud).write_text("{abîmé", encoding="utf-8")
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert existing.read_text(encoding="utf-8") == "ancien"
    assert (ud / "settings.corrupt-20261107-203015-2.json").read_text(encoding="utf-8") == "{abîmé"


def test_rename_failure_keeps_default(ud, monkeypatch):
    prefs.settings_path(ud).write_text("{abîmé", encoding="utf-8")

    def refuse(self, target):
        raise PermissionError("verrouillé")
    monkeypatch.setattr(type(prefs.settings_path(ud)), "rename", refuse)
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert prefs.settings_path(ud).exists()                # laissé en place, aucune erreur


def test_save_after_corrupt_file_writes_clean_file(ud):
    prefs.settings_path(ud).write_text("{abîmé", encoding="utf-8")
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST, clock)
    assert prefs.load_sort_order(ud) is SortOrder.NEWEST_FIRST
    assert (ud / "settings.corrupt-20261107-203015.json").exists()


def test_write_failure_returns_false_without_exception(tmp_path):
    missing = tmp_path / "absent"                           # dossier inexistant : écriture impossible
    assert prefs.save_sort_order(missing, SortOrder.NEWEST_FIRST) is False
    assert prefs.save_sort_order(None, SortOrder.NEWEST_FIRST) is False


def test_replace_failure_leaves_no_temp_file(ud, monkeypatch):
    prefs.save_sort_order(ud, SortOrder.OLDEST_FIRST)

    def refuse(src, dst):
        raise PermissionError("verrouillé")
    monkeypatch.setattr(prefs.os, "replace", refuse)
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST) is False
    assert sorted(p.name for p in ud.iterdir()) == ["settings.json"]
    assert prefs.load_sort_order(ud) is SortOrder.OLDEST_FIRST   # ancien fichier intact


# --- corrections de la revue technique de 2.5 -------------------------------------

def test_bom_file_is_read_and_kept(ud):
    """Défaut 3 : un fichier valide avec BOM (Bloc-notes, PowerShell 5) n'est pas « corrompu »."""
    content = b'\xef\xbb\xbf{"version": 1, "concerts_sort_order": "newest_first"}'
    prefs.settings_path(ud).write_bytes(content)
    assert prefs.load_sort_order(ud, clock) is SortOrder.NEWEST_FIRST
    assert sorted(p.name for p in ud.iterdir()) == ["settings.json"]
    assert prefs.settings_path(ud).read_bytes() == content


def test_bom_file_rewritten_with_its_keys(ud):
    prefs.settings_path(ud).write_bytes(b'\xef\xbb\xbf{"version": 1, "autre": 7}')
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST, clock)
    data = json.loads(prefs.settings_path(ud).read_text(encoding="utf-8"))
    assert data == {"version": 1, "autre": 7, "concerts_sort_order": "newest_first"}


def test_excessive_nesting_is_treated_as_unreadable(ud):
    """Défaut 2 : une imbrication pathologique ne lève plus d'erreur de récursion."""
    content = "[" * 100_000
    prefs.settings_path(ud).write_text(content, encoding="utf-8")
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert not prefs.settings_path(ud).exists()
    assert (ud / "settings.corrupt-20261107-203015.json").read_text(encoding="utf-8") == content
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST, clock)


@pytest.mark.parametrize("version", [2, 99])
def test_newer_version_is_never_rewritten(ud, version):
    """Amélioration 5 : défaut pour la session, fichier préservé octet pour octet."""
    content = json.dumps({"version": version, "concerts_sort_order": "newest_first", "x": 1}).encode()
    prefs.settings_path(ud).write_bytes(content)
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert prefs.save_sort_order(ud, SortOrder.NEWEST_FIRST, clock) is False
    assert prefs.settings_path(ud).read_bytes() == content
    assert sorted(p.name for p in ud.iterdir()) == ["settings.json"]


@pytest.mark.parametrize("version", [1, 0, "2", True, None])
def test_supported_or_unusual_version_is_not_newer(ud, version):
    prefs.settings_path(ud).write_text(
        json.dumps({"version": version, "concerts_sort_order": "newest_first"}), encoding="utf-8")
    assert prefs.load_sort_order(ud, clock) is SortOrder.NEWEST_FIRST


def test_access_denied_is_distinct_from_corrupt(ud, monkeypatch):
    """Amélioration 6 : accès refusé = ni renommé, ni écrasé, clés inconnues préservées."""
    content = b'{"version": 1, "garder": true, "concerts_sort_order": "newest_first"}'
    path = prefs.settings_path(ud)
    path.write_bytes(content)
    real = type(path).read_bytes

    def denied(self):
        if self.name == prefs.SETTINGS_FILENAME:
            raise PermissionError("accès refusé")
        return real(self)
    monkeypatch.setattr(type(path), "read_bytes", denied)
    assert prefs.load_sort_order(ud, clock) is DEFAULT_SORT
    assert prefs.save_sort_order(ud, SortOrder.OLDEST_FIRST, clock) is False
    monkeypatch.undo()
    assert path.read_bytes() == content
    assert sorted(p.name for p in ud.iterdir()) == ["settings.json"]
