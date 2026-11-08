"""Incrément 2.8d : écran de démarrage (D72 ; arbitrages B1 à B6, P1 à P6).

Écran dessiné par SceniX16, statique, fermé uniquement par programme ; étapes réelles ;
fermeture avant toute boîte de démarrage, à l'affichage de CONCERTS et dans chaque échec ;
rapport d'échec anonymisé ; --smoke-test. Les démarrages complets se font dans des dossiers
temporaires : le UserData réel n'est jamais utilisé.
"""

import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QAbstractAnimation, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

import scenix16.app as app_module
from scenix16 import __version__, startup
from scenix16.startup import EXIT_STARTUP_ERROR, Step
from scenix16.startup_report import (APP_TOKEN, HOME_TOKEN, MESSAGE_LIMIT, anonymize, report_text,
                                     write_report)
from scenix16.storage.instance_lock import InstanceLock
from scenix16.ui.splash import (ACCESSIBLE_NAME, HEIGHT, STEP_MESSAGES, STEP_NAMES, WIDTH,
                                StartupSplash, splash_pixmap, version_lines)
from scenix16.ui.startup_dialogs import MessageDialog, QtStartupUI, startup_failed_text
from scenix16.version import DEVELOPMENT_LABEL, BuildInfo

SRC = Path(__file__).resolve().parents[1] / "src"
BUILD = BuildInfo(date(2026, 11, 8), "abc1234", False)


@pytest.fixture
def splash(qtbot, qapp):
    widget = StartupSplash(use_build_file=False)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget
    widget.dismiss()


# --- contenu et aspect (B1, B6, P1) ------------------------------------------------------------------

def test_version_lines_from_sources_and_from_build():
    assert version_lines(None) == (f"Version {__version__}", DEVELOPMENT_LABEL)
    assert version_lines(BUILD) == (f"Version {__version__}", None)   # P1 : sans date de fabrication
    assert __version__ == "0.1.0-dev"


def test_step_messages_are_french_and_real():
    assert STEP_MESSAGES == {
        Step.STARTING: "Démarrage de SceniX16…",
        Step.STORAGE: "Vérification du dossier de données…",
        Step.DATABASE: "Ouverture de la base de données…",
        Step.INTERFACE: "Préparation de l'écran CONCERTS…",
    }
    assert set(STEP_NAMES) == set(Step)                               # chaque étape a un nom d'échec


def test_logical_size_and_sharp_pixmap(qapp):
    one, two = splash_pixmap(1.0, None), splash_pixmap(2.0, None)
    assert (one.width(), one.height()) == (WIDTH, HEIGHT) == (480, 280)
    assert (two.width(), two.height()) == (960, 560) and two.devicePixelRatio() == 2.0


def test_initial_state(splash):
    assert splash.message == "Démarrage de SceniX16…"
    assert splash.accessibleName() == ACCESSIBLE_NAME
    assert splash.size().width() == WIDTH and splash.size().height() == HEIGHT


def test_window_kind_no_taskbar_no_permanent_top(splash):
    flags = splash.windowFlags()
    assert flags & Qt.SplashScreen == Qt.SplashScreen                 # pas de bouton de barre des tâches
    assert flags & Qt.FramelessWindowHint
    assert not flags & Qt.WindowStaysOnTopHint                        # P6


def test_centered_on_primary_screen(splash):
    center = QApplication.primaryScreen().availableGeometry().center()
    geometry = splash.frameGeometry()
    assert abs(geometry.center().x() - center.x()) <= 1 and abs(geometry.center().y() - center.y()) <= 1


def test_static_without_animation_or_timer(splash):
    assert not splash.findChildren(QAbstractAnimation)
    assert not splash.findChildren(QTimer)


def test_step_changes_message_and_description(splash):
    splash.set_step(Step.DATABASE)
    assert splash.message == "Ouverture de la base de données…"
    assert splash.accessibleDescription() == splash.message
    splash.set_step(Step.LOCK)                                        # pas de message propre
    assert splash.message == "Ouverture de la base de données…"


def test_rendering_at_200_percent(tmp_path):
    script = tmp_path / "splash_200.py"
    script.write_text(textwrap.dedent('''
        import json, sys
        from scenix16.app import create_application
        from scenix16.ui.splash import StartupSplash
        app = create_application(sys.argv[:1])
        s = StartupSplash(use_build_file=False); s.show(); app.processEvents()
        image = s.grab()
        print(json.dumps({"dpr": s.devicePixelRatioF(), "logical": [s.width(), s.height()],
                          "pixels": [image.width(), image.height()],
                          "pixmap_dpr": s.pixmap().devicePixelRatio()}))
        s.dismiss()
    '''), encoding="utf-8")
    env = dict(os.environ, QT_SCALE_FACTOR="2", PYTHONPATH=str(SRC))
    done = subprocess.run([sys.executable, "-B", str(script)], capture_output=True, text=True, env=env,
                          timeout=120)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["dpr"] == 2.0 and result["pixmap_dpr"] == 2.0
    assert result["logical"] == [480, 280] and result["pixels"] == [960, 560]


# --- fermeture : programmée uniquement (P5) -------------------------------------------------------------

def test_click_does_not_close(splash, qtbot):
    qtbot.mouseClick(splash, Qt.LeftButton)
    assert splash.isVisible()


def test_user_close_request_is_ignored(splash, qapp):
    qapp.sendEvent(splash, QCloseEvent())                             # Alt+F4, fermeture système
    assert splash.isVisible()
    splash.close()
    assert splash.isVisible()


def test_programmatic_dismiss_always_works(splash):
    splash.dismiss()
    assert not splash.isVisible()
    splash.dismiss()                                                  # sans effet, sans erreur
    assert not splash.isVisible()


def test_finish_closes_when_window_is_shown(splash, qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    splash.finish(window)
    assert not splash.isVisible()
    splash.dismiss()                                                  # toujours possible ensuite


# --- étapes réelles et verrou (startup.prepare) -------------------------------------------------------

class SilentUI:
    def __init__(self):
        self.events = []

    def storage_problem(self, check, can_relocate):
        self.events.append("problem")
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
        self.events.append("running")


def test_steps_reported_in_order(tmp_path):
    steps = []
    outcome = startup.prepare(tmp_path, tmp_path / "UserData", SilentUI(), False, progress=steps.append)
    outcome.lock.release()
    assert steps == [Step.STORAGE, Step.LOCK, Step.DATABASE]


def test_steps_stop_at_second_instance(tmp_path):
    userdata = tmp_path / "UserData"
    first = startup.prepare(tmp_path, userdata, SilentUI(), False)
    steps = []
    outcome = startup.prepare(tmp_path, userdata, SilentUI(), False, progress=steps.append)
    first.lock.release()
    assert outcome.exit_code == startup.EXIT_ALREADY_RUNNING and steps == [Step.STORAGE, Step.LOCK]


def test_lock_released_when_database_fails(tmp_path, monkeypatch):
    def broken(_path):
        raise sqlite3.DatabaseError("file is not a database")
    monkeypatch.setattr(startup.database, "connect", broken)
    userdata = tmp_path / "UserData"
    with pytest.raises(sqlite3.DatabaseError):
        startup.prepare(tmp_path, userdata, SilentUI(), False)
    lock = InstanceLock(userdata)
    assert lock.acquire()                                             # le verrou n'est pas resté pris
    lock.release()


def test_exit_codes_are_distinct():
    codes = [startup.EXIT_QUIT, 1, startup.EXIT_STORAGE, EXIT_STARTUP_ERROR, startup.EXIT_ALREADY_RUNNING]
    assert EXIT_STARTUP_ERROR == 4 and len(set(codes)) == len(codes)


# --- rapport d'échec (B5, P2, P4) -----------------------------------------------------------------------

def failing(message):
    raise RuntimeError(message)


def caught(message):
    try:
        failing(message)
    except RuntimeError as error:
        return error


def test_report_written_with_expected_content(tmp_path):
    app_dir = Path(__file__).resolve().parents[1]                     # racine du projet (les sources)
    home = Path.home()
    error = caught(f"base illisible : {app_dir}\\UserData\\scenix16.db ; {home}\\Documents")
    userdata = tmp_path / "UserData"
    when = datetime(2026, 11, 8, 21, 5, 9)
    path = write_report(userdata, "Ouverture de la base de données", error, when=when, app_dir=app_dir,
                        home=home)
    assert path == userdata / "logs" / "startup-error-20261108-210509.txt"
    text = path.read_text(encoding="utf-8")
    assert "Étape : Ouverture de la base de données" in text
    assert "Date et heure : 08/11/2026 21:05:09" in text
    assert f"Version : {__version__}" in text
    assert "Exception : RuntimeError: base illisible" in text
    assert f"{APP_TOKEN}\\UserData\\scenix16.db" in text and f"{HOME_TOKEN}\\Documents" in text
    assert "Traceback" in text and "failing" in text                  # trace utile au diagnostic
    assert str(app_dir).lower() not in text.lower()                   # aucun chemin réel (P2)
    assert str(home).lower() not in text.lower()


def test_traceback_paths_are_anonymized(tmp_path):
    app_dir = Path(__file__).resolve().parents[1]
    text = report_text("Étape", caught("x"), datetime(2026, 1, 1), app_dir, Path.home())
    assert f'File "{APP_TOKEN}' in text                               # chemin du fichier de test
    assert str(Path(__file__).resolve()).lower() not in text.lower()


def test_exception_message_limited_to_500_characters(tmp_path):
    text = report_text("Étape", caught("A" * 2000), datetime(2026, 1, 1), None, None)
    line = next(l for l in text.splitlines() if l.startswith("Exception : "))
    assert len(line) - len("Exception : RuntimeError: ") == MESSAGE_LIMIT
    assert "A" * (MESSAGE_LIMIT + 1) not in text                      # trace comprise


def test_anonymize_handles_both_slash_styles_and_case():
    app_dir = Path("D:/Softs/SceniX16")
    home = Path("C:/Users/Laurent")
    text = anonymize("d:/softs/scenix16/x ; C:\\Users\\Laurent\\y", app_dir, home)
    assert text == f"{APP_TOKEN}/x ; {HOME_TOKEN}\\y"


def test_chained_exceptions_are_reported():
    try:
        try:
            raise KeyError("cause")
        except KeyError as inner:
            raise ValueError("conséquence") from inner
    except ValueError as error:
        text = report_text("Étape", error, datetime(2026, 1, 1), None, None)
    assert "KeyError" in text and "ValueError: conséquence" in text


def test_report_impossible_never_raises(tmp_path):
    blocker = tmp_path / "UserData"
    blocker.mkdir()
    (blocker / "logs").write_text("ceci est un fichier")            # logs ne peut pas être créé
    assert write_report(blocker, "Étape", caught("x")) is None
    assert write_report(None, "Étape", caught("x")) is None


def test_two_reports_in_the_same_second(tmp_path):
    when = datetime(2026, 11, 8, 21, 0, 0)
    first = write_report(tmp_path, "Étape", caught("x"), when=when)
    second = write_report(tmp_path, "Étape", caught("y"), when=when)
    assert first.name == "startup-error-20261108-210000.txt"
    assert second.name == "startup-error-20261108-210000-2.txt"


# --- boîtes de démarrage : écran fermé avant (B4) ---------------------------------------------------------

class DialogAnswer:
    """Agit sur la boîte de démarrage dès qu'elle est visible : minuteur répétitif conservé
    (toutes les 50 ms, 10 s au plus), arrêté une fois la boîte traitée."""

    def __init__(self, action, attempts=200):
        self.action, self.left = action, attempts
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._attempt)
        self.timer.start()

    def _attempt(self):
        dialog = next((w for w in QApplication.topLevelWidgets()
                       if isinstance(w, MessageDialog) and w.isVisible()), None)
        self.left -= 1
        if dialog is not None or self.left <= 0:
            self.timer.stop()
        if dialog is not None:
            self.action(dialog)


def when_dialog_shown(action):
    return DialogAnswer(action)


def answer_dialog(label, seen, splash):
    def click(dialog):
        seen["splash_visible"] = splash.isVisible()
        next(b for b in dialog.buttons if b.text() == label).click()
    return when_dialog_shown(click)


@pytest.mark.parametrize("call, label", [
    (lambda ui: ui.already_running(Path("X/UserData")), "OK"),
    (lambda ui: ui.storage_problem(__import__("scenix16.storage.userdata", fromlist=["WriteCheck"])
                                   .WriteCheck(Path("X"), False, "refus"), True), "Quitter"),
    (lambda ui: ui.relocation_failed(__import__("scenix16.services.relocation", fromlist=["RelocationError"])
                                     .RelocationError("échec")), "OK"),
    (lambda ui: ui.offer_restart(type("R", (), {"destination": Path("Y"), "files": 3})()), "Plus tard"),
    (lambda ui: ui.startup_failed("Ouverture de la base de données", None), "OK"),
])
def test_splash_closed_before_each_startup_dialog(splash, call, label):
    seen = {}
    answer = answer_dialog(label, seen, splash)            # noqa: F841 (minuteur conservé)
    call(QtStartupUI(splash))
    assert seen["splash_visible"] is False and not splash.isVisible()


def test_splash_closed_before_folder_choice(splash, monkeypatch):
    seen = {}

    def fake_dialog(*_args, **_kwargs):
        seen["splash_visible"] = splash.isVisible()
        return ""
    monkeypatch.setattr("scenix16.ui.startup_dialogs.QFileDialog.getExistingDirectory", fake_dialog)
    assert QtStartupUI(splash).choose_parent_folder() is None
    assert seen["splash_visible"] is False


def test_startup_failed_text_with_and_without_report():
    with_report = startup_failed_text("Ouverture de la base de données", Path("D:/SceniX16/UserData/logs/r.txt"))
    assert "« Ouverture de la base de données »" in with_report and "r.txt" in with_report
    without = startup_failed_text("Ouverture de la base de données", None)
    assert "Aucun rapport technique n'a pu être enregistré." in without


# --- démarrage complet, isolé dans un dossier temporaire ----------------------------------------------

class RecordingSplash(StartupSplash):
    instances = []

    def __init__(self, screen=None):
        super().__init__(screen=screen, use_build_file=False)
        self.steps = []
        self.finished_with = None
        RecordingSplash.instances.append(self)

    def set_step(self, step):
        if hasattr(self, "steps"):
            self.steps.append(step)
        super().set_step(step)

    def finish(self, window):
        self.finished_with = window
        super().finish(window)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Dossier d'application et UserData temporaires : jamais le UserData réel."""
    app_dir = tmp_path / "SceniX16"
    userdata = app_dir / "UserData"
    app_dir.mkdir()
    monkeypatch.setattr(app_module, "application_dir", lambda: app_dir)
    monkeypatch.setattr(app_module, "default_userdata_dir", lambda: userdata)
    monkeypatch.setattr(app_module, "is_frozen", lambda: False)
    RecordingSplash.instances.clear()
    yield app_dir, userdata
    app = QApplication.instance()                     # main() installe l'option A (barre sombre) :
    event_filter = getattr(app, "_dark_title_bar_filter", None)   # retirée pour les tests suivants
    if event_filter is not None:
        app.removeEventFilter(event_filter)
        del app._dark_title_bar_filter


def run_main(*args):
    return app_module.main(["scenix16", *args], splash_factory=RecordingSplash)


def lock_is_free(userdata):
    lock = InstanceLock(userdata)
    free = lock.acquire()
    lock.release()
    return free


# --smoke-test : processus séparé (fidèle au vrai lancement ; la fin de la boucle d'événements
# ne déborde pas sur les autres tests), dossier d'application et UserData temporaires.
SMOKE_DRIVER = textwrap.dedent("""
    import json, sys
    from pathlib import Path
    import scenix16.app as A
    app_dir, userdata, mode, capture = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    A.application_dir = lambda: app_dir
    A.default_userdata_dir = lambda: userdata
    A.is_frozen = lambda: False
    record = {"finished": False}
    import scenix16.ui.main_window as M
    if mode == "normal":
        class Watched(M.MainWindow):
            def showEvent(self, event):
                record["window_screen"] = self.screen().name()
                super().showEvent(event)
        M.MainWindow = Watched
    if mode == "window":
        def broken(*args, **kwargs):
            raise RuntimeError("construction impossible")
        M.MainWindow = broken
    elif mode in ("database", "nolog"):
        import sqlite3
        import scenix16.storage.database as D
        def broken(path):
            raise sqlite3.DatabaseError("file is not a database")
        D.connect = broken
        if mode == "nolog":
            import scenix16.storage.userdata as U
            U.SUBFOLDERS = ()
    from scenix16.ui.splash import StartupSplash
    class Recording(StartupSplash):
        def __init__(self, screen=None):
            self.steps = []
            super().__init__(screen=screen, use_build_file=False)
            record["splash"] = self
            record["splash_screen"] = self.screen().name()
        def set_step(self, step):
            self.steps.append(step.value)
            super().set_step(step)
        def finish(self, window):
            record["finished"] = True
            super().finish(window)
    code = A.main(["scenix16", "--smoke-test", capture], splash_factory=Recording)
    splash = record["splash"]
    print(json.dumps({"code": code, "steps": splash.steps, "visible": splash.isVisible(),
                      "finished": record["finished"], "splash_screen": record["splash_screen"],
                      "window_screen": record.get("window_screen")}))
""")


def smoke(tmp_path, mode="normal", userdata=None):
    app_dir = tmp_path / "SceniX16"
    app_dir.mkdir(exist_ok=True)
    userdata = userdata or app_dir / "UserData"
    driver = tmp_path / "smoke_driver.py"
    driver.write_text(SMOKE_DRIVER, encoding="utf-8")
    capture = tmp_path / "capture.png"
    env = dict(os.environ, PYTHONPATH=str(SRC))
    done = subprocess.run([sys.executable, "-B", str(driver), str(app_dir), str(userdata), mode, str(capture)],
                          capture_output=True, text=True, env=env, timeout=180)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout.strip().splitlines()[-1])
    result["stderr"], result["capture"], result["userdata"] = done.stderr, capture, userdata
    return result


def test_smoke_test_shows_splash_then_closes_it_before_capture(tmp_path):
    r = smoke(tmp_path)
    assert r["code"] == 0 and r["capture"].is_file()                 # capture faite, écran fermé
    assert r["steps"] == ["starting", "storage", "lock", "database", "interface"]
    assert r["finished"] and not r["visible"]
    assert r["window_screen"] == r["splash_screen"]                  # même écran (B6)
    assert lock_is_free(r["userdata"])


def test_failure_while_building_concerts(tmp_path):
    r = smoke(tmp_path, "window")
    assert r["code"] == EXIT_STARTUP_ERROR and not r["visible"] and not r["capture"].exists()
    reports = list((r["userdata"] / "logs").glob("startup-error-*.txt"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "Étape : Préparation de l'écran CONCERTS" in text and "construction impossible" in text
    # chemins anonymisés : le dossier temporaire du test est sous le dossier personnel
    assert str(tmp_path).lower() not in text.lower() and f'File "{HOME_TOKEN}' in text
    assert "SceniX16 n'a pas pu démarrer (étape : Préparation de l'écran CONCERTS)" in r["stderr"]
    assert lock_is_free(r["userdata"])


def test_failure_while_opening_database(tmp_path):
    r = smoke(tmp_path, "database")
    assert r["code"] == EXIT_STARTUP_ERROR and not r["visible"]
    text = next((r["userdata"] / "logs").glob("startup-error-*.txt")).read_text(encoding="utf-8")
    assert "Étape : Ouverture de la base de données" in text and "DatabaseError" in text
    assert lock_is_free(r["userdata"])


def test_failure_without_possible_report(tmp_path):
    userdata = tmp_path / "SceniX16" / "UserData"
    userdata.mkdir(parents=True)
    (userdata / "logs").write_text("fichier à la place du dossier")
    r = smoke(tmp_path, "nolog")
    assert r["code"] == EXIT_STARTUP_ERROR and not r["visible"]
    assert "SceniX16 n'a pas pu démarrer (étape : Ouverture de la base de données)" in r["stderr"]
    assert "rapport" not in r["stderr"]                               # aucun rapport écrit
    assert (userdata / "logs").is_file()


def test_second_instance_closes_splash(tmp_path):
    userdata = tmp_path / "SceniX16" / "UserData"
    first = startup.prepare(tmp_path, userdata, SilentUI(), False)
    try:
        r = smoke(tmp_path)
    finally:
        first.lock.release()
    assert r["code"] == startup.EXIT_ALREADY_RUNNING and not r["visible"]
    assert r["steps"] == ["starting", "storage", "lock"]


def test_unwritable_userdata_closes_splash(tmp_path):
    blocker = tmp_path / "bloque"
    blocker.write_text("x")
    r = smoke(tmp_path, userdata=blocker / "UserData")
    assert r["code"] == startup.EXIT_STORAGE and not r["visible"]


def test_dialog_path_closes_splash_before_message(isolated, tmp_path):
    """Sans --smoke-test : vraie boîte « déjà ouvert », écran déjà fermé quand elle apparaît."""
    _app_dir, userdata = isolated
    first = startup.prepare(*isolated, SilentUI(), False)
    seen = {}

    def answer(dialog):
        seen["splash_visible"] = RecordingSplash.instances[-1].isVisible()
        dialog.buttons[0].click()
    answering = when_dialog_shown(answer)     # noqa: F841 (minuteur conservé)
    try:
        code = run_main()
    finally:
        first.lock.release()
    assert code == startup.EXIT_ALREADY_RUNNING and seen["splash_visible"] is False


def test_failure_dialog_without_smoke_test(isolated, monkeypatch):
    _app_dir, userdata = isolated
    seen = {}

    def broken(*_args, **_kwargs):
        raise RuntimeError("x")
    monkeypatch.setattr("scenix16.ui.main_window.MainWindow", broken)

    def answer(dialog):
        seen["splash_visible"] = RecordingSplash.instances[-1].isVisible()
        seen["title"] = [label.text() for label in dialog.findChildren(QLabel)]
        dialog.buttons[0].click()
    answering = when_dialog_shown(answer)     # noqa: F841 (minuteur conservé)
    code = run_main()
    assert code == EXIT_STARTUP_ERROR and seen["splash_visible"] is False
    assert "SceniX16 n'a pas pu démarrer" in seen["title"]
    assert lock_is_free(userdata)


# --- écran de lancement : démarrage et CONCERTS sur le même écran (B6 mis à jour) ------------------------

from scenix16.ui import screens as screen_module                      # noqa: E402
from scenix16.ui.screens import centered_geometry, choose_screen_index, place_main_window  # noqa: E402

TWO = [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)]                    # écran 2 plus grand, à droite


@pytest.mark.parametrize("pointer, expected", [
    ((300, 500), 0), ((2500, 700), 1), ((1919, 0), 0), ((1920, 0), 1),
    ((-50, 10), 0), ((9000, 9000), 0), (None, 0),
])
def test_screen_under_pointer_else_primary(pointer, expected):
    assert choose_screen_index(TWO, 0, pointer) == expected


def test_primary_used_when_pointer_is_nowhere_even_if_not_first():
    assert choose_screen_index(TWO, 1, (-100, -100)) == 1
    assert choose_screen_index([(0, 0, 1920, 1080)], 0, (10, 10)) == 0       # un seul écran


def test_secondary_screen_with_negative_coordinates():
    screens = [(0, 0, 1920, 1080), (-1280, 100, 1280, 1024)]          # écran 2 à gauche
    assert choose_screen_index(screens, 0, (-600, 400)) == 1


def test_centered_geometry():
    assert centered_geometry((1920, 0, 2560, 1400), (1280, 800), (1024, 640)) == (2560, 300, 1280, 800)
    assert centered_geometry((0, 0, 1920, 1040), (480, 280)) == (720, 380, 480, 280)


def test_window_reduced_on_small_screen_but_never_below_minimum():
    assert centered_geometry((0, 0, 1100, 700), (1280, 800), (1024, 640)) == (0, 0, 1100, 700)
    assert centered_geometry((0, 0, 1200, 760), (1280, 800), (1024, 640)) == (0, 0, 1200, 760)
    assert centered_geometry((100, 50, 900, 600), (1280, 800), (1024, 640)) == (100, 50, 1024, 640)


def test_launch_screen_falls_back_to_primary(qapp, monkeypatch):
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(screen_module.QCursor, "pos", staticmethod(lambda: QPoint(-100000, -100000)))
    assert screen_module.launch_screen() is QApplication.primaryScreen()


def test_launch_screen_is_the_one_under_the_pointer(qapp, monkeypatch):
    from PySide6.QtCore import QPoint
    target = QApplication.screens()[-1]
    center = target.geometry().center()
    monkeypatch.setattr(screen_module.QCursor, "pos", staticmethod(lambda: QPoint(center)))
    assert screen_module.launch_screen() is target


def test_single_screen_keeps_windows_placement(qapp, qtbot, monkeypatch):
    monkeypatch.setattr(screen_module.QGuiApplication, "screens",
                        staticmethod(lambda: [QApplication.primaryScreen()]))
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(700, 500)
    before = window.pos()
    assert place_main_window(window, QApplication.primaryScreen()) is False
    assert window.pos() == before and window.size().width() == 700         # rien n'est changé


def test_splash_created_on_given_screen_with_its_scale(qapp, qtbot):
    for screen in QApplication.screens():
        splash = StartupSplash(screen=screen, use_build_file=False)
        splash.show()
        qtbot.waitExposed(splash)
        try:
            assert splash.screen() is screen
            assert splash.pixmap().devicePixelRatio() == screen.devicePixelRatio()
            area = screen.availableGeometry()
            g = splash.frameGeometry()
            assert area.contains(g) and abs(g.center().x() - area.center().x()) <= 1
        finally:
            splash.dismiss()


def test_two_real_screens_window_and_splash_on_second_screen(qapp, qtbot):
    if len(QApplication.screens()) < 2:
        pytest.skip("au moins deux écrans réels nécessaires")
    second = QApplication.screens()[1]
    splash = StartupSplash(screen=second, use_build_file=False)
    splash.show()
    window = QWidget()
    qtbot.addWidget(window)
    window.setMinimumSize(1024, 640)
    try:
        assert place_main_window(window, second) is True
        window.show()
        qtbot.waitExposed(window)
        assert window.screen() is second and splash.screen() is second
        assert second.availableGeometry().intersects(window.frameGeometry())
        assert abs(window.geometry().center().x() - second.availableGeometry().center().x()) <= 2
    finally:
        splash.dismiss()
