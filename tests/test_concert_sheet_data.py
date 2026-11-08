"""Données de la fiche du concert (incrément 2.7a — D16, D45, D69, Design Book v0.47).

Base fictive dans un dossier temporaire : la base réelle n'est jamais ouverte ici.
"""

import hashlib
from datetime import date, datetime, timedelta

import pytest

from scenix16.domain.dashboard import ConcertState, SortOrder, build_dashboard
from scenix16.domain.models import Contact, ScheduleItem, SetlistStatus
from scenix16.services import concert_service as cs
from scenix16.services import dashboard_service as ds
from scenix16.storage import repository
from scenix16.storage.database import connect
from scenix16.storage.userdata import check_writable, database_path

NOW = datetime(2026, 11, 7, 20, 0)
START = date(2026, 11, 7)

TRACKS = [  # titre, KEY, MK, VIRUS|TI, statut
    ("NO SURRENDER (Intro)", "G#", "-/-", "-/-", "OFF"),
    ("MY DIGNITY", "F", "A62", "RAM-D 75", "ON"),
    ("(HAVE WE) LOST IT ALL", "F#/G#/A#", None, "RAM-D 72", "OFF"),
    ("EYES WITHOUT A FACE", "", "  ", "RAM-D 74", None),
]


@pytest.fixture
def userdata(tmp_path):
    """22 concerts à venir (le 22e en banque B), un passé, un annulé, un sans date, une fiche complète."""
    folder = tmp_path / "UserData"
    check_writable(folder)
    conn = connect(database_path(folder))
    with conn:
        conn.executemany("INSERT INTO tracks(position, title, key, mk, virus, virus_status) VALUES (?,?,?,?,?,?)",
                         [(i + 1, *t) for i, t in enumerate(TRACKS)])
        for i in range(22):                                       # id 1 à 22, tous les 3 jours
            conn.execute("INSERT INTO setlists(name, concert_date, venue) VALUES (?,?,?)",
                         (f"Concert {i + 1:02d}", (START + timedelta(days=3 * i)).isoformat(), f"Salle {i + 1}"))
        conn.execute("INSERT INTO setlists(id, name, concert_date, venue) VALUES (30, 'Passé', '2026-10-01', 'Ailleurs')")
        conn.execute("INSERT INTO setlists(id, name, concert_date, status) VALUES (31, 'Annulé', '2026-12-01', 'cancelled')")
        conn.execute("INSERT INTO setlists(id, name) VALUES (32, 'Nouvelle setlist')")
        # fiche complète : concert 2 (A02) — répétition du morceau 2 aux positions 2 et 4
        conn.execute("""UPDATE setlists SET address = ?, organizer = ?, notes = ?, venue = 'Le Kiosque'
                        WHERE id = 2""", ("12 rue des Lilas\n86300 Chauvigny", "Mairie de Chauvigny",
                                          "Loges à l'étage.\nParking derrière la salle."))
        conn.executemany("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (2, ?, ?)",
                         [(1, 1), (2, 2), (3, 3), (4, 2), (5, 4)])
        conn.executemany("INSERT INTO setlist_contacts(setlist_id, position, name, role, phone, email) "
                         "VALUES (2, ?, ?, ?, ?, ?)",
                         [(2, "Bob", "Son", None, "bob@exemple.fr"), (1, "Alice", "Régie", "06 00 00 00 00", None)])
        conn.executemany("INSERT INTO setlist_schedule(setlist_id, position, label, time) VALUES (2, ?, ?, ?)",
                         [(1, "Arrivée", "16:00"), (2, "Balance", "17:30"), (3, "Passage", "21:30")])
        # concert 22 (B06) : un seul morceau
        conn.execute("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (22, 1, 1)")
    conn.close()
    return folder


def sha(folder):
    return hashlib.sha256(database_path(folder).read_bytes()).hexdigest()


# --- repository ------------------------------------------------------------------------------------

def test_detail_keeps_order_repetitions_and_stored_values(userdata):
    conn = connect(database_path(userdata))
    try:
        detail = repository.read_concert_detail(conn, 2)
    finally:
        conn.close()
    assert [t.position for t in detail.tracks] == [1, 2, 3, 4, 5]
    assert [t.title for t in detail.tracks] == ["NO SURRENDER (Intro)", "MY DIGNITY", "(HAVE WE) LOST IT ALL",
                                                "MY DIGNITY", "EYES WITHOUT A FACE"]   # répétition conservée
    first = detail.tracks[0]
    assert (first.key, first.mk, first.virus, first.virus_status) == ("G#", "-/-", "-/-", "OFF")
    assert detail.tracks[2].mk is None and detail.tracks[4].key == "" and detail.tracks[4].mk == "  "
    assert detail.address == "12 rue des Lilas\n86300 Chauvigny"
    assert [c.name for c in detail.contacts] == ["Alice", "Bob"]              # ordre des positions
    assert detail.schedule[2] == ScheduleItem("Passage", "21:30")
    assert detail.status is SetlistStatus.MAINTAINED and detail.concert_date == START + timedelta(days=3)


def test_unknown_id_gives_no_detail(userdata):
    conn = connect(database_path(userdata))
    try:
        assert repository.read_concert_detail(conn, 999) is None
    finally:
        conn.close()


# --- service : adresse de touche (même référence que le dashboard) -------------------------------

def dashboard_address(userdata, setlist_id, now=NOW, order=SortOrder.OLDEST_FIRST):
    key = ds.load_summary(userdata, now, order).view.key_of_concert(setlist_id)
    return key.address if key else None


@pytest.mark.parametrize("order", [SortOrder.OLDEST_FIRST, SortOrder.NEWEST_FIRST])
@pytest.mark.parametrize("setlist_id", [1, 2, 16, 17, 22])
def test_key_address_is_the_dashboard_one(userdata, order, setlist_id):
    sheet = cs.load_concert_sheet(userdata, setlist_id, NOW, order)
    assert sheet.key_address == dashboard_address(userdata, setlist_id, NOW, order)


def test_key_address_examples(userdata):
    assert cs.load_concert_sheet(userdata, 2, NOW).key_address == "A02"
    assert cs.load_concert_sheet(userdata, 22, NOW).key_address == "B06"
    assert cs.load_concert_sheet(userdata, 22, NOW, SortOrder.NEWEST_FIRST).key_address == "A01"
    assert cs.load_concert_sheet(userdata, 2, NOW).heading == "Touche A02 · Consultation"


def test_key_address_follows_scenix16_day(userdata):
    # 08/11 à 5 h 59 : le concert du 07/11 est encore du jour (D10) ; à 6 h il est passé
    before = cs.load_concert_sheet(userdata, 1, datetime(2026, 11, 8, 5, 59))
    after = cs.load_concert_sheet(userdata, 1, datetime(2026, 11, 8, 6, 0))
    assert before.key_address == "A01" and before.state is ConcertState.TODAY
    assert after.key_address is None and after.state is None
    assert cs.load_concert_sheet(userdata, 2, datetime(2026, 11, 8, 6, 0)).key_address == "A01"


@pytest.mark.parametrize("setlist_id, reason", [(30, "passé"), (31, "annulé"), (32, "sans date")])
def test_concert_off_dashboard_has_no_key_address(userdata, setlist_id, reason):
    sheet = cs.load_concert_sheet(userdata, setlist_id, NOW)
    assert sheet is not None, reason
    assert sheet.key_address is None and sheet.state is None
    assert sheet.heading == "Consultation"


def test_unknown_id_missing_or_absent_database(userdata, tmp_path):
    assert cs.load_concert_sheet(userdata, 999, NOW) is None
    assert cs.load_concert_sheet(None, 1, NOW) is None
    assert cs.load_concert_sheet(tmp_path / "absent", 1, NOW) is None


# --- service : formats d'affichage --------------------------------------------------------------------

def test_sheet_tracks_stored_values_and_em_dash(userdata):
    sheet = cs.load_concert_sheet(userdata, 2, NOW)
    rows = [(t.number, t.title, t.key, t.mk, t.virus, t.virus_status) for t in sheet.tracks]
    assert rows == [
        ("01", "NO SURRENDER (Intro)", "G#", "-/-", "-/-", "OFF"),        # « -/- » conservé
        ("02", "MY DIGNITY", "F", "A62", "RAM-D 75", "ON"),
        ("03", "(HAVE WE) LOST IT ALL", "F#/G#/A#", "—", "RAM-D 72", "OFF"),   # vide → —
        ("04", "MY DIGNITY", "F", "A62", "RAM-D 75", "ON"),                  # répétition
        ("05", "EYES WITHOUT A FACE", "—", "—", "RAM-D 74", "—"),            # chaîne vide, espaces, NULL
    ]
    assert cs.EMPTY == "—"


def test_sheet_heading_and_meta(userdata):
    sheet = cs.load_concert_sheet(userdata, 2, NOW)
    assert sheet.name == "Concert 02" and sheet.date == "10/11/26"
    assert sheet.meta == "Le Kiosque · 10/11/26 · 5 titres"
    one = cs.load_concert_sheet(userdata, 22, NOW)
    assert one.meta == "Salle 22 · 09/01/27 · 1 titre"
    undated = cs.load_concert_sheet(userdata, 32, NOW)
    assert undated.date == "DATE À DÉFINIR" and undated.meta == "DATE À DÉFINIR · 0 titre"   # salle vide omise


@pytest.mark.parametrize("stored", ["La Sirène\nLa Rochelle (17)", "La Sirène \nLa Rochelle (17)",
                                    "  La Sirène \r\n  La Rochelle (17)  "])
def test_multiline_venue_on_one_clean_line_in_meta(userdata, stored):
    conn = connect(database_path(userdata))
    with conn:
        conn.execute("UPDATE setlists SET venue = ? WHERE id = 5", (stored,))
    conn.close()
    sheet = cs.load_concert_sheet(userdata, 5, NOW)
    assert sheet.venue == stored                                             # champ complet conservé
    assert sheet.meta == "La Sirène · La Rochelle (17) · 19/11/26 · 0 titre"   # lignes jointes par « · » (2.9)


def test_practical_info_presence(userdata):
    full = cs.load_concert_sheet(userdata, 2, NOW)
    assert full.has_practical_info
    assert full.address == "12 rue des Lilas\n86300 Chauvigny" and full.organizer == "Mairie de Chauvigny"
    assert full.contacts[0] == Contact("Alice", "Régie", "06 00 00 00 00", None)
    assert [s.time for s in full.schedule] == ["16:00", "17:30", "21:30"]
    assert not cs.load_concert_sheet(userdata, 1, NOW).has_practical_info       # bloc masqué (D69)


def test_blank_practical_fields_count_as_empty(userdata):
    conn = connect(database_path(userdata))
    with conn:
        conn.execute("UPDATE setlists SET organizer = '   ', notes = '' WHERE id = 3")
        conn.execute("INSERT INTO setlist_contacts(setlist_id, position, name) VALUES (3, 1, ' ')")
    conn.close()
    assert not cs.load_concert_sheet(userdata, 3, NOW).has_practical_info


def test_cancelled_status_is_reported(userdata):
    assert cs.load_concert_sheet(userdata, 31, NOW).status is SetlistStatus.CANCELLED


# --- lecture seule ---------------------------------------------------------------------------------------

def test_reading_never_modifies_the_database(userdata):
    before = sha(userdata)
    for setlist_id in (1, 2, 22, 30, 31, 32, 999):
        cs.load_concert_sheet(userdata, setlist_id, NOW)
        cs.load_concert_sheet(userdata, setlist_id, NOW, SortOrder.NEWEST_FIRST)
    assert sha(userdata) == before
    assert not (database_path(userdata).parent / "scenix16.db-journal").exists()


def test_view_key_of_concert_matches_bank_of_concert(userdata):
    conn = connect(database_path(userdata))
    try:
        view = build_dashboard(repository.read_concert_summaries(conn), NOW)
    finally:
        conn.close()
    for setlist_id in (1, 17, 22, 30, 31, 32, 999):
        key = view.key_of_concert(setlist_id)
        assert view.bank_of_concert(setlist_id) == (key.bank if key else None)
    assert view.key_of_concert(17).address == "B01" and view.key_of_concert(30) is None


# --- résumé du bloc replié et séparateur de la salle (2.9, C2) ---------------------------------------------

from dataclasses import replace as _replace                             # noqa: E402

from scenix16.domain.models import Contact, ScheduleItem              # noqa: E402


@pytest.mark.parametrize("text, expected", [
    ("La Sirène\nLa Rochelle (17)", "La Sirène · La Rochelle (17)"),
    ("  Le Kiosque \r\n\n  Chauvigny   (86) ", "Le Kiosque · Chauvigny (86)"),
    ("Salle 22", "Salle 22"), ("", ""), (None, ""), (" \n ", ""),
])
def test_one_line_joins_venue_lines_with_a_dot(text, expected):
    assert cs.one_line(text) == expected


def summary_of(userdata, schedule=(), contacts=()):
    sheet = cs.load_concert_sheet(userdata, 5, NOW)
    return cs.practical_summary(_replace(sheet, schedule=tuple(schedule), contacts=tuple(contacts)))


def contact(name=None, role=None, phone=None, email=None):
    return Contact(name, role, phone, email)


def test_summary_prefers_passage_whatever_its_position(userdata):
    schedule = [ScheduleItem("Arrivée", "15:00"), ScheduleItem("Balance", "17:00"), ScheduleItem("PASSAGE", "21:30")]
    contacts = [contact("Claire"), contact(None, "Son")]
    assert summary_of(userdata, schedule, contacts) == "PASSAGE 21:30 · 2 contacts"


def test_summary_falls_back_to_first_schedule_item(userdata):
    assert summary_of(userdata, [ScheduleItem("Balance", "17:00"), ScheduleItem("Fin", "23:00")],
                      [contact("Claire")]) == "Balance 17:00 · 1 contact"


def test_summary_shows_only_available_information(userdata):
    assert summary_of(userdata, [ScheduleItem("Passage", "21:30")]) == "Passage 21:30"
    assert summary_of(userdata, [], [contact(phone="06")]) == "1 contact"
    assert summary_of(userdata, [ScheduleItem(None, "20:00")]) == "20:00"
    assert summary_of(userdata, [ScheduleItem("Passage", None)]) == "Passage"
    assert summary_of(userdata) == ""


def test_summary_ignores_empty_entries(userdata):
    schedule = [ScheduleItem(" ", " "), ScheduleItem("Balance", "17:00")]
    contacts = [contact(" ", None, "", None), contact("Marc")]
    assert summary_of(userdata, schedule, contacts) == "Balance 17:00 · 1 contact"
