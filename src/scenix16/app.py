"""Création de l'application Qt et lancement de la fenêtre principale.

Démarrage (D72, incrément 2.8d) :
1. QApplication, polices et feuille de style ;
2. écran de démarrage affiché aussitôt (B2 : l'interface n'est importée qu'ensuite) ;
3. étapes réelles (dossier de données, verrou, base, écran CONCERTS) annoncées par l'écran ;
4. fermeture de l'écran dès que CONCERTS est affichée, sans délai artificiel.
L'écran est fermé avant toute boîte de démarrage (B4) et dans tout cas de sortie. Un échec
inattendu ferme l'écran, écrit si possible un rapport technique anonymisé dans UserData\\logs
(B5), présente un message compréhensible et rend le code de sortie 4 ; le verrou est toujours
libéré. --smoke-test affiche aussi l'écran (B3), qui est fermé avant la capture.
Écran de lancement (B6 mis à jour) : choisi une seule fois (sous le pointeur, sinon écran
principal) ; l'écran de démarrage y est centré et, avec plusieurs écrans, CONCERTS aussi.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from scenix16 import startup
from scenix16.paths import is_frozen
from scenix16.startup import EXIT_QUIT, EXIT_STARTUP_ERROR, Step
from scenix16.startup_report import write_report
from scenix16.storage.userdata import application_dir, default_userdata_dir
from scenix16.ui import dark_title_bar
from scenix16.ui.screens import launch_screen, place_main_window
from scenix16.ui.splash import STEP_NAMES, StartupSplash
from scenix16.ui.theme.fonts import load_fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

SMOKE_TEST_FLAG = "--smoke-test"


def create_application(argv: list[str]) -> QApplication:
    # Mise à l'échelle fidèle au facteur Windows (125 %, 150 %…), sans arrondi.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("SceniX16")
    load_fonts()  # polices locales du Design Book, avant la feuille de style
    app.setStyle("Fusion")
    app.setStyleSheet(application_stylesheet())
    dark_title_bar.install(app)   # barre de titre native sombre (D61, option A) ; voir le module
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

    def startup_failed(self, step_name, report):
        detail = f" ; rapport : {report}" if report is not None else ""
        print(f"SceniX16 n'a pas pu démarrer (étape : {step_name}){detail}", file=sys.stderr)


def startup_ui(smoke: bool, splash):
    if smoke:
        return HeadlessStartupUI()
    from scenix16.ui.startup_dialogs import QtStartupUI
    return QtStartupUI(splash)


def report_failure(error: BaseException, step: Step, ui, splash, userdata: Path,
                   app_dir: Path) -> int:
    """Échec inattendu (B5) : écran fermé, rapport si possible, message, code de sortie 4."""
    splash.dismiss()
    step_name = STEP_NAMES[step]
    report = write_report(userdata, step_name, error, app_dir=app_dir)
    try:
        ui.startup_failed(step_name, report)
    except Exception:                            # le message ne doit pas masquer le code de sortie
        print(f"SceniX16 n'a pas pu démarrer (étape : {step_name})", file=sys.stderr)
    return EXIT_STARTUP_ERROR


def main(argv: list[str], splash_factory=StartupSplash) -> int:
    app = create_application(argv)
    smoke = SMOKE_TEST_FLAG in argv
    screen = launch_screen()                     # même écran pour le démarrage et CONCERTS (B6)
    splash = splash_factory(screen=screen)
    splash.show()
    app.processEvents()                          # premier affichage, avant les étapes bloquantes
    ui = startup_ui(smoke, splash)
    current = {"step": Step.STARTING}

    def progress(step: Step) -> None:
        current["step"] = step
        splash.set_step(step)

    app_dir, userdata = application_dir(), default_userdata_dir()
    outcome = None
    try:
        try:
            outcome = startup.prepare(app_dir, userdata, ui, can_relocate=is_frozen(),
                                      progress=progress)
            if outcome.restart_from is not None:
                splash.dismiss()
                executable = outcome.restart_from / Path(sys.executable).name
                QProcess.startDetached(str(executable), [], str(outcome.restart_from))
                return EXIT_QUIT
            if not outcome.ready:
                splash.dismiss()
                return outcome.exit_code

            progress(Step.INTERFACE)
            from scenix16.ui.main_window import MainWindow   # import différé (B2)
            window = MainWindow(outcome.userdata)
            place_main_window(window, screen)    # plusieurs écrans : CONCERTS sur l'écran de lancement
            window.show()
            splash.finish(window)                # CONCERTS affichée : l'écran se ferme
        except Exception as error:
            return report_failure(error, current["step"], ui, splash, userdata, app_dir)

        # Outil de vérification : ouvre la fenêtre, en enregistre une capture
        # puis ferme l'application (utilisé pour tester l'exécutable).
        if smoke:
            index = argv.index(SMOKE_TEST_FLAG)
            target = Path(argv[index + 1]) if index + 1 < len(argv) else None
            result = {"code": 1}

            def capture_and_quit():
                splash_closed = not splash.isVisible()       # B3 : fermé avant la capture
                if splash_closed and target is not None and window.grab().save(str(target)):
                    result["code"] = 0
                app.quit()

            QTimer.singleShot(1500, capture_and_quit)
            app.exec()
            return result["code"]

        return app.exec()
    finally:
        splash.dismiss()                         # fermeture programmée toujours possible
        if outcome is not None and outcome.lock is not None:
            outcome.lock.release()
