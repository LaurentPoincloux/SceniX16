"""Composant Emplacement : états, repère de groupe, textes, INIT."""

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from scenix16.domain.dashboard import ConcertState, DashboardKey
from scenix16.domain.models import ConcertSummary, SetlistStatus
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.widgets.slot_card import MARGIN, SlotCard
from scenix16.ui.widgets.step_key import GROUP_COLORS


def dkey(state=ConcertState.UPCOMING, number=1, name="Le Kiosque",
         venue="Le Kiosque \nChauvigny (86)", countdown=12):
    c = ConcertSummary(number, name, date(2026, 12, 1), venue, SetlistStatus.MAINTAINED, 26)
    return DashboardKey(number, c, state, countdown, (number - 1) % 16 // 4)


@pytest.fixture
def make_card(qtbot, qapp):
    fonts.load_fonts()

    def make(key=None, number=1, group=0, width=220, animations=False):
        card = SlotCard(number, group)
        qtbot.addWidget(card)
        card.set_concert(key, animations=animations)
        card.resize(width, card.sizeHint().height())
        card.show()
        qtbot.waitExposed(card)
        return card
    return make


def pixel(widget, x, y):
    image = widget.grab().toImage()
    r = image.devicePixelRatio()
    return QColor(image.pixel(round(x * r), round(y * r)))


def colors(widget):
    image = widget.grab().toImage()
    return {QColor(image.pixel(x, y)).name() for x in range(image.width()) for y in range(image.height())}


def test_texts_and_tag(make_card):
    card = make_card(dkey(ConcertState.UPCOMING, countdown=12))
    assert card.name_text() == "Le Kiosque"
    # arbitrage C : le retour à la ligne devient une espace (l'espace d'origine est conservée)
    assert card.venue_text() == "Le Kiosque  Chauvigny (86)"
    assert "\n" not in card.venue_text()
    assert card.key.concert.venue == "Le Kiosque \nChauvigny (86)"  # donnée intacte
    assert card.foot_text() == "J-12"
    assert card.tag_text() == "À VENIR"


@pytest.mark.parametrize("state, tag, foot", [
    (ConcertState.NEXT, "PROCHAIN", "J-12"),
    (ConcertState.TODAY, "AUJOURD'HUI", "Ce soir"),
])
def test_emphasized_states(make_card, state, tag, foot):
    card = make_card(dkey(state, countdown=0 if state is ConcertState.TODAY else 12))
    assert card.tag_text() == tag and card.foot_text() == foot
    c = card.card_rect()
    border = pixel(card, c.center().x(), c.bottom() - 1)
    if state is ConcertState.NEXT:
        assert border.name() == t.BRAND.lower()                 # « Prochain » : bordure orange
    else:
        assert border.name() != t.BRAND.lower()                 # « Aujourd'hui » : plus de bordure (v0.46)
        assert pixel(card, c.center().x(), c.bottom() - 0.6).name() != t.BRAND.lower()
    assert t.BRAND.lower() in colors(card)                      # étiquette orange conservée
    assert card.state in (ConcertState.NEXT, ConcertState.TODAY)


def test_today_card_neutral_border_but_ringed_dot(make_card):
    today = make_card(dkey(ConcertState.TODAY, countdown=0))
    upcoming = make_card(dkey(ConcertState.UPCOMING))
    c = today.card_rect()
    edge = (c.center().x(), c.bottom() - 0.6)
    assert pixel(today, *edge).name() == pixel(upcoming, *edge).name()   # même bordure qu'une carte à venir
    assert t.LED_ON.lower() in colors(today) and not today.pulse_running()   # point cerclé fixe


def test_upcoming_border_is_neutral(make_card):
    card = make_card(dkey(ConcertState.UPCOMING))
    c = card.card_rect()
    assert pixel(card, c.center().x(), c.bottom() - 0.6).name() != t.BRAND.lower()


def blend(top, bottom, alpha):
    a, b = QColor(top), QColor(bottom)
    return tuple(round(x * alpha + y * (1 - alpha)) for x, y in
                 ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue())))


@pytest.mark.parametrize("group", [0, 1, 2, 3])
def test_group_marker_color(make_card, group):
    """D63 : repère à 70 % au repos, à pleine intensité au survol ou en paire."""
    from scenix16.ui.widgets.slot_card import MARKER_REST
    card = make_card(dkey(), group=group)
    c = card.card_rect()
    rest = pixel(card, c.center().x(), c.top() + 1)
    expected = blend(GROUP_COLORS[group], t.CELL, MARKER_REST)
    assert all(abs(v - e) <= 3 for v, e in zip((rest.red(), rest.green(), rest.blue()), expected))
    card.set_highlighted(True)
    assert pixel(card, c.center().x(), c.top() + 1).name() == GROUP_COLORS[group].lower()


def test_today_fixed_and_selection_pulses(make_card):
    """D11, D63 (v0.45) : le jour ne pulse plus de lui-même ; la carte sélectionnée pulse."""
    today = make_card(dkey(ConcertState.TODAY, countdown=0), animations=True)
    assert not today.pulse_running()
    upcoming = make_card(dkey(ConcertState.UPCOMING), animations=True)
    upcoming.set_pulsing(True, animations=True)
    assert upcoming.pulsing and upcoming.pulse_running()
    fixed = make_card(dkey(ConcertState.UPCOMING), animations=False)
    fixed.set_pulsing(True, animations=False)
    assert not fixed.pulse_running()
    init = make_card(None)
    init.set_pulsing(True, animations=True)
    assert not init.pulse_running()


def test_init_card(make_card, qtbot):
    card = make_card(None, number=7, group=1)
    assert card.is_init and card.name_text() == "INIT"
    assert not card.isEnabled() and card.focusPolicy() == Qt.NoFocus
    clicks = []
    card.clicked.connect(lambda: clicks.append(1))
    qtbot.mouseClick(card, Qt.LeftButton)
    assert clicks == []
    c = card.card_rect()
    inside = pixel(card, c.center().x(), c.center().y() + 20)
    assert inside.name() != QColor(t.CELL).name()              # pas de fond plein
    card.set_highlighted(True)
    card.set_selected(True)
    assert not card.highlighted and not card.selected


def test_active_card_click_and_tab_focus(make_card, qtbot):
    card = make_card(dkey())
    clicks = []
    card.clicked.connect(lambda: clicks.append(1))
    qtbot.mouseClick(card, Qt.LeftButton)
    assert clicks == [1]
    assert card.focusPolicy() == Qt.TabFocus


def test_long_name_elided_without_tooltip(make_card):
    """D64 : plus d'info-bulle ; le nom complet est dans l'aperçu et la description accessible."""
    long_name = "Festival international des musiques synthétiques et électroniques"
    card = make_card(dkey(name=long_name), width=180)
    assert card.toolTip() == ""
    assert card.accessibleName().endswith(long_name)


def test_states_raised_selected_no_cream_ring(make_card):
    """D63 : survol = fond relevé ; sélection = fond relevé + bordure du groupe ; aucun anneau crème."""
    card = make_card(dkey())
    c = card.card_rect()
    inside = (c.left() + 6, c.center().y())
    assert pixel(card, *inside).name() == t.CELL.lower()
    card.set_highlighted(True)
    assert pixel(card, *inside).name() == t.RAISED.lower()
    assert pixel(card, c.center().x(), c.top() - 3).name() != t.SILK.lower()
    card.set_highlighted(False)
    card.set_selected(True)
    assert pixel(card, *inside).name() == t.RAISED.lower()
    border = pixel(card, c.left() + 0.5, c.center().y())
    assert border.red() > border.blue() + 40                         # bordure rouge du groupe 1


def test_height_follows_fonts(make_card):
    card = make_card(dkey())
    assert card.height() >= 104 + 2 * MARGIN
