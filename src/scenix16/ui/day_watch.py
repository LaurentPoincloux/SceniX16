"""Surveillance du jour SceniX16 pendant l'exécution (D73, D10 — incrément 2.8a).

La journée SceniX16 commence à 06:00 (heure fixe, sans réglage). Deux mécanismes :
- une minuterie unique, précise, réglée sur le prochain passage de 06:00 ;
- une vérification périodique légère (toutes les 60 s) qui compare le jour SceniX16 de
  l'horloge au dernier jour connu. Elle couvre ce que la minuterie seule ne voit pas :
  sortie de veille (les minuteries ne progressent pas pendant la veille), horloge
  système avancée ou reculée, changement d'heure légal.
Chaque vérification réarme la minuterie d'après l'horloge du moment. `day_changed` est
émis une seule fois par changement de jour, dans un sens comme dans l'autre (horloge
reculée comprise). L'objet ne lit l'horloge que par `clock`, injectable pour les tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from scenix16.domain.dashboard import next_day_switch, scenix16_day

CHECK_INTERVAL_MS = 60_000      # vérification périodique : au plus une minute de retard
MIN_SWITCH_DELAY_MS = 50        # minuterie déclenchée un peu tôt : nouvel essai, sans boucle serrée


def ms_until_switch(now: datetime) -> int:
    """Délai, en millisecondes, jusqu'au prochain passage de 06:00."""
    delay = (next_day_switch(now) - now).total_seconds() * 1000
    return max(MIN_SWITCH_DELAY_MS, int(delay) + 1)      # +1 : jamais un peu avant 06:00


class DayWatcher(QObject):
    day_changed = Signal(object)          # nouveau jour SceniX16 (datetime.date)

    def __init__(self, clock: Callable[[], datetime], parent: QObject | None = None):
        super().__init__(parent)
        self.clock = clock
        self.day: date = scenix16_day(clock())
        self.switch_timer = QTimer(self)
        self.switch_timer.setSingleShot(True)
        self.switch_timer.setTimerType(Qt.PreciseTimer)   # une minuterie grossière dériverait de minutes
        self.switch_timer.timeout.connect(self.check)
        self.check_timer = QTimer(self)
        self.check_timer.setInterval(CHECK_INTERVAL_MS)
        self.check_timer.timeout.connect(self.check)
        self.check_timer.start()
        self._arm()

    def _arm(self, now: datetime | None = None) -> None:
        self.switch_timer.start(ms_until_switch(self.clock() if now is None else now))

    def check(self) -> bool:
        """Compare le jour SceniX16 de l'horloge au dernier connu ; True s'il a changé."""
        now = self.clock()
        day = scenix16_day(now)
        self._arm(now)
        if day == self.day:
            return False
        self.day = day
        self.day_changed.emit(day)
        return True

    def stop(self) -> None:
        self.switch_timer.stop()
        self.check_timer.stop()
