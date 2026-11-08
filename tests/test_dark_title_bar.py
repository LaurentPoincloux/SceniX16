"""Barre de titre native sombre (D61, option A — repli de 2.8e).

Le cadre et les comportements natifs sont conservés : seul l'attribut DWM est posé, à chaque
affichage d'une fenêtre principale ou d'une boîte de dialogue Qt. Tout refus est silencieux.
Les vérifications visuelles se font sur l'écran réel (ignorées sans affichage).
"""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QMainWindow, QMenu, QSplashScreen, QWidget

from scenix16.ui import dark_title_bar as dtb


@pytest.fixture
def calls(monkeypatch):
    """Remplace l'appel Windows : enregistre les fenêtres traitées (aucun effet réel)."""
    seen = []
    monkeypatch.setattr(dtb, "supported", lambda: True)
    monkeypatch.setattr(dtb, "_dwm_set_dark", lambda hwnd: seen.append(hwnd) or 0)
    monkeypatch.setattr(dtb, "_redraw_frame", lambda hwnd, active: seen.append(("redraw", hwnd)))
    return seen


@pytest.fixture
def installed(qapp, calls):
    event_filter = dtb.DarkTitleBarFilter()
    qapp.installEventFilter(event_filter)
    yield calls
    qapp.removeEventFilter(event_filter)


def real_display():
    return QGuiApplication.platformName() == "windows"


# --- systèmes pris en charge ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform, build, expected", [
    ("win32", 19045, True), ("win32", 19041, True), ("win32", 22631, True),
    ("win32", 18363, False), ("linux", 22631, False),
])
def test_supported_systems(monkeypatch, platform, build, expected):
    monkeypatch.setattr(dtb.sys, "platform", platform)
    monkeypatch.setattr(dtb.sys, "getwindowsversion",
                        lambda: SimpleNamespace(major=10, minor=0, build=build), raising=False)
    assert dtb.supported() is expected


def test_unsupported_system_does_nothing(qapp, monkeypatch):
    monkeypatch.setattr(dtb, "supported", lambda: False)
    monkeypatch.setattr(dtb, "_dwm_set_dark", lambda hwnd: pytest.fail("aucun appel attendu"))
    assert dtb.apply_dark_title_bar(QMainWindow()) is False
    assert dtb.install(SimpleNamespace()) is None


def test_disabled_switch_restores_native_behaviour(qapp, monkeypatch, calls):
    monkeypatch.setattr(dtb, "ENABLED", False)
    assert dtb.apply_dark_title_bar(QMainWindow()) is False and calls == []
    assert dtb.install(SimpleNamespace()) is None


# --- refus et erreurs : silencieux ------------------------------------------------------------------------

def test_windows_refusal_is_silent(qapp, monkeypatch):
    monkeypatch.setattr(dtb, "supported", lambda: True)
    monkeypatch.setattr(dtb, "_dwm_set_dark", lambda hwnd: -2147024809)          # E_INVALIDARG
    assert dtb.apply_dark_title_bar(QMainWindow()) is False


def test_api_error_is_silent(qapp, monkeypatch):
    def broken(hwnd):
        raise OSError("dwmapi indisponible")
    monkeypatch.setattr(dtb, "supported", lambda: True)
    monkeypatch.setattr(dtb, "_dwm_set_dark", broken)
    assert dtb.apply_dark_title_bar(QMainWindow()) is False


# --- fenêtres concernées --------------------------------------------------------------------------------

def test_concerned_windows(qapp):
    assert dtb.concerned(QMainWindow()) and dtb.concerned(QDialog())
    assert not dtb.concerned(QWidget())                                  # ni principale ni dialogue
    assert not dtb.concerned(QSplashScreen())                            # écran de démarrage exclu
    assert not dtb.concerned(QMenu())
    frameless = QDialog()
    frameless.setWindowFlags(frameless.windowFlags() | Qt.FramelessWindowHint)
    assert not dtb.concerned(frameless)
    parent = QMainWindow()
    child = QMainWindow(parent)
    child.setWindowFlags(Qt.Widget)                                      # intégrée, pas une fenêtre
    assert not dtb.concerned(child)


def test_applied_at_each_show(installed, qtbot):
    window, dialog = QMainWindow(), QDialog()
    for widget in (window, dialog):
        qtbot.addWidget(widget)
        widget.show()
    handles = [int(window.winId()), int(dialog.winId())]
    assert [c for c in installed if not isinstance(c, tuple)] == handles
    dialog.hide()
    dialog.show()                                                        # nouvel affichage : réappliqué
    assert installed.count(int(dialog.winId())) == 2


def test_not_applied_to_splash_menus_or_plain_widgets(installed, qtbot):
    splash, plain = QSplashScreen(), QWidget()
    for widget in (splash, plain):
        qtbot.addWidget(widget)
        widget.show()
    splash.close()
    assert installed == []


def test_theme_change_reapplies_and_redraws(installed, qtbot, qapp):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.show()
    installed.clear()
    qapp.sendEvent(window, QEvent(QEvent.ThemeChange))
    assert installed == [int(window.winId()), ("redraw", int(window.winId()))]


def test_flags_and_geometry_unchanged(installed, qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.resize(1100, 700)
    flags = window.windowFlags()
    window.show()
    qtbot.waitExposed(window)
    assert window.windowFlags() == flags                                 # cadre et boutons natifs
    assert flags & Qt.WindowSystemMenuHint and flags & Qt.WindowCloseButtonHint
    assert (window.width(), window.height()) == (1100, 700)


class FakeApp(QObject):
    def __init__(self):
        super().__init__()
        self.filters = []

    def installEventFilter(self, event_filter):
        self.filters.append(event_filter)


def test_install_once_per_application(qapp, monkeypatch):
    monkeypatch.setattr(dtb, "supported", lambda: True)
    app = FakeApp()
    first = dtb.install(app)
    assert isinstance(first, dtb.DarkTitleBarFilter)
    assert dtb.install(app) is first and app.filters == [first]


def test_create_application_installs_option_a(qapp, monkeypatch):
    from scenix16.app import create_application
    monkeypatch.setattr(dtb, "supported", lambda: True)
    monkeypatch.delattr(qapp, "_dark_title_bar_filter", raising=False)
    app = create_application([])
    try:
        assert isinstance(getattr(app, "_dark_title_bar_filter", None), dtb.DarkTitleBarFilter)
    finally:
        app.removeEventFilter(app._dark_title_bar_filter)
        del app._dark_title_bar_filter


# --- vérifications réelles (écran réel, Windows) ----------------------------------------------------------

def title_bar_color(widget):
    image = QGuiApplication.primaryScreen().grabWindow(0).toImage()
    frame, geometry = widget.frameGeometry(), widget.geometry()
    ratio = QGuiApplication.primaryScreen().devicePixelRatio()
    x, y = frame.left() + frame.width() // 2, (frame.top() + geometry.top()) // 2
    return image.pixelColor(round(x * ratio), round(y * ratio))


@pytest.mark.parametrize("kind", [QMainWindow, QDialog])
def test_real_title_bar_is_dark(qapp, qtbot, kind):
    if not real_display() or not dtb.supported():
        pytest.skip("barre de titre réelle : écran réel sous Windows 10 (19041+) ou 11")
    event_filter = dtb.DarkTitleBarFilter()
    qapp.installEventFilter(event_filter)
    try:
        widget = kind()
        qtbot.addWidget(widget)
        widget.setWindowTitle("SceniX16 — essai de barre sombre")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        widget.resize(520, 200)
        widget.move(screen.x() + 60, screen.y() + 60)
        widget.show()
        widget.raise_()
        widget.activateWindow()
        qtbot.waitExposed(widget)
        qtbot.wait(400)
        assert title_bar_color(widget).lightness() < 80               # barre native sombre
    finally:
        qapp.removeEventFilter(event_filter)
