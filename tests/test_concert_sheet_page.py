"""Écran de la fiche en consultation (incrément 2.7b — D8, D16, D38, D52, D69, Design Book v0.47).

La page est testée seule : son ouverture et son retour depuis le dashboard relèvent de 2.7c.
Base fictive dans un dossier temporaire ; la base réelle n'est jamais ouverte ici.
"""

from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from scenix16.services.concert_service import load_concert_sheet
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path
from scenix16.ui.concert.sheet_page import (COPIED_MESSAGE, ConcertSheetPage)
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet

NOW = datetime(2026, 11, 7, 20, 30)
TRACKS = [("THE PASSENGER", "G#", "-/-", "-/-", "OFF"), ("MY DIGNITY", "F", "A62", "RAM-D 75", "ON"),
          ("(HAVE WE) LOST IT ALL", "F#/G#/A#", None, "RAM-D 72", "OFF"), ("EYES WITHOUT A FACE", "", "  ", None, None),
          ("A VERY LONG TITLE THAT GOES ON AND ON — EXTENDED NIGHT VERSION WITH REPRISE AND CODA", "E", "B12",
           "RAM-D 74", "ON")]


@pytest.fixture
def userdata(tmp_path):
    folder = tmp_path / "UserData"
    check_writable(folder)
    conn = connect(database_path(folder))
    with conn:
        conn.executemany("INSERT INTO tracks(position, title, key, mk, virus, virus_status) VALUES (?,?,?,?,?,?)",
                         [(i + 1, *t) for i, t in enumerate(TRACKS)])
        for i in range(5):
            conn.execute("INSERT INTO setlists(name, concert_date, venue) VALUES (?,?,?)",
                         (f"Concert {i + 1:02d}", (date(2026, 11, 7) + timedelta(days=3 * i)).isoformat(), f"Salle {i + 1}"))
        conn.execute("UPDATE setlists SET name = 'Le Kiosque', venue = ? WHERE id = 3", ("Le Kiosque \nChauvigny (86)",))
        conn.executemany("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (3, ?, ?)",
                         [(p, (p - 1) % len(TRACKS) + 1) for p in range(1, 41)])            # 40 titres
        conn.execute("UPDATE setlists SET address = ?, organizer = ?, notes = ? WHERE id = 3",
                     ("  Place du Marché\n86300 Chauvigny  ", "Les Nuits Romanes", "Loges à l'étage."))
        conn.executemany("INSERT INTO setlist_contacts(setlist_id, position, name, role, phone, email) VALUES (3,?,?,?,?,?)",
                         [(1, "Alice", "Régie", "06 00 00 00 01", "alice@exemple.fr"), (2, "Bob", None, None, None)])
        conn.execute("INSERT INTO setlist_schedule(setlist_id, position, label, time) VALUES (3, 1, 'Passage', '21:30')")
        conn.execute("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (1, 1, 2)")
    conn.close()
    return folder


@pytest.fixture
def page(qtbot, qapp, userdata):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    widget = ConcertSheetPage()
    qtbot.addWidget(widget)
    widget.resize(900, 640)
    widget.set_sheet(load_concert_sheet(userdata, 3, NOW))
    widget.show()
    qtbot.waitExposed(widget)
    return widget


# --- en-tête -----------------------------------------------------------------------------------------

def test_header(page):
    assert page.heading_label.text() == "Touche A03 · Consultation"
    assert page.name_label.text() == "Le Kiosque"
    assert page.meta_label.text() == "Le Kiosque · Chauvigny (86) · 13/11/26 · 40 titres"   # lignes jointes (2.9)
    assert "\n" not in page.meta_label.text() and "  " not in page.meta_label.text()


def test_edit_and_more_visible_but_inactive(page):
    for button, text in ((page.edit_button, "Modifier"), (page.more_button, "⋯")):
        assert button.text() == text and button.isVisible() and not button.isEnabled()   # D69
        assert button.focusPolicy() == Qt.NoFocus


def test_no_project_nor_visual(page):
    texts = {label.text() for label in page.findChildren(QLabel)}
    assert "Visuel" not in texts                                                      # D69 (8)
    assert not page.findChildren(QLabel, "SheetVisual") and not page.findChildren(QLabel, "SheetProject")


def test_back_button_only_emits_its_signal(page, qtbot):
    assert page.back_button.text() == "← CONCERTS"     # v0.48
    with qtbot.waitSignal(page.back_requested, timeout=500):
        page.back_button.click()


# --- setlist ------------------------------------------------------------------------------------------

def cells(row):
    return tuple(c.text() for c in row.cells)


def test_all_forty_titles_with_stored_values(page):
    assert len(page.track_rows) == 40                                                # sans troncature
    assert cells(page.track_rows[0]) == ("01", "THE PASSENGER", "G#", "-/-", "-/-")
    assert page.track_rows[0].status.text() == "OFF"
    assert cells(page.track_rows[1]) == ("02", "MY DIGNITY", "F", "A62", "RAM-D 75")
    assert page.track_rows[1].status.text() == "ON" and page.track_rows[1].status.objectName() == "VirusStatusOn"
    assert cells(page.track_rows[2])[3] == "—"                                       # NULL → —
    assert cells(page.track_rows[3])[2:] == ("—", "—", "—")                          # vide, espaces, NULL
    assert page.track_rows[3].status.text() == "—"
    assert cells(page.track_rows[39])[0] == "40"
    assert [cells(r)[1] for r in page.track_rows[:6]] == [t[0] for t in TRACKS] + [TRACKS[0][0]]   # répétition


def test_long_title_wraps_instead_of_widening(page):
    title = page.track_rows[4].cells[1]
    assert title.wordWrap() and title.width() < title.fontMetrics().horizontalAdvance(title.text())


def test_vertical_scroll_only(page, qtbot):
    for width in (700, 900, 1200):
        page.resize(width, 600)
        qtbot.wait(30)
        assert page.scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert not page.scroll.horizontalScrollBar().isVisible()
        assert page.canvas.width() <= page.scroll.viewport().width()
        assert page.scroll.verticalScrollBar().maximum() > 0                         # la fiche défile


# --- infos pratiques ------------------------------------------------------------------------------------

def test_practical_info_collapsed_by_default_and_not_remembered(page, userdata):
    assert page.info_block.isVisible() and not page.info_expanded()                  # replié (D69)
    page.info_toggle.setChecked(True)
    assert page.info_expanded()
    page.set_sheet(load_concert_sheet(userdata, 3, NOW))                             # nouvelle ouverture
    assert not page.info_expanded()                                                  # sans mémorisation


def test_practical_info_hidden_when_empty(page, userdata):
    page.set_sheet(load_concert_sheet(userdata, 1, NOW))
    assert page.info_block is None
    assert all(not w.isVisible() for w in page.findChildren(type(page.info_toggle), "SheetInfoToggle"))


def test_copy_address_with_discreet_confirmation(page, qtbot):
    page.info_toggle.setChecked(True)
    QGuiApplication.clipboard().clear()
    assert not page.copied_label.isVisible()
    page.copy_button.click()
    assert QGuiApplication.clipboard().text() == "Place du Marché\n86300 Chauvigny"
    assert page.copied_label.isVisible() and page.copied_label.text() == COPIED_MESSAGE
    page._copied_timer.timeout.emit()                                                # fin du délai
    assert not page.copied_label.isVisible()


def card_texts(card):
    return [label.text() for label in card.findChildren(QLabel)]


def test_contacts_selectable_text_without_links(page):
    page.info_toggle.setChecked(True)
    assert [card_texts(c) for c in page.contact_cards] == [
        ["Alice", "Régie", "06 00 00 00 01", "alice@exemple.fr"], ["Bob"]]   # une carte par contact (2.9)
    for card in page.contact_cards:
        for label in card.findChildren(QLabel):
            assert label.textInteractionFlags() & Qt.TextSelectableByMouse
            assert label.textFormat() == Qt.PlainText and not label.openExternalLinks()


def test_clicks_never_show_the_keyboard_focus_ring(page, qtbot):
    for widget in (page.info_toggle, page.copy_button):
        assert widget.focusPolicy() == Qt.TabFocus                                   # clic : pas de focus


def test_no_sheet_shows_nothing(page):
    page.set_sheet(None)
    assert page.sheet is None and page.card is None


# --- présentation des infos pratiques (2.9) -------------------------------------------------------------

def test_summary_visible_only_when_collapsed(page):
    assert page.info_summary.text() == "Passage 21:30 · 2 contacts"
    assert page.info_summary.isVisible()
    assert page.info_toggle.accessibleName() == "Infos pratiques, replié : Passage 21:30 · 2 contacts"
    page.info_toggle.setChecked(True)
    assert not page.info_summary.isVisible()
    assert page.info_toggle.accessibleName() == "Infos pratiques, déplié"
    page.info_toggle.setChecked(False)
    assert page.info_summary.isVisible()


def test_no_summary_without_schedule_or_contact(page, userdata):
    conn = connect(database_path(userdata))
    with conn:
        conn.execute("DELETE FROM setlist_contacts WHERE setlist_id = 3")
        conn.execute("DELETE FROM setlist_schedule WHERE setlist_id = 3")
    conn.close()
    page.set_sheet(load_concert_sheet(userdata, 3, NOW))
    assert page.info_block is not None and page.info_summary.text() == ""
    assert not page.info_summary.isVisible()
    assert page.contact_cards == [] and page.schedule_times == []


def test_two_columns_on_wide_sheet_one_on_narrow(page, qtbot):
    page.info_toggle.setChecked(True)
    page.resize(1100, 640)
    qtbot.waitUntil(page.info_two_columns)
    columns = page.info_body.findChildren(QWidget, "SheetInfoColumn")
    assert len(columns) == 2 and columns[0].geometry().top() == columns[1].geometry().top()
    page.resize(640, 640)
    qtbot.waitUntil(lambda: not page.info_two_columns())
    assert columns[1].geometry().top() > columns[0].geometry().bottom()        # empilées


def test_schedule_times_in_an_aligned_column(page):
    page.info_toggle.setChecked(True)
    assert [label.text() for label in page.schedule_times] == ["21:30"]
    time = page.schedule_times[0]
    assert time.objectName() == "SheetScheduleTime" and time.alignment() & Qt.AlignRight


def test_copy_button_next_to_the_address_title(page):
    page.info_toggle.setChecked(True)
    title = next(label for label in page.info_body.findChildren(QLabel) if label.text() == "ADRESSE")
    button = page.copy_button.geometry()
    assert abs(button.center().y() - title.geometry().center().y()) <= 4      # même ligne
    assert button.left() - title.geometry().right() < 40                       # juste à côté
    assert page.address_label.text() == "Place du Marché\n86300 Chauvigny"


def test_section_titles_and_notes_panel(page):
    page.info_toggle.setChecked(True)
    titles = [label.text() for label in page.info_body.findChildren(QLabel, "SheetInfoLabel")]
    assert titles == ["ADRESSE", "ORGANISATEUR", "NOTES", "HORAIRES", "CONTACTS"]
    assert page.notes_label.text() == "Loges à l'étage."
    assert page.notes_label.parent().objectName() == "SheetNotes"


def test_partial_information_shows_only_its_sections(page, userdata):
    conn = connect(database_path(userdata))
    with conn:
        conn.execute("UPDATE setlists SET address = '1 rue Exemple', organizer = NULL, notes = NULL WHERE id = 2")
    conn.close()
    page.set_sheet(load_concert_sheet(userdata, 2, NOW))
    page.info_toggle.setChecked(True)
    titles = [label.text() for label in page.info_body.findChildren(QLabel, "SheetInfoLabel")]
    assert titles == ["ADRESSE"] and page.info_summary.text() == ""
    assert len(page.info_body.findChildren(QWidget, "SheetInfoColumn")) == 1
