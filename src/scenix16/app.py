"""Création de l'application Qt et lancement de la fenêtre principale."""

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from scenix16 import startup
from scenix16.paths import is_frozen
from scenix16.storage.userdata import application_dir, default_userdata_dir
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme.stylesheet import application_stylesheet

SMOKE_TEST_FLAG = "--smoke-test"


def create_application(argv: list[str]) -> QApplication:
    # Mise à l'échelle fidèle au facteur Windows (125 %, 150 %…), sans arrondi.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("SceniX16")
    app.setStyle("Fusion")
    app.setStyleSheet(application_stylesheet())
    return app


class HeadlessStartupUI:
    """Démarrage sans dialogue (vérification automatique) : tout problème arrête."""

    def storage_problem(self, check, can_relocate):
        return startup.Choice.QUIT

    def choose_parent_folder(self):
        return None

    def copying(self, running):
        pass

    def relocation_failed(self, error):
        pass

    def offer_restart(self, result):
        return False

    def already_running(self, userdata):
        pass


def main(argv: list[str]) -> int:
    app = create_application(argv)
    smoke = SMOKE_TEST_FLAG in argv
    if smoke:
        ui = HeadlessStartupUI()
    else:
        from scenix16.ui.startup_dialogs import QtStartupUI
        ui = QtStartupUI()

    outcome = startup.prepare(
        application_dir(), default_userdata_dir(), ui, can_relocate=is_frozen()
    )
    if outcome.restart_from is not None:
        executable = outcome.restart_from / Path(sys.executable).name
        QProcess.startDetached(str(executable), [], str(outcome.restart_from))
        return startup.EXIT_QUIT
    if not outcome.ready:
        return outcome.exit_code

    try:
        window = MainWindow()
        window.show()

        # Outil de vérification : ouvre la fenêtre, en enregistre une capture
        # puis ferme l'application (utilisé pour tester l'exécutable).
        if smoke:
            index = argv.index(SMOKE_TEST_FLAG)
            target = Path(argv[index + 1]) if index + 1 < len(argv) else None
            result = {"code": 1}

            def capture_and_quit():
                if target is not None and window.grab().save(str(target)):
                    result["code"] = 0
                app.quit()

            QTimer.singleShot(1500, capture_and_quit)
            app.exec()
            return result["code"]

        return app.exec()
    finally:
        outcome.lock.release()
