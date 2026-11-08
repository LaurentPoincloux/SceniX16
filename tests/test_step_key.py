"""Composant Touche : proportions, couleurs, voyant, états, INIT."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from scenix16.domain.dashboard import ConcertState
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.widgets.step_key import (
    ASPECT, GROUP_COLORS, LED_RATIO, LED_TOP, MARGIN, MAX_WIDTH, MIN_WIDTH, Led, StepKey,
)


@pytest.fixture
def make_key(qtbot, qapp):
    fonts.load_fonts()

    def make(state=ConcertState.UPCOMING, number=1, group=0, width=70, animations=False):
        key = StepKey(number, group)
        qtbot.addWidget(key)
        key.resize(width + 2 * MARGIN, key.heightForWidth(width + 2 * MARGIN))
        key.set_concert_state(state, animations=animations)
        key.show()
        qtbot.waitExposed(key)
        return key
    return make


def pixel(key, x, y) -> QColor:
    image = key.grab().toImage()
    ratio = image.devicePixelRatio()
    return QColor(image.pixel(round(x * ratio), round(y * ratio)))


def body_sample(key):
    """Point du corps hors voyant, numéro et relief."""
    b = key.body_rect()
    return pixel(key, b.center().x() - b.width() * 0.3, b.top() + b.height() * 0.5)


def led_center(key):
    b = key.body_rect()
    d = b.width() * LED_RATIO
    return pixel(key, b.center().x(), b.top() + b.height() * LED_TOP + d / 2)


# --- proportions --------------------------------------------------------------

@pytest.mark.parametrize("width", [MIN_WIDTH, 60, 80, MAX_WIDTH])
def test_body_ratio_three_five(make_key, width):
    key = make_key(width=width)
    body = key.body_rect()
    assert abs(body.width() - width) <= 1
    assert abs(body.height() / body.width() - ASPECT) < 0.02


def test_width_limits_and_height_for_width(make_key):
    key = make_key()
    assert key.hasHeightForWidth()
    assert key.minimumWidth() == MIN_WIDTH + 2 * MARGIN
    assert key.maximumWidth() == MAX_WIDTH + 2 * MARGIN
    assert key.heightForWidth(60 + 2 * MARGIN) == 100 + 2 * MARGIN


def test_body_keeps_ratio_in_wrong_sized_widget(make_key):
    key = make_key()
    key.resize(200, 120)                 # place trop large et trop basse
    body = key.body_rect()
    assert abs(body.height() / body.width() - ASPECT) < 0.02
    assert body.height() <= 120


# --- couleurs des groupes -----------------------------------------------------

@pytest.mark.parametrize("group", [0, 1, 2, 3])
def test_group_colors(make_key, group):
    key = make_key(group=group)
    assert body_sample(key).name() == GROUP_COLORS[group].lower()


def test_group_color_order_matches_design_book():
    assert GROUP_COLORS == (t.KEY_RED, t.KEY_ORANGE, t.KEY_YELLOW, t.KEY_WHITE)
    assert [c.upper() for c in GROUP_COLORS] == ["#FF4E3A", "#FF9450", "#FCE95C", "#F9FFFF"]


# --- voyant et états ----------------------------------------------------------

def test_upcoming_led_on_without_halo(make_key):
    key = make_key(ConcertState.UPCOMING)
    assert key.led is Led.ON
    assert led_center(key).name() == t.LED_ON.lower()


def test_next_led_ringed_without_glow(make_key):
    """D57 : « prochain » = point cerclé (Led.HALO conservé), sans lueur autour du cercle."""
    from scenix16.ui.widgets.step_key import STATUS_RING_GAP, STATUS_RING_WIDTH
    key = make_key(ConcertState.NEXT, group=3)
    assert key.led is Led.HALO
    assert led_center(key).name() == t.LED_ON.lower()
    b = key.body_rect()
    d = b.width() * LED_RATIO
    cx, cy = b.center().x(), b.top() + b.height() * LED_TOP + d / 2
    ring = cx + d / 2 + STATUS_RING_GAP + STATUS_RING_WIDTH / 2
    tint = pixel(key, ring, cy)
    assert tint.red() > 200 and tint.green() < 120                   # cercle rouge
    gap = pixel(key, cx + d / 2 + STATUS_RING_GAP / 2, cy)
    assert gap.green() > tint.green() + 60                           # écart nettement plus clair que le cercle
    outside = pixel(key, ring + STATUS_RING_WIDTH + 3, cy)
    assert outside.name() == t.KEY_WHITE.lower()                     # aucune lueur au-delà
    upcoming = make_key(ConcertState.UPCOMING, group=3)
    assert pixel(upcoming, ring, cy).name() == t.KEY_WHITE.lower()   # « à venir » : pas de cercle


def test_today_ringed_and_fixed_without_selection(make_key):
    """D11 révisée en v0.45 : le concert du jour garde un point cerclé fixe ; il ne pulse plus de lui-même."""
    key = make_key(ConcertState.TODAY, animations=True)
    assert key.led is Led.HALO and not key.pulsing and not key.pulse_running()
    assert led_center(key).name() == t.LED_ON.lower()


def test_selected_pair_pulses_whatever_its_state(make_key):
    """D57, D63 (v0.45) : la pulsation suit la paire sélectionnée, quel que soit l'état du concert."""
    for state in (ConcertState.UPCOMING, ConcertState.NEXT, ConcertState.TODAY):
        key = make_key(state, animations=True)
        key.set_pulsing(True, animations=True)
        assert key.pulsing and key.pulse_running()
        key.set_pulsing(False, animations=True)
        assert not key.pulsing and not key.pulse_running()


def test_selected_pair_fixed_when_animations_reduced(make_key):
    key = make_key(ConcertState.UPCOMING, animations=False)
    key.set_pulsing(True, animations=False)
    assert not key.pulsing and not key.pulse_running()
    assert led_center(key).name() == t.LED_ON.lower()


def test_init_key_never_pulses(make_key):
    key = make_key(None)
    key.set_pulsing(True, animations=True)
    assert not key.pulsing and not key.pulse_running()


def test_states_absent_from_dashboard_are_rejected(make_key):
    key = make_key()
    for state in (ConcertState.PAST, ConcertState.CANCELLED, ConcertState.UNDATED):
        with pytest.raises(ValueError):
            key.set_concert_state(state)


def test_number_uses_plex_mono(make_key):
    key = make_key(number=7)
    assert key.number_font().family() == fonts.MONO_FAMILY


# --- INIT : inactive, sans focus ----------------------------------------------

def test_init_key_inactive_without_focus(make_key, qtbot):
    key = make_key(None)
    assert key.is_init and key.led is Led.OFF
    assert not key.isEnabled()
    assert key.focusPolicy() == Qt.NoFocus
    key.setFocus()
    assert not key.hasFocus()
    clicks = []
    key.clicked.connect(lambda: clicks.append(1))
    qtbot.mouseClick(key, Qt.LeftButton, pos=key.body_rect().center().toPoint())
    assert clicks == []
    assert led_center(key).name() == t.LED_OFF.lower()


def test_init_key_is_dimmed(make_key):
    active = make_key(ConcertState.UPCOMING, group=0)
    init = make_key(None, group=0)
    a, i = body_sample(active), body_sample(init)
    assert i.saturationF() < a.saturationF() * 0.5
    assert i.valueF() < a.valueF() * 0.7


def test_init_ignores_selection_and_highlight(make_key):
    key = make_key(None)
    key.set_selected(True)
    key.set_highlighted(True)
    assert not key.selected and not key.highlighted


def test_init_then_active_again(make_key):
    key = make_key(None)
    key.set_concert_state(ConcertState.UPCOMING, animations=False)
    assert key.isEnabled() and key.focusPolicy() == Qt.TabFocus      # clavier seulement (v0.45)


# --- interaction --------------------------------------------------------------

def test_active_key_clickable_and_focusable(make_key, qtbot):
    key = make_key(ConcertState.UPCOMING)
    clicks = []
    key.clicked.connect(lambda: clicks.append(1))
    qtbot.mouseClick(key, Qt.LeftButton, pos=key.body_rect().center().toPoint())
    assert clicks == [1]
    assert key.isEnabled() and key.focusPolicy() == Qt.TabFocus      # focus au clavier seulement
    assert not key.hasFocus()                                         # un clic ne donne pas le focus (D8, v0.45)


def ring_pixel(key):
    b = key.body_rect()
    return pixel(key, b.center().x(), b.top() - 3 - 1)


def test_flat_body_without_relief(make_key):
    """D57 : ni liseré clair en haut, ni bande sombre en bas."""
    key = make_key(ConcertState.UPCOMING, group=0)
    b = key.body_rect()
    expected = t.KEY_RED.lower()
    assert pixel(key, b.left() + b.width() * 0.25, b.top() + 0.5).name() == expected
    assert pixel(key, b.left() + b.width() * 0.25, b.bottom() - 2).name() == expected


def test_selected_cream_underline_no_ring(make_key):
    """D63 : fiche ouverte = filet crème sous la touche, plus d'anneau crème."""
    from scenix16.ui.widgets.step_key import UNDERLINE, UNDERLINE_GAP
    key = make_key(ConcertState.UPCOMING)
    key.set_selected(True)
    b = key.body_rect()
    assert pixel(key, b.center().x(), b.bottom() + UNDERLINE_GAP + UNDERLINE / 2).name() == t.SILK.lower()
    assert ring_pixel(key).name() != t.SILK.lower()


def test_highlight_brightens_without_ring(make_key):
    """D63 : paire mise en évidence = +6 % de luminosité, aucun anneau."""
    key = make_key(ConcertState.UPCOMING, group=0)
    rest = body_sample(key)
    key.set_highlighted(True)
    lit = body_sample(key)
    assert lit.lightness() > rest.lightness()
    assert ring_pixel(key).name() != t.SILK.lower()


def test_focus_ring_brand(make_key, qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    key = StepKey(1, 0, host)
    key.set_concert_state(ConcertState.UPCOMING, animations=False)
    key.resize(80, key.heightForWidth(80))
    host.show()
    host.activateWindow()
    qtbot.waitExposed(host)
    key.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(key.hasFocus)
    assert ring_pixel(key).name() == t.BRAND.lower()


def near(color: QColor, expected: str, tolerance: int = 8) -> bool:
    """Couleur à quelques unités près (bord lissé d'un tracé de 2 px)."""
    e = QColor(expected)
    return all(abs(a - b) <= tolerance for a, b in ((color.red(), e.red()), (color.green(), e.green()),
                                                    (color.blue(), e.blue())))


def focused_key(qtbot, selected):
    host = QWidget()
    qtbot.addWidget(host)
    key = StepKey(1, 0, host)
    key.set_concert_state(ConcertState.UPCOMING, animations=False)
    key.resize(80, key.heightForWidth(80))
    key.set_selected(selected)
    host.show()
    host.activateWindow()
    qtbot.waitExposed(host)
    key.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(key.hasFocus)
    return host, key


def test_focus_ring_stays_whole_over_open_sheet_underline(qtbot, qapp):
    """2.9 (C1) : avec le focus, le filet crème passe à l'intérieur de l'anneau, qui reste continu."""
    from scenix16.ui.widgets.step_key import RING_OFFSET
    _host, key = focused_key(qtbot, selected=True)
    b = key.body_rect()
    for x in (b.center().x(), b.left() + b.width() * 0.3, b.right() - b.width() * 0.3):
        assert pixel(key, x, b.bottom() + RING_OFFSET).name() == t.BRAND.lower()   # anneau intact
        assert near(pixel(key, x, b.bottom() + 1), t.SILK)                          # crème visible


def test_open_sheet_underline_unchanged_without_focus(make_key):
    from scenix16.ui.widgets.step_key import UNDERLINE, UNDERLINE_GAP
    key = make_key(ConcertState.UPCOMING)
    key.set_selected(True)
    b = key.body_rect()
    for x in (b.center().x(), b.left() + b.width() * 0.3, b.right() - b.width() * 0.3):
        assert pixel(key, x, b.bottom() + UNDERLINE_GAP + UNDERLINE / 2).name() == t.SILK.lower()


def test_hover_brightens(make_key):
    key = make_key(ConcertState.UPCOMING, group=0)
    before = body_sample(key)
    key.hovered = True
    key.update()
    after = body_sample(key)
    assert after.valueF() >= before.valueF() and after != before
