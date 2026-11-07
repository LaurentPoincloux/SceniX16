"""Création de l'application Qt et lancement de la fenêtre principale."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

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


def main(argv: list[str]) -> int:
    app = create_application(argv)
    window = MainWindow()
    window.show()

    # Outil de vérification de la phase 0 : ouvre la fenêtre, en enregistre
    # une capture puis ferme l'application (utilisé pour tester l'exécutable).
    if SMOKE_TEST_FLAG in argv:
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
