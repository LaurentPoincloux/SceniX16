"""Version de l'application et informations de fabrication (Q18, Design Book v0.43).

- Source unique de la version : scenix16.__version__ (« 0.1.0-dev » pendant le
  développement, « 0.1.0-rc.N » en recette, « 0.1.0 » à la clôture des phases 1 et 2).
  Les étapes de la feuille de route (2.6b, 2.6c, 2.7…) n'apparaissent jamais dans la version.
- Propriétés de l'exécutable Windows : quatre nombres, FILE_VERSION.
- Informations de fabrication : écrites par la fabrication (tools/scenix16.spec) dans
  build_info.json, à côté des ressources de l'exécutable, jamais dans les sources.
  Lancé depuis les sources, l'application n'en a pas : « Version de développement ».
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scenix16 import __version__
from scenix16.paths import resource

FILE_VERSION = (0, 1, 0, 0)          # propriétés de l'exécutable (arbitrage de 2.6c)
BUILD_INFO_NAME = "build_info.json"
DEVELOPMENT_LABEL = "Version de développement"


@dataclass(frozen=True)
class BuildInfo:
    built_on: date
    commit: str              # identifiant court du commit, ou « inconnu »
    local_changes: bool      # modifications non commitées dans le code fabriqué


def build_info_payload(built_on: date, commit: str, local_changes: bool) -> dict:
    return {"version": __version__, "built_on": built_on.isoformat(), "commit": commit,
            "local_changes": local_changes}


def load_build_info(path: Path | None = None) -> BuildInfo | None:
    """Informations de fabrication, ou None (lancement depuis les sources, fichier illisible)."""
    path = path or resource(BUILD_INFO_NAME)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return BuildInfo(date.fromisoformat(data["built_on"]), str(data["commit"]),
                         bool(data["local_changes"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None
