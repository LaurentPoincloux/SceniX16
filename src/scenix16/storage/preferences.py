"""Préférences de l'utilisateur : UserData/settings.json.

Incrément 2.5 : sens de tri des concerts, partagé entre le dashboard et
SETLISTS (D7), « Plus ancien d'abord » par défaut (D1).

Règles (arbitrage 4 de l'incrément 2.5) :
- fichier absent, valeur inconnue ou clé manquante : sens par défaut ;
- encodage UTF-8, avec ou sans BOM ;
- fichier illisible (JSON invalide, imbrication excessive, autre chose qu'un
  objet) : renommé avec un suffixe horodaté (settings.corrupt-AAAAMMJJ-HHMMSS.json),
  puis sens par défaut ; si le renommage échoue, l'application continue avec
  le sens par défaut ;
- fichier inaccessible (accès refusé, verrou) : sens par défaut pour la session,
  fichier jamais renommé ni réécrit (ses clés sont préservées) ;
- fichier d'une version plus récente que celle prise en charge : sens par
  défaut pour la session, fichier jamais réécrit ;
- écriture atomique (fichier temporaire puis remplacement), clés inconnues
  conservées ; un échec d'écriture ne lève jamais d'exception : l'appelant
  garde le sens choisi pour la session.
Ces fonctions ne touchent jamais à la base SQLite.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

from scenix16.domain.dashboard import DEFAULT_SORT, SortOrder

SETTINGS_FILENAME = "settings.json"
SETTINGS_VERSION = 1
SORT_ORDER_KEY = "concerts_sort_order"     # nom neutre : dashboard et SETLISTS (D7)


def settings_path(userdata: Path) -> Path:
    return userdata / SETTINGS_FILENAME


def _corrupt_name(userdata: Path, now: datetime) -> Path:
    stamp = now.strftime("%Y%m%d-%H%M%S")
    candidate = userdata / f"settings.corrupt-{stamp}.json"
    n = 2
    while candidate.exists():                 # ne jamais écraser un fichier existant
        candidate = userdata / f"settings.corrupt-{stamp}-{n}.json"
        n += 1
    return candidate


class FileState(Enum):
    ABSENT = "absent"              # pas de fichier : écriture permise
    OK = "ok"                      # lu et pris en charge
    CORRUPT = "corrupt"            # illisible : renommé (si possible), écriture permise
    INACCESSIBLE = "inaccessible"  # accès refusé : ni renommé ni réécrit
    NEWER = "newer"                # version plus récente : jamais réécrit


def _read(userdata: Path, clock: Callable[[], datetime]) -> tuple[FileState, dict]:
    """État du fichier et son contenu ({} sauf pour un fichier lu et pris en charge)."""
    path = settings_path(userdata)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return FileState.ABSENT, {}
    except OSError:
        return FileState.INACCESSIBLE, {}     # accès refusé : distinct d'un fichier abîmé
    try:
        data = json.loads(raw.decode("utf-8-sig"))      # BOM accepté
        if not isinstance(data, dict):
            raise ValueError("objet JSON attendu")
    except (UnicodeDecodeError, ValueError, RecursionError):
        try:
            path.rename(_corrupt_name(userdata, clock()))
        except OSError:
            pass                               # renommage impossible : on continue
        return FileState.CORRUPT, {}
    version = data.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version > SETTINGS_VERSION:
        return FileState.NEWER, {}
    return FileState.OK, data


def load_sort_order(userdata: Path | None,
                    clock: Callable[[], datetime] = datetime.now) -> SortOrder:
    if userdata is None:
        return DEFAULT_SORT
    state, data = _read(userdata, clock)
    if state is not FileState.OK:
        return DEFAULT_SORT
    try:
        return SortOrder(data.get(SORT_ORDER_KEY))
    except ValueError:
        return DEFAULT_SORT


def save_sort_order(userdata: Path | None, order: SortOrder,
                    clock: Callable[[], datetime] = datetime.now) -> bool:
    """Enregistre le sens de tri ; renvoie False en cas d'échec, sans exception."""
    if userdata is None:
        return False
    state, data = _read(userdata, clock)
    if state in (FileState.INACCESSIBLE, FileState.NEWER):
        return False                           # le fichier existant est préservé tel quel
    data["version"] = SETTINGS_VERSION
    data[SORT_ORDER_KEY] = order.value
    path = settings_path(userdata)
    temp = userdata / f".{SETTINGS_FILENAME}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        return True
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
