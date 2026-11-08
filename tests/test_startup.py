"""Séquence de démarrage : écriture, copie, instance unique, base."""

import pytest

from scenix16 import startup
from scenix16.startup import Choice


class FakeUI:
    def __init__(self, choices=(), parents=(), restart=True):
        self.choices = list(choices)
        self.parents = list(parents)
        self.restart = restart
        self.events = []

    def storage_problem(self, check, can_relocate):
        self.events.append(("problem", check.path, can_relocate))
        return self.choices.pop(0) if self.choices else Choice.QUIT

    def choose_parent_folder(self):
        self.events.append(("choose",))
        return self.parents.pop(0) if self.parents else None

    def copying(self, running):
        self.events.append(("copying", running))

    def relocation_failed(self, error):
        self.events.append(("failed", str(error), error.partial))

    def offer_restart(self, result):
        self.events.append(("restart?", result.destination))
        return self.restart

    def already_running(self, userdata):
        self.events.append(("running", userdata))


@pytest.fixture
def app_dir(tmp_path):
    root = tmp_path / "SceniX16"
    (root / "_internal").mkdir(parents=True)
    (root / "SceniX16.exe").write_bytes(b"MZ")
    return root


def unwritable(tmp_path):
    blocker = tmp_path / "bloque"
    blocker.write_text("x")
    return blocker / "UserData"   # le parent est un fichier : écriture impossible


def test_normal_start_creates_database_and_takes_lock(app_dir):
    ui = FakeUI()
    outcome = startup.prepare(app_dir, app_dir / "UserData", ui, can_relocate=True)
    try:
        assert outcome.ready and outcome.lock.held
        assert (app_dir / "UserData" / "scenix16.db").is_file()
        assert ui.events == []          # aucun dialogue
    finally:
        outcome.lock.release()


def test_second_instance_stopped_without_touching_data(app_dir):
    userdata = app_dir / "UserData"
    first = startup.prepare(app_dir, userdata, FakeUI(), can_relocate=True)
    db_before = (userdata / "scenix16.db").read_bytes()
    ui = FakeUI()
    second = startup.prepare(app_dir, userdata, ui, can_relocate=True)
    first.lock.release()
    assert not second.ready
    assert second.exit_code == startup.EXIT_ALREADY_RUNNING
    assert ui.events == [("running", userdata)]
    assert (userdata / "scenix16.db").read_bytes() == db_before


def test_unwritable_then_quit(app_dir, tmp_path):
    ui = FakeUI(choices=[Choice.QUIT])
    outcome = startup.prepare(app_dir, unwritable(tmp_path), ui, can_relocate=True)
    assert not outcome.ready and outcome.exit_code == startup.EXIT_STORAGE
    assert [e[0] for e in ui.events] == ["problem"]


def test_unwritable_without_relocation_only_quits(app_dir, tmp_path):
    ui = FakeUI(choices=[Choice.CHOOSE_LOCATION])
    outcome = startup.prepare(app_dir, unwritable(tmp_path), ui, can_relocate=False)
    assert not outcome.ready
    assert ui.events[0][2] is False
    assert ("choose",) not in ui.events


def test_unwritable_choose_location_copies_and_restarts(app_dir, tmp_path):
    parent = tmp_path / "accessible"
    parent.mkdir()
    ui = FakeUI(choices=[Choice.CHOOSE_LOCATION], parents=[parent])
    outcome = startup.prepare(app_dir, unwritable(tmp_path), ui, can_relocate=True)
    assert not outcome.ready
    assert outcome.restart_from == (parent / "SceniX16").resolve()
    assert (outcome.restart_from / "SceniX16.exe").is_file()
    assert (outcome.restart_from / "UserData").is_dir()
    assert ("copying", True) in ui.events and ("copying", False) in ui.events


def test_failed_copy_returns_to_warning(app_dir, tmp_path):
    parent = tmp_path / "dest"
    (parent / "SceniX16").mkdir(parents=True)          # conflit : refus sans écrasement
    ui = FakeUI(choices=[Choice.CHOOSE_LOCATION, Choice.QUIT], parents=[parent])
    outcome = startup.prepare(app_dir, unwritable(tmp_path), ui, can_relocate=True)
    kinds = [e[0] for e in ui.events]
    assert kinds == ["problem", "choose", "copying", "copying", "failed", "problem"]
    assert outcome.exit_code == startup.EXIT_STORAGE
    assert list((parent / "SceniX16").iterdir()) == []


def test_cancelled_folder_choice_returns_to_warning(app_dir, tmp_path):
    ui = FakeUI(choices=[Choice.CHOOSE_LOCATION, Choice.QUIT], parents=[None])
    startup.prepare(app_dir, unwritable(tmp_path), ui, can_relocate=True)
    assert [e[0] for e in ui.events] == ["problem", "choose", "problem"]
