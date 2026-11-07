"""Import en ligne de commande : python -m scenix16.importer [classeur.xlsx]

Crée la base dans UserData (à côté de l'application) et écrit le rapport dans
UserData/logs. Refuse si UserData n'est pas accessible en écriture, si
SceniX16 est déjà ouvert sur ce UserData, ou si la base contient déjà des
données.
"""

from __future__ import annotations

import sys
from pathlib import Path

from scenix16.importer.service import ImportRefused, import_into_userdata
from scenix16.storage import userdata
from scenix16.storage.instance_lock import InstanceLock

DEFAULT_WORKBOOK = Path("reference") / "SceniX16_Setlist_Manager_v2.3.0.xlsx"
EXIT_ALREADY_RUNNING = 5


def main(argv: list[str]) -> int:
    xlsx = Path(argv[1]) if len(argv) > 1 else userdata.application_dir() / DEFAULT_WORKBOOK
    if not xlsx.is_file():
        print(f"Classeur introuvable : {xlsx}")
        return 2
    check = userdata.check_writable(userdata.default_userdata_dir())
    if not check.writable:
        print(f"Écriture impossible dans {check.path} : {check.error}")
        return 3
    with InstanceLock(check.path) as lock:
        if not lock.acquire():
            print(f"SceniX16 est ouvert sur {check.path} : fermez-le avant l'import.")
            return EXIT_ALREADY_RUNNING
        try:
            result = import_into_userdata(xlsx, check.path)
        except ImportRefused as exc:
            print(exc)
            return 4
    print(f"Import terminé : {result.tracks} morceaux, {result.setlists} setlists, "
          f"{result.entries} entrées, {len(result.data.findings)} particularités à vérifier.")
    print(f"Base : {userdata.database_path(check.path)}")
    print(f"Rapport : {result.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
