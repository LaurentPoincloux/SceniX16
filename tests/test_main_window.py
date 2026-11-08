"""Vérifie la fenêtre du socle (phase 0)."""

from PySide6.QtGui import QColor, QPixmap

from scenix16.paths import resource
from scenix16.ui.main_window import MainWindow
from scenix16.ui.shell.nav_rail import LOGO_HEIGHT
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.stylesheet import application_stylesheet


def make_window(qtbot, qapp):
    qapp.setStyleSheet(application_stylesheet())
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def test_default_logo_present_and_no_group_logo(qapp):  # QPixmap exige une application Qt
    path = resource("logos", "scenix16.png")
    assert path.is_file(), path
    assert not QPixmap(str(path)).isNull()
    # Q20 (Design Book v0.43) : aucun logo de groupe dans les ressources de l'application
    assert sorted(p.name for p in resource("logos").iterdir()) == ["scenix16.png"]
    assert not any("waiting" in p.name.lower() for p in resource().rglob("*"))


def test_window_title_and_sizes(qtbot, qapp):
    window = make_window(qtbot, qapp)
    assert window.windowTitle() == "SceniX16"
    assert window.minimumWidth() == t.WINDOW_MIN_WIDTH
    assert window.minimumHeight() == t.WINDOW_MIN_HEIGHT


def test_background_is_design_book_ground(qtbot, qapp):
    window = make_window(qtbot, qapp)
    image = window.grab().toImage()
    # marge gauche de la zone centrale : fond nu (le centre porte le panneau d'état vide)
    sample = QColor(image.pixel(t.RAIL_WIDTH + 12, image.height() // 3))
    assert sample.name() == t.GROUND.lower()


def test_logo_keeps_proportions(qtbot, qapp):
    window = make_window(qtbot, qapp)
    assert window.logo.source_is_valid()
    source = QPixmap(str(resource("logos", "scenix16.png")))
    expected_width = round(source.width() * LOGO_HEIGHT / source.height())
    assert window.logo.height() == LOGO_HEIGHT
    assert abs(window.logo.width() - expected_width) <= 1


def test_window_resizes_within_limits(qtbot, qapp):
    window = make_window(qtbot, qapp)
    window.resize(800, 500)  # plus petit que le minimum
    assert window.width() >= t.WINDOW_MIN_WIDTH
    assert window.height() >= t.WINDOW_MIN_HEIGHT
    window.resize(1920, 1080)
    assert window.width() == 1920
