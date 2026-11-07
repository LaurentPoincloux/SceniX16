"""Copie complète et sécurisée du dossier portable SceniX16 (plan technique,
décision 2 et précisions validées).

Utilisée quand UserData n'est pas accessible en écriture : l'utilisateur
choisit un dossier parent, l'application y crée une copie complète de son
dossier (exécutable, _internal, UserData), la vérifie, puis propose de
redémarrer depuis la copie.

Garanties :
- le dossier d'origine n'est jamais modifié ni supprimé ;
- aucune destination existante n'est écrasée ;
- en cas d'échec, la copie partielle est signalée, jamais supprimée
  automatiquement ;
- la base SQLite est copiée avec la méthode de sauvegarde de SQLite, qui
  produit un fichier cohérent même si la base est ouverte.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from scenix16.storage.instance_lock import LOCK_FILENAME
from scenix16.storage.userdata import DATABASE_FILENAME, USERDATA_DIRNAME, check_writable

SPACE_MARGIN = 10 * 1024 * 1024  # 10 Mo de marge


class RelocationError(Exception):
    """Copie impossible ou échouée. `partial` indique une copie partielle laissée en place."""

    def __init__(self, message: str, partial: Path | None = None):
        super().__init__(message)
        self.partial = partial


@dataclass(frozen=True)
class RelocationResult:
    destination: Path
    files: int
    bytes: int


def _files(root: Path) -> list[Path]:
    """Fichiers à copier, en relatif, hors fichier de verrou."""
    return sorted(
        p.relative_to(root) for p in root.rglob("*")
        if p.is_file() and p.name != LOCK_FILENAME
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_database(rel: Path) -> bool:
    return rel.parts == (USERDATA_DIRNAME, DATABASE_FILENAME)


def plan_destination(source: Path, parent: Path) -> Path:
    """Contrôles préalables, sans rien écrire. Renvoie le dossier de destination."""
    source = Path(source).resolve()
    parent = Path(parent).resolve()
    destination = parent / source.name
    if not parent.is_dir():
        raise RelocationError(f"Le dossier choisi n'existe pas : {parent}")
    if destination == source or source in destination.parents:
        raise RelocationError(
            "Le dossier choisi se trouve dans le dossier actuel de SceniX16. "
            "Choisissez un emplacement à l'extérieur."
        )
    if destination.exists():
        raise RelocationError(
            f"Un dossier « {destination.name} » existe déjà dans {parent}. "
            "Rien n'a été écrasé ; choisissez un autre emplacement."
        )
    needed = sum((source / rel).stat().st_size for rel in _files(source)) + SPACE_MARGIN
    if shutil.disk_usage(parent).free < needed:
        raise RelocationError(
            f"Espace libre insuffisant dans {parent} "
            f"(environ {needed // (1024 * 1024)} Mo nécessaires)."
        )
    probe = check_writable(parent / f".scenix16-probe-{source.name}")
    if not probe.writable:
        raise RelocationError(f"Écriture impossible dans {parent} : {probe.error}")
    shutil.rmtree(probe.path, ignore_errors=True)  # dossier d'essai créé à l'instant
    return destination


def copy_portable_folder(source: Path, parent: Path) -> RelocationResult:
    source = Path(source).resolve()
    destination = plan_destination(source, parent)
    files = _files(source)
    destination.mkdir()
    total = 0
    try:
        for rel in files:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if _is_database(rel):
                src_conn = sqlite3.connect(f"file:{source / rel}?mode=ro", uri=True)
                dst_conn = sqlite3.connect(target)
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
                    src_conn.close()
            else:
                shutil.copy2(source / rel, target)
            total += target.stat().st_size
        _verify(source, destination, files)
        check = check_writable(destination / USERDATA_DIRNAME)
        if not check.writable:
            raise RelocationError(f"La copie n'est pas accessible en écriture : {check.error}")
    except RelocationError as exc:
        raise RelocationError(str(exc), partial=destination) from exc
    except (OSError, sqlite3.Error) as exc:
        raise RelocationError(f"La copie a échoué : {exc}", partial=destination) from exc
    return RelocationResult(destination, len(files), total)


def _verify(source: Path, destination: Path, files: list[Path]) -> None:
    copied = _files(destination)
    missing = set(files) - set(copied)
    if missing:
        raise RelocationError(f"Copie incomplète : {len(missing)} fichier(s) manquant(s).")
    for rel in files:
        if _is_database(rel):
            conn = sqlite3.connect(destination / rel)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RelocationError("La base copiée est endommagée.")
            finally:
                conn.close()
        elif _sha256(source / rel) != _sha256(destination / rel):
            raise RelocationError(f"Fichier différent après copie : {rel}")
