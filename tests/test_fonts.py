"""Polices locales du Design Book (Q4) et licences."""

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

from scenix16.paths import resource
from scenix16.ui.theme import fonts


def test_font_files_and_licences_present():
    for folder, name in fonts.FONT_FILES:
        path = resource("fonts", folder, name)
        assert path.is_file(), path
        assert path.read_bytes()[:4] == b"\x00\x01\x00\x00"   # TrueType
    for folder in ("barlow-semi-condensed", "ibm-plex-mono"):
        licence = resource("fonts", folder, "OFL.txt").read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in licence


def test_fonts_load_locally(qapp):
    loaded = fonts.load_fonts()
    assert sorted(loaded) == sorted(name for _, name in fonts.FONT_FILES)
    assert fonts.fonts_available()
    assert {"Medium", "SemiBold", "Bold"} <= set(QFontDatabase.styles(fonts.LABEL_FAMILY))
    assert {"Regular", "Medium"} <= set(QFontDatabase.styles(fonts.MONO_FAMILY))


def test_fonts_resolve_without_fallback(qapp):
    fonts.load_fonts()
    for family in (fonts.LABEL_FAMILY, fonts.MONO_FAMILY):
        assert QFontInfo(QFont(family)).family() == family


def test_load_fonts_is_idempotent(qapp):
    assert fonts.load_fonts() is fonts.load_fonts()
