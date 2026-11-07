"""Bouton de tri (section 06, D1, D12 ; incrément 2.5)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from scenix16.domain.dashboard import SortOrder
from scenix16.ui.theme import fonts, tokens as t
from scenix16.ui.widgets.sort_button import BODY_HEIGHT, MARGIN, SortButton


@pytest.fixture
def button(qtbot, qapp):
    fonts.load_fonts()
    b = SortButton()
    qtbot.addWidget(b)
    b.resize(b.sizeHint())
    b.show()
    qtbot.waitExposed(b)
    return b


def test_default_order_and_texts(button):
    assert button.order is SortOrder.OLDEST_FIRST
    assert button.text() == "Plus ancien d'abord"                 # D12
    assert button.display_text() == "PLUS ANCIEN D'ABORD"         # capitales de la maquette
    assert button.arrow_up
    assert button.accessibleName() == \
        "Classement « Plus ancien d'abord ». Activer pour passer à « Plus récent d'abord »."


def test_set_order_updates_label_arrow_and_accessible_name(button):
    button.set_order(SortOrder.NEWEST_FIRST)
    assert button.display_text() == "PLUS RÉCENT D'ABORD"
    assert not button.arrow_up
    assert button.accessibleName().startswith("Classement « Plus récent d'abord »")


def test_size_is_stable_between_orders(button):
    size = button.sizeHint()
    button.set_order(SortOrder.NEWEST_FIRST)
    assert button.sizeHint() == size
    assert size.height() == BODY_HEIGHT + 2 * MARGIN
    assert button.body_rect().height() == BODY_HEIGHT


def test_click_emits_without_changing_order_itself(button, qtbot):
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    qtbot.mouseClick(button, Qt.LeftButton)
    assert clicks == [1]
    assert button.order is SortOrder.OLDEST_FIRST                 # l'appelant décide (set_order)


def test_keyboard_space_and_enter(button, qtbot):
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    assert button.focusPolicy() == Qt.TabFocus
    qtbot.keyClick(button, Qt.Key_Return)
    qtbot.keyClick(button, Qt.Key_Enter)
    qtbot.keyClick(button, Qt.Key_Space)
    assert clicks == [1, 1, 1]


def test_arrow_painted_in_brand_orange(button):
    image = button.grab().toImage()
    found = any(QColor(image.pixel(x, y)).name() == t.BRAND.lower()
                for x in range(image.width()) for y in range(image.height()))
    assert found


# --- correction de la revue technique de 2.5 (défaut 4) ----------------------------

def test_held_enter_activates_only_once(button):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    for key in (Qt.Key_Return, Qt.Key_Enter):
        clicks.clear()
        button.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, "", False))
        for _ in range(5):                                     # répétition automatique du clavier
            event = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, "", True)
            button.keyPressEvent(event)
            assert event.isAccepted()
        assert clicks == [1]
