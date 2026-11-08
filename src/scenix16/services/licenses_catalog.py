"""Catalogue des licences et composants tiers (D59, section 12 — Design Book v0.45, incrément 2.6e).

Décrit, pour la fenêtre « Licences et composants tiers », chaque police et chaque composant :
catégorie, nom, licence, version, fichier de licence du dossier LICENCES, et le libellé repris
mot pour mot du LISEZ-MOI. Il alimente la navigation et la page « Présentation ».

Ce catalogue ne remplace pas les fichiers : les textes juridiques sont toujours lus dans le
dossier LICENCES et affichés sans aucune modification. Les tests vérifient qu'il concorde avec
les fichiers présents, avec le LISEZ-MOI et avec les versions réellement installées, pour qu'il
ne devienne jamais une seconde source de vérité incohérente.
"""

from __future__ import annotations

from dataclasses import dataclass

PRESENTATION = "Présentation"
FONTS = "Polices"
COMPONENTS = "Composants"
REFERENCE = "Textes de référence"
CATEGORIES = (PRESENTATION, FONTS, COMPONENTS, REFERENCE)

SUMMARY_FILE = "LISEZ-MOI.txt"

INTRO = ("SceniX16 utilise les polices et les composants ci-dessous. Les textes officiels complets de "
         "leurs licences se trouvent dans ce dossier LICENCES, placé à côté de l'exécutable, et dans "
         "l'application (Aide › À propos de SceniX16 › Licences et composants tiers).")
FONTS_NOTE = "fournies sans modification, chargées localement"
QT_LIBRARIES_NOTE = ("Les bibliothèques Qt, PySide6 et shiboken6 sont fournies sous forme de fichiers "
                     "séparés (dossier _internal de l'exécutable), remplaçables par d'autres versions "
                     "compatibles.")
QT_SOURCES = (("Qt", "https://download.qt.io/official_releases/qt/"),
              ("PySide6 et shiboken6", "https://download.qt.io/official_releases/QtForPython/"))
OBLIGATIONS = ("Obligations de redistribution : vérifiées composant par composant avant chaque diffusion ; "
               "cette liste est tenue à jour à chaque changement de dépendance et contrôlée à chaque "
               "fabrication d'un exécutable distribuable.")


@dataclass(frozen=True)
class LicenseEntry:
    key: str
    category: str
    name: str                    # nom affiché dans la navigation et l'en-tête
    licence: str                 # licence, forme courte
    version: str | None          # version du composant (None pour une police ou un texte de référence)
    file: str                    # fichier du dossier LICENCES, affiché sans modification
    summary: str                 # libellé repris mot pour mot du LISEZ-MOI
    distribution: str | None = None   # paquet installé dont la version est vérifiée par les tests


CATALOG: tuple[LicenseEntry, ...] = (
    LicenseEntry("barlow", FONTS, "Barlow Semi Condensed", "SIL Open Font License 1.1", None,
                 "Barlow-Semi-Condensed-OFL-1.1.txt",
                 "Barlow Semi Condensed — © 2017 The Barlow Project Authors"),
    LicenseEntry("plex", FONTS, "IBM Plex Mono", "SIL Open Font License 1.1", None,
                 "IBM-Plex-Mono-OFL-1.1.txt",
                 "IBM Plex Mono — © 2017 IBM Corp., nom réservé « Plex »"),
    LicenseEntry("python", COMPONENTS, "Python", "Licence PSF", "3.15.2",
                 "Python-PSF-License.txt",
                 "Python 3.15.2 — Python Software Foundation License, avec les conditions des composants "
                 "intégrés à la distribution Windows (bzip2, libffi, OpenSSL…)", "python"),
    LicenseEntry("qt", COMPONENTS, "Qt, PySide6 et shiboken6", "GNU LGPL v3", "6.12.0",
                 "LGPL-3.0.txt",
                 "Qt 6.12, PySide6 6.12.0 et shiboken6 6.12.0 — GNU Lesser General Public License v3 "
                 "(LGPL v3), qui complète la GNU General Public License v3", "PySide6_Essentials"),
    LicenseEntry("openpyxl", COMPONENTS, "openpyxl", "Licence MIT", "3.1.5", "openpyxl-MIT.txt",
                 "openpyxl 3.1.5 — licence MIT", "openpyxl"),
    LicenseEntry("et_xmlfile", COMPONENTS, "et_xmlfile", "Licence MIT", "2.0.0", "et_xmlfile-MIT.txt",
                 "et_xmlfile 2.0.0 — licence MIT", "et_xmlfile"),
    LicenseEntry("et_xmlfile_python", COMPONENTS, "et_xmlfile (code repris)", "Licence Python", "2.0.0",
                 "et_xmlfile-Python-License.txt",
                 "avec la licence Python du code repris", "et_xmlfile"),
    LicenseEntry("pyinstaller", COMPONENTS, "PyInstaller", "GNU GPL v2+ avec exception",
                 "6.22.3", "PyInstaller-COPYING.txt",
                 "PyInstaller 6.22.3 (chargeur de l'exécutable) — GNU General Public License v2 ou "
                 "ultérieure, avec une exception qui autorise la distribution des programmes fabriqués",
                 "pyinstaller"),
    LicenseEntry("gpl3", REFERENCE, "GNU General Public License v3", "Texte de référence de la LGPL v3",
                 None, "GPL-3.0.txt", "GPL-3.0.txt"),
)


def entries(category: str) -> tuple[LicenseEntry, ...]:
    return tuple(e for e in CATALOG if e.category == category)


def entry_meta(entry: LicenseEntry) -> str:
    """Ligne secondaire : licence et version (« GNU LGPL v3 · 6.12.0 »)."""
    return f"{entry.licence} · {entry.version}" if entry.version else entry.licence
