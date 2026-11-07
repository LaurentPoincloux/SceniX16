"""Verrou empêchant deux instances d'utiliser le même UserData.

Le verrou est un fichier `UserData/.scenix16.lock` ouvert et verrouillé par
Windows tant que l'application tourne. Windows libère le verrou à la fin du
processus, même après un plantage : il ne reste jamais de verrou « bloqué ».
"""

from __future__ import annotations

import msvcrt
import os
from pathlib import Path

LOCK_FILENAME = ".scenix16.lock"


class InstanceLock:
    def __init__(self, userdata: Path):
        self.path = Path(userdata) / LOCK_FILENAME
        self._fd: int | None = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> bool:
        """Prend le verrou. Renvoie False si une autre instance le détient."""
        if self._fd is not None:
            return True
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
