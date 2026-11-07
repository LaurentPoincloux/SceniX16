"""Fenêtres de dialogue du démarrage (aspect et boutons)."""

from pathlib import Path

from PySide6.QtCore import QTimer

from scenix16.startup import Choice
from scenix16.storage.userdata import WriteCheck
from scenix16.ui.startup_dialogs import MessageDialog, QtStartupUI
from scenix16.ui.theme.stylesheet import application_stylesheet


def click_when_shown(qtbot, label):
    def click():
        dialog = next(w for w in __import__("PySide6.QtWidgets", fromlist=["QApplication"])
                      .QApplication.topLevelWidgets()
                      if isinstance(w, MessageDialog) and w.isVisible())
        button = next(b for b in dialog.buttons if b.text() == label)
        button.click()
    QTimer.singleShot(200, click)


def test_storage_dialog_quit(qtbot, qapp):
    qapp.setStyleSheet(application_stylesheet())
    click_when_shown(qtbot, "Quitter")
    choice = QtStartupUI().storage_problem(WriteCheck(Path("C:/Program Files/SceniX16/UserData"), False, "refus"), True)
    assert choice is Choice.QUIT


def test_storage_dialog_choose(qtbot, qapp):
    click_when_shown(qtbot, "Choisir un emplacement…")
    choice = QtStartupUI().storage_problem(WriteCheck(Path("X"), False, "refus"), True)
    assert choice is Choice.CHOOSE_LOCATION


def test_storage_dialog_choose_disabled_without_relocation(qtbot, qapp):
    seen = {}

    def inspect():
        from PySide6.QtWidgets import QApplication
        dialog = next(w for w in QApplication.topLevelWidgets()
                      if isinstance(w, MessageDialog) and w.isVisible())
        seen["labels"] = [b.text() for b in dialog.buttons]
        seen["enabled"] = [b.isEnabled() for b in dialog.buttons]
        dialog.buttons[0].click()

    QTimer.singleShot(200, inspect)
    QtStartupUI().storage_problem(WriteCheck(Path("X"), False, "refus"), False)
    assert seen["labels"] == ["Quitter", "Choisir un emplacement…"]
    assert seen["enabled"] == [True, False]


def test_already_running_dialog(qtbot, qapp):
    click_when_shown(qtbot, "OK")
    QtStartupUI().already_running(Path("D:/SceniX16/UserData"))
