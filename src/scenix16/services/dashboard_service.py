"""Chiffres affichés autour du dashboard (barre supérieure, barre d'état).

Lit la base en lecture seule (repository) et applique les règles du domaine.
L'instant courant est fourni par l'appelant : aucune lecture d'horloge ici.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scenix16.domain.dashboard import DEFAULT_SORT, DashboardView, SortOrder, build_dashboard
from scenix16.storage.repository import count_tracks, read_concert_summaries
from scenix16.storage.userdata import database_path


@dataclass(frozen=True)
class DashboardSummary:
    view: DashboardView | None
    track_count: int
    setlist_count: int

    @property
    def upcoming(self) -> int:
        return self.view.upcoming_count if self.view else 0

    @property
    def past(self) -> int:
        return self.view.counters.past if self.view else 0


EMPTY = DashboardSummary(None, 0, 0)


def load_summary(userdata: Path | None, now: datetime,
                 order: SortOrder = DEFAULT_SORT) -> DashboardSummary:
    """Résumé du dashboard. Base absente ou illisible : tous les compteurs à zéro."""
    if userdata is None:
        return EMPTY
    path = database_path(userdata)
    if not path.is_file():
        return EMPTY
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return EMPTY
    try:
        concerts = read_concert_summaries(connection)
        tracks = count_tracks(connection)
    except sqlite3.Error:
        return EMPTY
    finally:
        connection.close()
    return DashboardSummary(build_dashboard(concerts, now, order), tracks, len(concerts))


def plural(count: int, singular: str, plural_form: str) -> str:
    """Accord français : 0 et 1 au singulier."""
    return f"{count} {singular if count <= 1 else plural_form}"


def concerts_label(summary: DashboardSummary) -> str:
    """Repère de la barre supérieure : « N à venir · M passés »."""
    return f"{summary.upcoming} à venir · {plural(summary.past, 'passé', 'passés')}"


def date_label(now: datetime) -> str:
    """Date calendaire du jour (même entre minuit et 6 h)."""
    return now.strftime("%d/%m/%Y")


def countdown_label(days: int) -> str:
    """Pied d'un emplacement : « Ce soir » le jour du concert, sinon « J-n »."""
    return "Ce soir" if days == 0 else f"J-{days}"


STATE_TAGS = {"today": "AUJOURD'HUI", "next": "PROCHAIN", "upcoming": "À VENIR"}


def card_venue(venue: str | None) -> str:
    """Salle / lieu sur une ligne, pour l'affichage dans une carte uniquement (arbitrage C)."""
    return (venue or "").replace("\r\n", " ").replace("\n", " ").strip()


def indicator_parts(view: DashboardView | None) -> tuple[str, str] | None:
    """Indicateur sous les emplacements (D5, D22) ; None s'il n'y a rien à signaler."""
    if view is None or view.is_empty:
        return None
    c = view.counters
    parts = []
    if c.undated:
        parts.append(f"{c.undated} sans date")
    if c.past:
        parts.append(plural(c.past, "passé", "passés"))
    if c.cancelled:
        parts.append(plural(c.cancelled, "annulé", "annulés"))
    if not parts:
        return None
    left = f"{plural(view.upcoming_count, 'concert', 'concerts')} à venir sur le dashboard"
    return left, f"{' · '.join(parts)} dans SETLISTS →"


def empty_state_text(view: DashboardView | None) -> str:
    """Texte de l'état vide (section 06)."""
    text = "Les 16 touches sont libres (INIT)."
    if view is None:
        return text
    c = view.counters
    parts = []
    if c.past:
        parts.append(plural(c.past, "setlist passée", "setlists passées"))
    if c.undated:
        parts.append(plural(c.undated, "setlist sans date", "setlists sans date"))
    if c.cancelled:
        parts.append(plural(c.cancelled, "setlist annulée", "setlists annulées"))
    if parts:
        total = c.past + c.undated + c.cancelled
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " et " + parts[-1]
        verb = "est conservée" if total <= 1 else "sont conservées"
        text += f" {joined[0].upper() + joined[1:]} {verb} dans SETLISTS."
    return text


SORT_LABELS = {                       # D12 : mêmes mots sur le dashboard et dans SETLISTS
    SortOrder.OLDEST_FIRST: "Plus ancien d'abord",
    SortOrder.NEWEST_FIRST: "Plus récent d'abord",
}


def other_order(order: SortOrder) -> SortOrder:
    """Sens obtenu en activant le bouton de tri."""
    return SortOrder.NEWEST_FIRST if order is SortOrder.OLDEST_FIRST else SortOrder.OLDEST_FIRST


def sort_label(order: SortOrder) -> str:
    """Libellé D12 du sens affiché (l'interface le présente en capitales)."""
    return SORT_LABELS[order]


def sort_accessible_name(order: SortOrder) -> str:
    """Nom accessible : sens affiché et action d'inversion, avec les formulations D12."""
    return (f"Classement « {sort_label(order)} ». "
            f"Activer pour passer à « {sort_label(other_order(order))} ».")


def status_parts(summary: DashboardSummary) -> list[str]:
    """Barre d'état (section 07) : « SceniX16 · N titres au catalogue · M setlists »."""
    return [
        "SceniX16",
        f"{plural(summary.track_count, 'titre', 'titres')} au catalogue",
        plural(summary.setlist_count, "setlist", "setlists"),
    ]
