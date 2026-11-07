"""Séquence de démarrage : UserData accessible, instance unique, base prête.

La logique est séparée de l'interface : les fenêtres de dialogue sont
fournies par un objet `StartupUI` (implémenté en Qt dans ui/startup_dialogs.py,
et par un faux objet dans les tests).

Ordre :
1. contrôle d'écriture de UserData (à côté de l'application) ;
2. en cas d'échec : « Choisir un emplacement… » (copie complète du dossier
   portable puis redémarrage depuis la copie) ou « Quitter » — jamais de repli
   silencieux ailleurs ;
3. verrou d'instance : si SceniX16 tourne déjà sur ce UserData, message et arrêt
   sans toucher aux données ;
4. ouverture (ou création) de la base SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from scenix16.services.relocation import RelocationError, RelocationResult, copy_portable_folder
from scenix16.storage import database
from scenix16.storage.instance_lock import InstanceLock
from scenix16.storage.userdata import WriteCheck, check_writable, database_path

EXIT_QUIT = 0
EXIT_ALREADY_RUNNING = 5
EXIT_STORAGE = 3


class Choice(Enum):
    CHOOSE_LOCATION = "choose"
    QUIT = "quit"


class StartupUI(Protocol):
    def storage_problem(self, check: WriteCheck, can_relocate: bool) -> Choice: ...
    def choose_parent_folder(self) -> Path | None: ...
    def copying(self, running: bool) -> None: ...
    def relocation_failed(self, error: RelocationError) -> None: ...
    def offer_restart(self, result: RelocationResult) -> bool: ...
    def already_running(self, userdata: Path) -> None: ...


@dataclass
class StartupOutcome:
    ready: bool
    exit_code: int = EXIT_QUIT
    userdata: Path | None = None
    lock: InstanceLock | None = None
    restart_from: Path | None = None   # dossier de la copie à lancer


def prepare(app_dir: Path, userdata: Path, ui: StartupUI, can_relocate: bool) -> StartupOutcome:
    check = check_writable(userdata)
    while not check.writable:
        choice = ui.storage_problem(check, can_relocate)
        if choice is not Choice.CHOOSE_LOCATION or not can_relocate:
            return StartupOutcome(False, EXIT_STORAGE)
        parent = ui.choose_parent_folder()
        if parent is None:
            continue  # retour à l'avertissement
        ui.copying(True)
        try:
            result = copy_portable_folder(app_dir, parent)
        except RelocationError as error:
            ui.copying(False)
            ui.relocation_failed(error)
            continue
        ui.copying(False)
        if ui.offer_restart(result):
            return StartupOutcome(False, EXIT_QUIT, restart_from=result.destination)
        # copie conservée ; l'utilisateur peut choisir à nouveau ou quitter

    lock = InstanceLock(userdata)
    if not lock.acquire():
        ui.already_running(userdata)
        return StartupOutcome(False, EXIT_ALREADY_RUNNING)

    connection = database.connect(database_path(userdata))  # crée le schéma au besoin
    connection.close()
    return StartupOutcome(True, userdata=userdata, lock=lock)
