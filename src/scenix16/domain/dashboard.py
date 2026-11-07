"""Règles du dashboard (Design Book v0.40).

Toutes les règles temporelles reçoivent l'instant courant en paramètre
(`now`) : aucune ne lit l'horloge de la machine.

- D10 / D2 : jour SceniX16 = de 6 h à 5 h 59 le lendemain. Un concert reste
  « du jour » jusqu'à 5 h 59 le lendemain de sa date, puis devient passé.
- D2 / D4 / D5 : les touches ne portent que des concerts maintenus, datés du
  jour SceniX16 ou ultérieurs. Annulés et setlists sans date en sont exclus.
- D1 / D7 : classement chronologique ; sens croissant par défaut, le sens
  choisi est fourni par l'appelant (sa mémorisation relève de 2.5).
- D6 : à date égale, ordre alphabétique français du nom : sans tenir compte
  de la casse ni des accents, le nom exact servant à départager ; cet ordre
  reste alphabétique quel que soit le sens de tri.
- D22 / D31 : 16 touches de base, sans limite ; au-delà, zone défilante ;
  classement continu ; même statut pour toutes les touches.
- D11 : état « Aujourd'hui » pour le concert du jour ; à défaut, le ou les
  concerts de la prochaine date sont « Prochain ».
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from scenix16.domain.models import ConcertSummary, SetlistStatus

DAY_SWITCH_HOUR = 6        # D10 : bascule le lendemain à 6 h
BASE_KEYS = 16             # disposition de base (D22)
GROUP_SIZE = 4             # 4 groupes de 4 couleurs, cycle repris au-delà de 16 (D31)


class SortOrder(Enum):
    OLDEST_FIRST = "oldest_first"   # « Plus ancien d'abord » (défaut, D1)
    NEWEST_FIRST = "newest_first"   # « Plus récent d'abord »


DEFAULT_SORT = SortOrder.OLDEST_FIRST


class ConcertState(Enum):
    TODAY = "today"          # concert du jour SceniX16 (D11)
    NEXT = "next"            # prochain concert, quand aucun n'a lieu aujourd'hui
    UPCOMING = "upcoming"    # à venir
    PAST = "past"            # passé (SETLISTS uniquement)
    CANCELLED = "cancelled"  # annulé (SETLISTS uniquement)
    UNDATED = "undated"      # « DATE À DÉFINIR » (SETLISTS uniquement)


ON_DASHBOARD = (ConcertState.TODAY, ConcertState.NEXT, ConcertState.UPCOMING)


def scenix16_day(now: datetime) -> date:
    """Jour SceniX16 correspondant à l'instant `now` (date et heure locales)."""
    return (now - timedelta(hours=DAY_SWITCH_HOUR)).date()


def _next_date(concerts: list[ConcertSummary], day: date) -> date | None:
    dates = [c.concert_date for c in concerts
             if c.concert_date is not None and c.status is SetlistStatus.MAINTAINED
             and c.concert_date >= day]
    return min(dates) if dates else None


def concert_state(concert: ConcertSummary, day: date, next_date: date | None) -> ConcertState:
    """État d'une setlist pour un jour SceniX16 donné.

    Une setlist sans date n'est jamais passée, annulée ni à venir (D5).
    """
    if concert.concert_date is None:
        return ConcertState.UNDATED
    if concert.status is SetlistStatus.CANCELLED:
        return ConcertState.CANCELLED
    if concert.concert_date < day:
        return ConcertState.PAST
    if concert.concert_date == day:
        return ConcertState.TODAY
    if next_date is not None and concert.concert_date == next_date:
        return ConcertState.NEXT
    return ConcertState.UPCOMING


def countdown_days(concert_date: date, day: date) -> int:
    """Jours restants avant le concert (0 = aujourd'hui, affiché « Ce soir »)."""
    return (concert_date - day).days


def key_group(number: int) -> int:
    """Groupe de couleur (0 à 3) de la touche `number` (1, 2, …), cycle de 16."""
    return ((number - 1) % BASE_KEYS) // GROUP_SIZE


@dataclass(frozen=True)
class DashboardKey:
    number: int                 # 1, 2, … (Q2)
    concert: ConcertSummary
    state: ConcertState
    countdown: int              # jours avant le concert
    group: int                  # 0 rouge, 1 orange, 2 jaune, 3 blanc


@dataclass(frozen=True)
class SetlistsCounters:
    """Setlists sans touche, comptées par l'indicateur vers SETLISTS."""

    undated: int
    past: int
    cancelled: int


@dataclass(frozen=True)
class DashboardView:
    day: date
    order: SortOrder
    keys: tuple[DashboardKey, ...]      # toutes les touches, classement continu
    counters: SetlistsCounters

    @property
    def base_keys(self) -> tuple[DashboardKey, ...]:
        return self.keys[:BASE_KEYS]

    @property
    def overflow_keys(self) -> tuple[DashboardKey, ...]:
        """Touches 17 et suivantes (zone défilante, D31)."""
        return self.keys[BASE_KEYS:]

    @property
    def free_slots(self) -> int:
        """Emplacements INIT parmi les 16 de base."""
        return max(0, BASE_KEYS - len(self.keys))

    @property
    def is_empty(self) -> bool:
        """Aucun concert à venir : état vide du dashboard."""
        return not self.keys

    @property
    def upcoming_count(self) -> int:
        return len(self.keys)


def alphabetical_key(name: str) -> tuple[str, str]:
    """Clé d'ordre alphabétique français (D6) : sans casse ni accents, puis nom exact."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    base = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return (base, name)


def _sort_key(concert: ConcertSummary, order: SortOrder):
    ordinal = concert.concert_date.toordinal()
    if order is SortOrder.NEWEST_FIRST:
        ordinal = -ordinal
    # D6 : à date égale, ordre alphabétique français ; l'id garantit un ordre stable
    return (ordinal, alphabetical_key(concert.name), concert.id)


def build_dashboard(concerts: list[ConcertSummary], now: datetime,
                    order: SortOrder = DEFAULT_SORT) -> DashboardView:
    day = scenix16_day(now)
    next_date = _next_date(concerts, day)
    states = {c.id: concert_state(c, day, next_date) for c in concerts}

    on_keys = sorted((c for c in concerts if states[c.id] in ON_DASHBOARD),
                     key=lambda c: _sort_key(c, order))
    keys = tuple(
        DashboardKey(
            number=index,
            concert=c,
            state=states[c.id],
            countdown=countdown_days(c.concert_date, day),
            group=key_group(index),
        )
        for index, c in enumerate(on_keys, start=1)
    )
    counters = SetlistsCounters(
        undated=sum(s is ConcertState.UNDATED for s in states.values()),
        past=sum(s is ConcertState.PAST for s in states.values()),
        cancelled=sum(s is ConcertState.CANCELLED for s in states.values()),
    )
    return DashboardView(day, order, keys, counters)
