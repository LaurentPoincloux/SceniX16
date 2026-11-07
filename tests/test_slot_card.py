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
    assert border.name() == t.BRAND.lower()                     # bordure orange


def test_upcoming_border_is_neutral(make_card):
    card = make_card(dkey(ConcertState.UPCOMING))
    c = card.card_rect()
    assert pixel(card, c.center().x(), c.bottom() - 0.6).name() != t.BRAND.lower()


@pytest.mark.parametrize("group", [0, 1, 2, 3])
def test_group_marker_color(make_card, group):
    card = make_card(dkey(), group=group)
    c = card.card_rect()
    assert pixel(card, c.center().x(), c.top() + 1).name() == GROUP_COLORS[group].lower()


def test_today_pulse_or_fixed(make_card):
    assert make_card(dkey(ConcertState.TODAY, countdown=0), animations=True).pulse_running()
    fixed = make_card(dkey(ConcertState.TODAY, countdown=0), animations=False)
    assert not fixed.pulse_running()


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


def test_long_name_elided_with_full_tooltip(make_card):
    long_name = "Festival international des musiques synthétiques et électroniques"
    card = make_card(dkey(name=long_name), width=180)
    assert card.toolTip() == long_name


def test_highlight_ring(make_card):
    card = make_card(dkey())
    card.set_highlighted(True)
    c = card.card_rect()
    assert pixel(card, c.center().x(), c.top() - 3).name() == t.SILK.lower()


def test_height_follows_fonts(make_card):
    card = make_card(dkey())
    assert card.height() >= 104 + 2 * MARGIN
