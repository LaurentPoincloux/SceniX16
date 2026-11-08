"""À propos (D59, Q10, Q14, Q18) et Licences et composants tiers — Design Book v0.43."""

import re
from datetime import date
from importlib.metadata import version as dist_version

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from scenix16.ui.about_dialog import CREDITS, LICENSES_LINK, AboutDialog, version_lines
from scenix16.ui.licenses_dialog import SUMMARY, LicensesDialog, license_files, licenses_dir
from scenix16.ui.theme.stylesheet import application_stylesheet
from scenix16.version import BuildInfo

CREDITS_V043 = (
    "Conception et direction du projet : Laurent Poincloux.",
    "Développement logiciel : réalisé avec l'assistance de Claude Code (Anthropic), sous la direction "
    "de Laurent Poincloux.",
    "Conception, architecture et accompagnement : avec l'assistance de ChatGPT (OpenAI) pour la "
    "réflexion fonctionnelle, les choix d'architecture, la formalisation des spécifications et la revue "
    "des propositions de développement, sous la direction de Laurent Poincloux.",
)


# --- version (Q18) ------------------------------------------------------------------------

def test_version_lines_from_sources():
    assert version_lines(None) == ("Version de développement", None)


def test_version_lines_of_a_build_without_local_changes():
    info = BuildInfo(date(2026, 11, 7), "a83e126", False)
    assert version_lines(info, "0.1.0-dev") == ("Version 0.1.0-dev · fabrication du 7 novembre 2026",
                                               "Commit a83e126")


def test_version_lines_flag_uncommitted_changes():
    info = BuildInfo(date(2026, 12, 1), "a83e126", True)
    assert version_lines(info, "0.1.0") == (
        "Version 0.1.0 · fabrication du 1er décembre 2026",
        "Commit a83e126, avec modifications locales non commitées")


# --- boîte À propos ------------------------------------------------------------------------

@pytest.fixture
def about(qtbot, qapp):
    qapp.setStyleSheet(application_stylesheet())
    dialog = AboutDialog(use_build_file=False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def test_about_content(about):
    assert about.windowTitle() == "À propos de SceniX16"
    assert about.name_label.text() == "SceniX16"
    assert about.logo.source_is_valid()
    assert about.version_label.text() == "Version de développement"
    assert not about.build_label.isVisible()
    assert tuple(label.text() for label in about.credit_labels) == CREDITS == CREDITS_V043
    assert about.licenses_button.text() == LICENSES_LINK == "Licences et composants tiers…"
    texts = " ".join(w.text() for w in about.findChildren(type(about.name_label)))
    assert "@" not in texts and "http" not in texts and "WAITING" not in texts.upper()   # Q14


def test_about_with_build_info(qtbot, qapp):
    dialog = AboutDialog(build_info=BuildInfo(date(2026, 11, 7), "a83e126", True))
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.version_label.text().startswith("Version 0.1.0-dev · fabrication du 7 novembre 2026")
    assert dialog.build_label.isVisible()
    assert dialog.build_label.text() == "Commit a83e126, avec modifications locales non commitées"


def test_escape_closes_about(about, qtbot):
    qtbot.keyClick(about, Qt.Key_Escape)
    assert not about.isVisible()


def test_licenses_link_opens_read_only_window(about, qtbot):
    seen = {}

    def inside():
        dialog = QApplication.activeModalWidget()
        seen["title"] = dialog.windowTitle()
        seen["read_only"] = dialog.text.isReadOnly()
        seen["first"] = dialog.list.currentItem().text()
        dialog.accept()

    QTimer.singleShot(200, inside)
    about.licenses_button.click()
    assert seen == {"title": "Licences et composants tiers", "read_only": True, "first": "Vue d'ensemble"}


# --- dossier LICENCES -------------------------------------------------------------------------

def test_summary_first_then_texts():
    files = license_files()
    assert files[0].name == SUMMARY
    assert [p.name for p in files[1:]] == sorted((p.name for p in files[1:]), key=str.lower)


def test_every_listed_licence_text_is_present():
    summary = (licenses_dir() / SUMMARY).read_text(encoding="utf-8")
    listed = set(re.findall(r"[\w.-]+\.txt", summary))
    assert {"LGPL-3.0.txt", "GPL-3.0.txt", "Python-PSF-License.txt", "PyInstaller-COPYING.txt",
            "openpyxl-MIT.txt", "et_xmlfile-MIT.txt", "Barlow-Semi-Condensed-OFL-1.1.txt",
            "IBM-Plex-Mono-OFL-1.1.txt"} <= listed
    for name in listed:
        assert (licenses_dir() / name).is_file(), name
    present = {p.name for p in licenses_dir().glob("*.txt")} - {SUMMARY}
    assert present <= listed                                   # aucun texte non référencé


@pytest.mark.parametrize("dist", ["PySide6_Essentials", "shiboken6", "openpyxl", "et_xmlfile", "pyinstaller"])
def test_summary_versions_match_installed_dependencies(dist):
    summary = (licenses_dir() / SUMMARY).read_text(encoding="utf-8")
    assert dist_version(dist) in summary                       # liste tenue à jour (D59)


def test_official_texts_are_complete():
    folder = licenses_dir()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in (folder / "LGPL-3.0.txt").read_text(encoding="utf-8")
    assert "Version 3, 29 June 2007" in (folder / "LGPL-3.0.txt").read_text(encoding="utf-8")
    gpl = (folder / "GPL-3.0.txt").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in gpl and "END OF TERMS AND CONDITIONS" in gpl
    assert "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in \
        (folder / "Python-PSF-License.txt").read_text(encoding="utf-8")
    for font in ("Barlow-Semi-Condensed-OFL-1.1.txt", "IBM-Plex-Mono-OFL-1.1.txt"):
        assert "SIL OPEN FONT LICENSE Version 1.1" in (folder / font).read_text(encoding="utf-8")


def test_licenses_dialog_shows_texts(qtbot, qapp):
    dialog = LicensesDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.text.toPlainText().startswith("SceniX16 utilise les polices et les composants")
    assert dialog.text.isReadOnly() and dialog.text.lineWrapMode() == dialog.text.LineWrapMode.WidgetWidth
    rows = {dialog.list.item(r).text(): r for r in dialog.entry_rows()}
    dialog.list.setCurrentRow(rows["openpyxl"])
    assert "Permission is hereby granted" in dialog.text.toPlainText()


# --- 2.6d : bouton Fermer et harmonisation des deux fenêtres ------------------------------------

def _colors(widget):
    from PySide6.QtGui import QColor
    image = widget.grab().toImage()
    return {QColor(image.pixel(x, y)).name() for x in range(image.width()) for y in range(image.height())}


def _shown(qtbot, dialog):
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.activateWindow()
    qtbot.waitUntil(dialog.isActiveWindow)
    qtbot.wait(50)


@pytest.mark.parametrize("make", [lambda: AboutDialog(use_build_file=False), lambda: LicensesDialog()])
def test_close_button_orange_only_with_keyboard_focus(qtbot, qapp, make):
    from scenix16.ui.theme import tokens as t
    qapp.setStyleSheet(application_stylesheet())
    dialog = make()
    qtbot.addWidget(dialog)
    _shown(qtbot, dialog)
    button = dialog.close_button
    button.setFocus(Qt.OtherFocusReason)               # focus automatique, comme à l'ouverture
    qtbot.wait(30)
    assert button.hasFocus() and not button.keyboard_focus()
    assert t.BRAND.lower() not in _colors(button)       # bordure neutre
    assert t.LINE_STRONG.lower() in _colors(button)
    button.setFocus(Qt.MouseFocusReason)                # clic : pas d'accent
    qtbot.wait(30)
    assert t.BRAND.lower() not in _colors(button)
    dialog.setFocus(Qt.OtherFocusReason)
    button.setFocus(Qt.TabFocusReason)                  # navigation clavier : accent orange
    qtbot.wait(30)
    assert button.keyboard_focus() and t.BRAND.lower() in _colors(button)
    dialog.setFocus(Qt.TabFocusReason)                  # focus parti : bordure neutre
    qtbot.wait(30)
    assert not button.keyboard_focus() and t.BRAND.lower() not in _colors(button)


def test_close_button_still_closes_with_enter_and_escape(qtbot, qapp):
    for key in (Qt.Key_Return, Qt.Key_Escape):
        dialog = AboutDialog(use_build_file=False)
        qtbot.addWidget(dialog)
        _shown(qtbot, dialog)
        assert dialog.close_button.isDefault()
        qtbot.keyClick(dialog, key)
        assert not dialog.isVisible()


def test_licenses_window_matches_about(qtbot, qapp):
    qapp.setStyleSheet(application_stylesheet())
    about, licenses = AboutDialog(use_build_file=False), LicensesDialog()
    for d in (about, licenses):
        qtbot.addWidget(d)
        _shown(qtbot, d)
    assert licenses.title_label.text() == "Licences et composants tiers"
    assert licenses.title_label.objectName() == about.name_label.objectName() == "DialogTitle"
    assert licenses.title_label.font().pixelSize() == about.name_label.font().pixelSize()
    assert licenses.layout().contentsMargins() == about.layout().contentsMargins()
    assert type(licenses.close_button) is type(about.close_button)
    assert licenses.palette().window().color() == about.palette().window().color()   # même fond relevé
    assert licenses.text.isReadOnly()                    # consultation seule, contenu inchangé
    assert len(licenses.entry_rows()) == len(license_files())       # Vue d'ensemble + un texte par fichier



# --- 2.6e : refonte de la fenêtre et catalogue vérifié --------------------------------------------

from scenix16.services import licenses_catalog as cat                     # noqa: E402
from scenix16.ui.licenses_dialog import presentation_html, read_legal_text   # noqa: E402


def _norm(text):
    return " ".join(text.replace("\r\n", "\n").split())


def test_catalog_matches_licence_files_exactly():
    files = {p.name for p in licenses_dir().glob("*.txt")} - {SUMMARY}
    in_catalog = [e.file for e in cat.CATALOG]
    assert sorted(in_catalog) == sorted(files)                              # un élément par fichier, sans oubli
    assert len(set(in_catalog)) == len(in_catalog)


def test_catalog_matches_lisez_moi():
    summary = _norm((licenses_dir() / SUMMARY).read_text(encoding="utf-8"))
    for entry in cat.CATALOG:
        assert _norm(entry.summary) in summary, entry.key                   # libellé repris mot pour mot
        assert entry.file in summary, entry.file
        if entry.version:
            assert entry.version in summary, entry.key
    for text in (cat.INTRO, cat.FONTS_NOTE, cat.QT_LIBRARIES_NOTE, cat.OBLIGATIONS):
        assert _norm(text) in summary, text[:40]
    for _label, url in cat.QT_SOURCES:
        assert url in summary


def test_catalog_versions_match_installed_components():
    import platform
    from importlib.metadata import version as dist_version
    for entry in cat.CATALOG:
        if entry.distribution == "python":
            assert entry.version == platform.python_version()
        elif entry.distribution:
            assert entry.version == dist_version(entry.distribution), entry.key
    assert dist_version("shiboken6") == cat.CATALOG[[e.key for e in cat.CATALOG].index("qt")].version


def test_presentation_keeps_every_reference_of_lisez_moi():
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(presentation_html())
    shown = _norm(doc.toPlainText())
    for entry in cat.CATALOG:
        assert _norm(entry.summary) in shown and entry.file in shown, entry.key
    for _label, url in cat.QT_SOURCES:
        assert url in shown
    for text in (cat.INTRO, cat.QT_LIBRARIES_NOTE):
        assert _norm(text) in shown
    assert _norm(cat.OBLIGATIONS.split(" : ", 1)[1])[1:] in shown


@pytest.fixture
def licences_window(qtbot, qapp):
    qapp.setStyleSheet(application_stylesheet())
    dialog = LicensesDialog()
    qtbot.addWidget(dialog)
    _shown(qtbot, dialog)
    return dialog


def test_navigation_grouped_by_category(licences_window):
    d = licences_window
    categories = [d.list.item(r).text() for r in range(d.list.count()) if r not in d.entry_rows()]
    assert categories == list(cat.CATEGORIES)
    for r in range(d.list.count()):
        item = d.list.item(r)
        if r not in d.entry_rows():
            assert item.flags() == Qt.NoItemFlags                             # intitulé non sélectionnable
    names = [d.list.item(r).text() for r in d.entry_rows()]
    assert names[0] == "Vue d'ensemble" and "Qt, PySide6 et shiboken6" in names
    qt_row = d.entry_rows()[names.index("Qt, PySide6 et shiboken6")]
    assert d.list.item(qt_row).data(Qt.AccessibleTextRole) == "Qt, PySide6 et shiboken6, GNU LGPL v3 · 6.12.0"


def test_every_legal_text_shown_strictly_identical(licences_window):
    d = licences_window
    for row in d.entry_rows()[1:]:
        d.list.setCurrentRow(row)
        entry = d.current_entry()
        original = read_legal_text(entry.file).replace("\r\n", "\n")
        assert d.text.toPlainText() == original.rstrip("\n") or d.text.toPlainText() == original, entry.file
        assert entry.name == d.header_name.text() and entry.file in d.header_meta.text()
        assert entry.licence in d.header_meta.text()


def test_wrapping_without_horizontal_scroll(licences_window, qtbot):
    d = licences_window
    rows = {d.list.item(r).text(): r for r in d.entry_rows()}
    d.list.setCurrentRow(rows["IBM Plex Mono"])                           # lignes jusqu'à 93 caractères
    d.resize(760, 560)
    qtbot.wait(50)
    assert d.text.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert not d.text.horizontalScrollBar().isVisible()
    assert d.text.document().size().width() <= d.text.viewport().width() + 1
    assert d.text.verticalScrollBar().maximum() > 0                       # défilement vertical conservé


def test_keyboard_navigation_skips_categories_and_shows_focus_ring(licences_window, qtbot):
    from scenix16.ui.theme import tokens as t
    d = licences_window
    assert not d.list.keyboard_focus                                      # focus automatique : pas d'anneau
    d.close_button.setFocus(Qt.OtherFocusReason)
    d.list.setFocus(Qt.TabFocusReason)                                    # Tab jusqu'à la liste
    qtbot.waitUntil(d.list.hasFocus)
    assert d.list.keyboard_focus
    seen = []
    for _ in range(len(d.entry_rows()) + 2):
        qtbot.keyClick(d.list, Qt.Key_Down)
        seen.append(d.list.currentRow())
    assert set(seen) <= set(d.entry_rows())                               # intitulés ignorés
    assert t.BRAND.lower() in _colors(d.list.viewport())                  # anneau orange au clavier
    rect = d.list.visualItemRect(d.list.item(d.entry_rows()[1]))
    qtbot.mouseClick(d.list.viewport(), Qt.LeftButton, pos=rect.center())
    assert not d.list.keyboard_focus and t.BRAND.lower() not in _colors(d.list.viewport())   # clic : sans anneau
    assert t.SILK.lower() in _colors(d.list.viewport())                   # sélection : barre crème


def test_escape_closes_licences_window(licences_window, qtbot):
    qtbot.keyClick(licences_window, Qt.Key_Escape)
    assert not licences_window.isVisible()


def test_licence_files_untouched_by_the_window(licences_window):
    import hashlib
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in licenses_dir().iterdir()}
    for row in licences_window.entry_rows():
        licences_window.list.setCurrentRow(row)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in licenses_dir().iterdir()}
    assert before == after
