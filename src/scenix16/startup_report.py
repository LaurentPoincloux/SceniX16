"""Rapport technique d'un échec de démarrage (D72, incrément 2.8d — arbitrages B5, P2, P4).

Fichier texte UTF-8 `UserData\\logs\\startup-error-AAAAMMJJ-HHMMSS.txt`, écrit seulement si
c'est possible : son échec n'empêche jamais la gestion normale de l'erreur (la fonction ne lève
jamais d'exception). Contenu : étape, date et heure, version, type et message de l'exception
(500 caractères au plus), trace utile au diagnostic. Aucune donnée de la base ni du classeur.
Anonymisation, y compris dans la trace : le dossier de l'application devient `<SceniX16>`, le
dossier personnel de l'utilisateur `<utilisateur>`.
"""

from __future__ import annotations

import re
import traceback
from datetime import datetime
from pathlib import Path

from scenix16 import __version__

REPORT_PREFIX = "startup-error-"
MESSAGE_LIMIT = 500
APP_TOKEN = "<SceniX16>"
HOME_TOKEN = "<utilisateur>"


def _variants(path: Path | None) -> list[str]:
    """Écritures possibles d'un chemin (barres obliques ou inverses), de la plus longue à la plus courte."""
    if path is None:
        return []
    found = set()
    for candidate in (path, _resolved(path)):
        text = str(candidate).rstrip("\\/")
        if len(text) > 3:                        # jamais « C:\ » seul
            found.update({text, text.replace("\\", "/")})
    return sorted(found, key=len, reverse=True)


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def anonymize(text: str, app_dir: Path | None, home: Path | None) -> str:
    """Remplace le dossier de l'application puis le dossier personnel (casse ignorée, Windows)."""
    for token, path in ((APP_TOKEN, app_dir), (HOME_TOKEN, home)):
        for variant in _variants(path):
            text = re.sub(re.escape(variant), lambda _m, token=token: token, text, flags=re.IGNORECASE)
    return text


def _limited(message: str) -> str:
    return message if len(message) <= MESSAGE_LIMIT else message[:MESSAGE_LIMIT - 1] + "…"


def describe(error: BaseException, app_dir: Path | None, home: Path | None) -> tuple[str, str]:
    """(exception « Type: message », trace) anonymisés ; messages limités à 500 caractères."""
    def exception_line(exc: BaseException) -> str:
        message = _limited(anonymize(str(exc), app_dir, home))
        name = type(exc).__qualname__
        return f"{name}: {message}" if message else name

    parts = []
    chain = []
    seen = set()
    exc: BaseException | None = error
    while exc is not None and id(exc) not in seen:      # causes enchaînées, sans boucle
        seen.add(id(exc))
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__
    for index, exc in enumerate(reversed(chain)):
        if index:
            parts.append("\nPuis, pendant le traitement de cette erreur :\n")
        parts.append("Traceback (most recent call last):\n")
        parts.extend(traceback.format_tb(exc.__traceback__))
        parts.append(exception_line(exc) + "\n")
    trace = anonymize("".join(parts), app_dir, home)
    return exception_line(error), trace


def report_text(step_name: str, error: BaseException, when: datetime,
                app_dir: Path | None, home: Path | None, version: str = __version__) -> str:
    exception, trace = describe(error, app_dir, home)
    return (
        "SceniX16 — rapport d'échec du démarrage\n"
        "=======================================\n\n"
        f"Date et heure : {when:%d/%m/%Y %H:%M:%S}\n"
        f"Version : {version}\n"
        f"Étape : {step_name}\n"
        f"Exception : {exception}\n\n"
        "Trace technique (chemins anonymisés) :\n"
        f"{trace}"
    )


def write_report(userdata: Path | None, step_name: str, error: BaseException,
                 when: datetime | None = None, app_dir: Path | None = None,
                 home: Path | None = None) -> Path | None:
    """Écrit le rapport dans UserData\\logs ; None si c'est impossible (jamais d'exception)."""
    try:
        if userdata is None:
            return None
        when = when or datetime.now()
        if home is None:
            home = Path.home()
        text = report_text(step_name, error, when, app_dir, home)
        logs = Path(userdata) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        stem = f"{REPORT_PREFIX}{when:%Y%m%d-%H%M%S}"
        path = logs / f"{stem}.txt"
        index = 2
        while path.exists():                     # deux échecs dans la même seconde
            path = logs / f"{stem}-{index}.txt"
            index += 1
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
        return path
    except Exception:
        return None
