"""Dossier UserData : toutes les données écrites par SceniX16.

Règle du plan technique (décision 2) : UserData se trouve à côté de
l'exécutable portable. Rien n'est jamais écrit ailleurs, ni dans
%LOCALAPPDATA%, et aucun repli silencieux n'est fait si l'écriture est
impossible : l'appelant reçoit un résultat explicite et décide quoi afficher.

En développement (programme lancé depuis les sources), UserData se trouve à
la racine du projet ; il est exclu de Git par .gitignore.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from scenix16.paths import is_frozen

USERDATA_DIRNAME = "UserData"
DATABASE_FILENAME = "scenix16.db"
SUBFOLDERS = ("media", "backups", "logs")


def application_dir() -> Path:
    """Dossier de l'application : celui de SceniX16.exe, ou la racine du projet."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # src/scenix16/storage/userdata.py -> racine du projet
    return Path(__file__).resolve().parents[3]


def default_userdata_dir() -> Path:
    return application_dir() / USERDATA_DIRNAME


@dataclass(frozen=True)
class WriteCheck:
    """Résultat de la vérification d'écriture."""

    path: Path
    writable: bool
    error: str | None = None


def check_writable(userdata: Path) -> WriteCheck:
    """Crée UserData (et ses sous-dossiers) si besoin, puis fait un essai d'écriture.

    L'essai écrit puis supprime un petit fichier temporaire. Aucune donnée
    existante n'est modifiée.
    """
    try:
        userdata.mkdir(parents=True, exist_ok=True)
        for name in SUBFOLDERS:
            (userdata / name).mkdir(exist_ok=True)
        probe = userdata / f".write-test-{uuid.uuid4().hex}.tmp"
        with open(probe, "wb") as handle:
            handle.write(b"SceniX16")
            handle.flush()
            os.fsync(handle.fileno())
        probe.unlink()
    except OSError as exc:
        return WriteCheck(userdata, False, f"{type(exc).__name__}: {exc}")
    return WriteCheck(userdata, True)


def database_path(userdata: Path) -> Path:
    return userdata / DATABASE_FILENAME
