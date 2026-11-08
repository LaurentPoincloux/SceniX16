"""Onglets de banques (D44 à D47, arbitrages 2, 3, 4 et 8 de l'incrément 2.6)."""

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QKeyEvent

from scenix16.ui.dashboard.bank_tabs import BankTabs
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.widgets.bank_tab import BODY_HEIGHT, MARGIN, MIN_BODY_WIDTH, BankTab


@pytest.fixture
def tabs(qtbot, qapp):
    fonts.load_fonts()
    row = BankTabs()
    qtbot.addWidget(row)
    row.resize(700, row.sizeHint().height())
    row.set_tabs([16, 4] + [0] * 6, 0)
    row.show()
    qtbot.waitExposed(row)
    return row


def pixels(widget):
    image = widget.grab().toImage()
    return {QColor(image.pixel(x, y)).name() for x in range(image.width()) for y in range(image.height())}


# --- onglet seul -----------------------------------------------------------------

def test_tab_dimensions_and_label(qtbot, qapp):
    fonts.load_fonts()
    tab = BankTab(1)
    qtbot.addWidget(tab)
    assert tab.text() == "B"
    assert tab.sizeHint().height() == BODY_HEIGHT + 2 * MARGIN
    assert tab.sizeHint().width() >= MIN_BODY_WIDTH + 2 * MARGIN
    assert BankTab(26).sizeHint().width() > tab.sizeHint().width()          # « AA » plus large


def test_tab_states_and_accessible_names(qtbot, qapp):
    tab = BankTab(1)
    qtbot.addWidget(tab)
    tab.set_state(False, 4)
    assert tab.isEnabled() and tab.accessibleName() == "Banque B : 4 concerts"
    tab.set_state(False, 0)
    assert not tab.isEnabled() and tab.accessibleName() == "Banque B : vide"
    tab.set_state(True, 0)                                       # A dans l'état vide (arbitrage 8)
    assert tab.selected and not tab.isEnabled()


def test_selection_and_focus_are_distinct(tabs, qtbot):
    a, b = tabs.tab(0), tabs.tab(1)
    tabs.activateWindow()
    b.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(b.hasFocus)
    selected_px, focused_px = pixels(a), pixels(b)
    assert t.BANK_ON_BG.lower() in selected_px                  # allumé (D67, v0.44)
    assert t.SILK.lower() not in selected_px                     # sans filet crème
    assert t.BRAND.lower() not in selected_px
    assert t.BRAND.lower() in focused_px and t.BANK_ON_BG.lower() not in focused_px   # focus seul
    assert t.BANK_OFF_BG.lower() in focused_px                   # B reste éteinte
    a.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(a.hasFocus)
    both = pixels(a)
    assert {t.BRAND.lower(), t.BANK_ON_BG.lower()} <= both       # allumé et focus cumulables


def test_empty_tab_is_inactive(tabs, qtbot):
    c = tabs.tab(2)
    requests = []
    tabs.bank_requested.connect(requests.append)
    assert not c.isEnabled() and c.focusPolicy() == Qt.NoFocus
    qtbot.mouseClick(c, Qt.LeftButton)
    assert requests == []


def test_click_occupied_tab_requests_bank(tabs, qtbot):
    requests = []
    tabs.bank_requested.connect(requests.append)
    qtbot.mouseClick(tabs.tab(1), Qt.LeftButton)
    assert requests == [1]
    assert tabs.selected == 0                                    # la page décide, puis renvoie


def test_enter_and_space_select_held_enter_once(tabs, qtbot):
    requests = []
    tabs.bank_requested.connect(requests.append)
    b = tabs.tab(1)
    b.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "", False))
    for _ in range(4):
        b.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "", True))
    assert requests == [1]
    qtbot.keyClick(b, Qt.Key_Space)
    assert requests == [1, 1]


# --- rangée ------------------------------------------------------------------------

def test_a_to_h_always_then_only_occupied(tabs):
    assert [t_.text() for t_ in tabs.visible_tabs()] == list("ABCDEFGH")
    tabs.set_tabs([16] * 9 + [3], 0)
    assert [t_.text() for t_ in tabs.visible_tabs()] == list("ABCDEFGHIJ")
    tabs.set_tabs([5] + [0] * 7, 0)
    assert len(tabs.visible_tabs()) == 8


def test_single_tab_stop_on_selected_tab(tabs):
    tabs.set_tabs([16, 16, 2] + [0] * 5, 1)
    policies = [t_.focusPolicy() for t_ in tabs.visible_tabs()]
    assert policies[1] == Qt.TabFocus
    assert all(p == Qt.NoFocus for i, p in enumerate(policies) if i != 1)


def test_arrows_move_focus_without_selecting_or_wrapping(tabs, qtbot):
    tabs.set_tabs([16, 16, 2] + [0] * 5, 0)
    requests = []
    tabs.bank_requested.connect(requests.append)
    tabs.activateWindow()
    tabs.tab(0).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(tabs.tab(0).hasFocus)
    qtbot.keyClick(tabs.tab(0), Qt.Key_Right)
    assert tabs.tab(1).hasFocus()
    qtbot.keyClick(tabs.tab(1), Qt.Key_Right)
    assert tabs.tab(2).hasFocus()
    qtbot.keyClick(tabs.tab(2), Qt.Key_Right)                    # D à H vides : rien
    assert tabs.tab(2).hasFocus()
    qtbot.keyClick(tabs.tab(2), Qt.Key_Left)
    qtbot.keyClick(tabs.tab(1), Qt.Key_Left)
    qtbot.keyClick(tabs.tab(0), Qt.Key_Left)                     # pas de bouclage
    assert tabs.tab(0).hasFocus()
    assert requests == [] and tabs.selected == 0                 # le focus ne sélectionne pas


def test_focus_kept_when_selection_follows(tabs, qtbot):
    tabs.activateWindow()
    tabs.tab(1).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(tabs.tab(1).hasFocus)
    tabs.set_tabs([16, 4] + [0] * 6, 1)                          # la page sélectionne B
    assert tabs.tab(1).hasFocus() and tabs.tab(1).selected
    assert tabs.tab(1).focusPolicy() == Qt.TabFocus


@pytest.mark.parametrize("width", [760, 1000])
def test_overflow_arrows_only_when_needed(qtbot, qapp, width):
    fonts.load_fonts()
    row = BankTabs()
    qtbot.addWidget(row)
    row.resize(width, row.sizeHint().height())
    row.show()
    qtbot.waitExposed(row)
    row.set_tabs([16, 4] + [0] * 6, 0)
    qtbot.wait(10)
    assert not row.overflowing() and not row.prev_arrow.isVisible()
    row.set_tabs([16] * 26 + [1], 26)                            # 27 banques : A … AA
    qtbot.wait(10)
    assert row.overflowing() and row.prev_arrow.isVisible() and row.next_arrow.isVisible()
    assert row.prev_arrow.focusPolicy() == Qt.NoFocus
    # la banque sélectionnée (AA) est rendue visible
    tab = row.tab(26)
    left = tab.mapTo(row.scroll.viewport(), tab.rect().topLeft()).x()
    assert 0 <= left and left + tab.width() <= row.scroll.viewport().width()
    before = row.scroll.horizontalScrollBar().value()
    qtbot.mouseClick(row.prev_arrow, Qt.LeftButton)
    assert row.scroll.horizontalScrollBar().value() < before


def test_left_inset_aligns_first_tab(tabs):
    tabs.set_left_inset(12)
    assert tabs.strip_layout.contentsMargins().left() == 12


# --- rendu des boutons de banque (D67, révisé en v0.44 : ON/OFF) ----------------------------------

def test_rest_button_has_discreet_relief_and_empty_is_flat(tabs):
    from scenix16.ui.widgets.bank_tab import MARGIN as M
    b, c = tabs.tab(1), tabs.tab(2)                       # B occupée au repos, C vide
    body = b.body_rect()
    image = b.grab().toImage()
    r = image.devicePixelRatio()
    top = QColor(image.pixel(round(body.center().x() * r), int((body.top() + 1) * r)))
    fill = QColor(image.pixel(round(body.center().x() * r), round(body.center().y() * r - 6 * r)))
    assert top.lightness() > fill.lightness()             # liseré clair en haut
    assert t.BANK_OFF_BG.lower() in pixels(b)                   # éteint : vert sombre
    for color in (t.BANK_OFF_BG, t.BANK_ON_BG, t.CELL):           # vide : plat, inchangé
        assert color.lower() not in pixels(c)


def test_on_off_colors_letters_and_luminance(tabs):
    from scenix16.ui.widgets.bank_tab import MARGIN as M
    a, b = tabs.tab(0), tabs.tab(1)                               # A allumée, B éteinte
    center = lambda tab: QColor(tab.grab().toImage().pixel(M + 3, M + 8))
    on, off = center(a), center(b)
    assert on.name() == t.BANK_ON_BG.lower() and off.name() == t.BANK_OFF_BG.lower()
    assert on.lightness() - off.lightness() > 60                  # différence de luminosité, pas de teinte seule
    assert t.BANK_ON_TEXT.lower() in pixels(a)                    # lettre en encre sur le bouton allumé
    assert t.BANK_OFF_TEXT.lower() in pixels(b)
    assert a.text() == "A" and b.text() == "B"                    # aucun texte ON ou OFF


def test_off_button_hover_is_lighter_green(tabs, qtbot):
    b = tabs.tab(1)
    b.setAttribute(Qt.WA_UnderMouse, True)
    assert t.BANK_OFF_HOVER.lower() in pixels(b)
    b.setAttribute(Qt.WA_UnderMouse, False)


# --- dashboard vide : A reste sélectionnée sans être active (arbitrage 8 de 2.6, D67 v0.44) ----------

def test_empty_dashboard_bank_a_lit_but_inactive(qtbot, qapp):
    from scenix16.domain.dashboard import MIN_TABS
    from scenix16.ui.widgets.bank_tab import MARGIN as M
    fonts.load_fonts()
    row = BankTabs()
    qtbot.addWidget(row)
    row.resize(700, row.sizeHint().height())
    row.set_tabs([0] * MIN_TABS, 0)                        # base vide
    row.show()
    qtbot.waitExposed(row)
    requests = []
    row.bank_requested.connect(requests.append)
    a = row.tab(0)
    # A : allumée (vert lumineux), car sélectionnée…
    assert a.selected
    assert QColor(a.grab().toImage().pixel(M + 3, M + 8)).name() == t.BANK_ON_BG.lower()
    assert t.BANK_ON_TEXT.lower() in pixels(a)
    # … mais inactive et non focusable
    assert not a.isEnabled() and a.focusPolicy() == Qt.NoFocus
    a.setFocus(Qt.TabFocusReason)
    assert not a.hasFocus()
    qtbot.mouseClick(a, Qt.LeftButton)
    assert requests == []
    assert a.accessibleName() == "Banque A : vide"
    # B à H : banques vides inchangées (plates, pointillés, atténuées, inactives)
    for i in range(1, MIN_TABS):
        tab = row.tab(i)
        colors = pixels(tab)
        assert not tab.selected and not tab.isEnabled()
        for color in (t.BANK_ON_BG, t.BANK_OFF_BG, t.BANK_OFF_HOVER, t.CELL):
            assert color.lower() not in colors
        assert tab.focusPolicy() == Qt.NoFocus


def test_empty_bank_rendering_identical_whatever_the_position(qtbot, qapp):
    """Une banque vide non sélectionnée a le même rendu, qu'il y ait des concerts ailleurs ou non."""
    from scenix16.domain.dashboard import MIN_TABS
    fonts.load_fonts()
    empty_row, mixed_row = BankTabs(), BankTabs()
    for row, counts in ((empty_row, [0] * MIN_TABS), (mixed_row, [16, 4] + [0] * (MIN_TABS - 2))):
        qtbot.addWidget(row)
        row.resize(700, row.sizeHint().height())
        row.set_tabs(counts, 0)
        row.show()
        qtbot.waitExposed(row)
    assert empty_row.tab(4).grab().toImage() == mixed_row.tab(4).grab().toImage()   # E vide dans les deux cas


def test_first_concert_restores_normal_rules(qtbot, qapp):
    from scenix16.domain.dashboard import MIN_TABS
    fonts.load_fonts()
    row = BankTabs()
    qtbot.addWidget(row)
    row.resize(700, row.sizeHint().height())
    row.set_tabs([0] * MIN_TABS, 0)
    row.show()
    qtbot.waitExposed(row)
    row.set_tabs([3] + [0] * (MIN_TABS - 1), 0)             # A reçoit des concerts
    a = row.tab(0)
    assert a.isEnabled() and a.selected and t.BANK_ON_BG.lower() in pixels(a)
    row.activateWindow()
    a.setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(a.hasFocus)
    assert {t.BRAND.lower(), t.BANK_ON_BG.lower()} <= pixels(a)   # allumée et focus clavier
    assert not row.tab(1).isEnabled() and t.BANK_OFF_BG.lower() not in pixels(row.tab(1))
