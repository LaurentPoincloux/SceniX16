"""Navigation MAIN / PARAMÈTRES et import depuis la section DONNÉES."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from scenix16.importer.service import import_into_userdata
from scenix16.storage import database
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.main_window import MainWindow
from scenix16.ui.settings_page import (
    IMPORT_DISABLED_HINT, IMPORT_HINT, IMPORT_LABEL, SettingsPage,
)
from scenix16.ui.theme.stylesheet import application_stylesheet

WORKBOOK = Path(__file__).resolve().parents[1] / "reference" / "SceniX16_Setlist_Manager_v2.3.0.xlsx"


class Recorder:
    def __init__(self, files=()):
        self.files = list(files)
        self.messages = []
        self.chooser_calls = 0

    def choose(self, parent):
        self.chooser_calls += 1
        return self.files.pop(0) if self.files else None

    def show(self, title, text):
        self.messages.append((title, text))


@pytest.fixture
def userdata(tmp_path):
    path = tmp_path / "UserData"
    assert check_writable(path).writable
    database.connect(database_path(path)).close()   # base vide, comme après le démarrage
    return path


@pytest.fixture
def window(qtbot, qapp, userdata):
    qapp.setStyleSheet(application_stylesheet())
    rec = Recorder()
    page = SettingsPage(userdata, choose_file=rec.choose, show_message=rec.show)
    win = MainWindow(userdata, settings_page=page)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.recorder = rec
    return win


def count(userdata, table):
    conn = database.connect(database_path(userdata))
    try:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# --- navigation ---------------------------------------------------------------

def test_gear_opens_settings_and_back_button_returns(window, qtbot):
    assert window.pages.currentWidget() is window.main_page
    qtbot.mouseClick(window.gear_button, Qt.LeftButton)
    assert window.pages.currentWidget() is window.settings_page
    assert window.settings_page.back_button.text() == "← MAIN"
    qtbot.mouseClick(window.settings_page.back_button, Qt.LeftButton)
    assert window.pages.currentWidget() is window.main_page


def test_escape_returns_to_main(window, qtbot):
    window.show_settings()
    qtbot.keyClick(window.settings_page, Qt.Key_Escape)
    assert window.pages.currentWidget() is window.main_page


def test_no_import_entry_on_main_page(window):
    from PySide6.QtWidgets import QPushButton
    labels = [b.text() for b in window.main_page.findChildren(QPushButton)]
    assert IMPORT_LABEL not in labels


# --- état de l'entrée d'import ------------------------------------------------

def test_entry_enabled_on_empty_database(window):
    window.show_settings()
    page = window.settings_page
    assert page.import_button.text() == IMPORT_LABEL
    assert page.import_button.isEnabled()
    assert page.import_hint.text() == IMPORT_HINT


def test_entry_state_refreshed_at_each_opening(window, userdata):
    window.show_settings()
    assert window.settings_page.import_button.isEnabled()
    window.show_main()
    import_into_userdata(WORKBOOK, userdata)          # base remplie par ailleurs
    window.show_settings()
    assert not window.settings_page.import_button.isEnabled()
    assert window.settings_page.import_hint.text() == IMPORT_DISABLED_HINT


# --- parcours d'import --------------------------------------------------------

def test_successful_import_shows_counts_and_disables_entry(window, userdata):
    window.show_settings()
    page, rec = window.settings_page, window.recorder
    rec.files = [WORKBOOK]
    page.import_button.click()
    title, text = rec.messages[-1]
    assert title == "Import terminé"
    assert "37 morceaux, 3 setlists et 64 entrées" in text
    assert "13 particularités" in text
    assert str(userdata / "logs") in text
    assert not page.import_button.isEnabled()          # désactivée sans redémarrage
    assert count(userdata, "tracks") == 37


def test_cancelled_file_choice_changes_nothing(window, userdata):
    window.show_settings()
    window.settings_page.import_button.click()
    assert window.recorder.chooser_calls == 1
    assert window.recorder.messages == []
    assert count(userdata, "tracks") == 0
    assert window.settings_page.import_button.isEnabled()


def test_invalid_file_refused_with_clear_message(window, userdata, tmp_path):
    fake = tmp_path / "faux.xlsx"
    fake.write_text("pas un classeur", encoding="utf-8")
    window.show_settings()
    window.recorder.files = [fake]
    window.settings_page.import_button.click()
    title, text = window.recorder.messages[-1]
    assert title == "Import refusé"
    assert "Aucune donnée n'a été modifiée" in text
    assert "Traceback" not in text
    assert count(userdata, "tracks") == 0
    assert window.settings_page.import_button.isEnabled()


def test_unexpected_error_presented_without_partial_data(window, userdata, monkeypatch):
    from scenix16.ui import settings_page as module

    def boom(xlsx, ud):
        raise ValueError("détail technique")

    monkeypatch.setattr(module, "import_into_userdata", boom)
    window.show_settings()
    window.recorder.files = [WORKBOOK]
    window.settings_page.import_button.click()
    title, text = window.recorder.messages[-1]
    assert title == "L'import a échoué"
    assert "ValueError" in text and "détail technique" not in text
    assert count(userdata, "tracks") == 0


def test_refused_when_database_not_empty_even_if_triggered(window, userdata):
    import_into_userdata(WORKBOOK, userdata)
    window.show_settings()
    window.recorder.files = [WORKBOOK]
    window.settings_page.run_import()                  # appel direct malgré l'entrée désactivée
    title, _ = window.recorder.messages[-1]
    assert title == "Import refusé"
    assert count(userdata, "tracks") == 37             # rien de doublé
