"""Emplacements utilisés par l'application.

Les ressources par défaut (logos, polices, icônes) sont livrées avec le
programme et ne sont jamais modifiées. En mode portable (exécutable
PyInstaller), elles se trouvent dans le dossier interne de l'application.
"""

import sys
from pathlib import Path


def is_frozen() -> bool:
    """Vrai quand l'application tourne depuis l'exécutable portable."""
    return getattr(sys, "frozen", False)


def resources_dir() -> Path:
    """Dossier des ressources par défaut, en développement comme en portable."""
    if is_frozen():
        return Path(sys._MEIPASS) / "scenix16" / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "resources"


def resource(*parts: str) -> Path:
    """Chemin d'une ressource par défaut."""
    return resources_dir().joinpath(*parts)
