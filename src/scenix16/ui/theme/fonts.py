"""Chargement local des polices du Design Book (Q4).

Les fichiers sont livrés avec l'application (resources/fonts) : aucun
téléchargement à l'exécution. Licence SIL Open Font License 1.1, fichiers
OFL.txt conservés à côté des polices.
"""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from scenix16.paths import resource

LABEL_FAMILY = "Barlow Semi Condensed"   # libellés de façade, titres, boutons
MONO_FAMILY = "IBM Plex Mono"            # valeurs : numéros, patchs, dates

FONT_FILES = (
    ("barlow-semi-condensed", "BarlowSemiCondensed-Medium.ttf"),
    ("barlow-semi-condensed", "BarlowSemiCondensed-SemiBold.ttf"),
    ("barlow-semi-condensed", "BarlowSemiCondensed-Bold.ttf"),
    ("ibm-plex-mono", "IBMPlexMono-Regular.ttf"),
    ("ibm-plex-mono", "IBMPlexMono-Medium.ttf"),
)

_loaded: list[str] | None = None


def load_fonts() -> list[str]:
    """Enregistre les polices auprès de Qt (une seule fois). Renvoie les fichiers chargés.

    Une QGuiApplication doit exister. Un fichier manquant n'empêche pas le
    démarrage : Qt utilise alors la police de repli (Segoe UI).
    """
    global _loaded
    if _loaded is not None:
        return _loaded
    loaded = []
    for folder, name in FONT_FILES:
        path = resource("fonts", folder, name)
        if path.is_file() and QFontDatabase.addApplicationFont(str(path)) != -1:
            loaded.append(name)
    _loaded = loaded
    return loaded


def fonts_available() -> bool:
    families = QFontDatabase.families()
    return LABEL_FAMILY in families and MONO_FAMILY in families
