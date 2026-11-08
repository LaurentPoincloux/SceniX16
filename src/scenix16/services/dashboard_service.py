"""Chiffres affichés autour du dashboard (barre supérieure, barre d'état).

Lit la base en lecture seule (repository) et applique les règles du domaine.
L'instant courant est fourni par l'appelant : aucune lecture d'horloge ici.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from scenix16.domain.dashboard import (DEFAULT_SORT, DashboardKey, DashboardView, SortOrder,
                                       address, bank_label, build_dashboard, scenix16_day)
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


@dataclass(frozen=True)
class InfoReadout:
    """Contenu de l'afficheur d'information de la barre supérieure (D60)."""

    upcoming: str          # « 23 »
    upcoming_label: str    # « À VENIR » (invariable)
    past: str              # « 6 »
    past_label: str        # « PASSÉ » / « PASSÉS »
    date: str              # « 07/11/2026 », jour SceniX16
    accessible: str        # « 23 concerts à venir, 6 passés, date de référence 7 novembre 2026 »


def date_label(now: datetime) -> str:
    """Date de référence du dashboard : le jour SceniX16 (D10, Q12) ; de 0 h à 5 h 59, la veille."""
    return scenix16_day(now).strftime("%d/%m/%Y")


def info_readout(summary: DashboardSummary, now: datetime) -> InfoReadout:
    """Afficheur (D60) : compteurs d'abord, date de référence en retrait."""
    day = scenix16_day(now)
    upcoming, past = summary.upcoming, summary.past
    accessible = (f"{plural(upcoming, 'concert', 'concerts')} à venir, {plural(past, 'passé', 'passés')}, "
                  f"date de référence {day_month_year(day)}")
    return InfoReadout(str(upcoming), "À VENIR", str(past), "PASSÉ" if past <= 1 else "PASSÉS",
                       date_label(now), accessible)


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


DAY_NAMES = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTH_NAMES = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
               "septembre", "octobre", "novembre", "décembre")


def long_date(d: date) -> str:
    """Date en toutes lettres, en français, sans dépendre de la langue du système.

    « samedi 7 novembre 2026 », « mardi 1er décembre 2026 ».
    """
    return f"{DAY_NAMES[d.weekday()]} {day_month_year(d)}"


def day_month_year(d: date) -> str:
    """« 7 novembre 2026 », « 1er décembre 2026 » (sans le jour de la semaine)."""
    day = "1er" if d.day == 1 else str(d.day)
    return f"{day} {MONTH_NAMES[d.month - 1]} {d.year}"


def tracks_label(count: int) -> str:
    return plural(count, "titre", "titres")


@dataclass(frozen=True)
class PreviewContent:
    """Contenu de l'aperçu au survol d'une paire (D64), par ordre d'importance."""

    address: str          # « B03 »
    tag: str              # « À VENIR », « PROCHAIN », « AUJOURD'HUI »
    emphasized: bool      # prochain ou aujourd'hui
    name: str             # nom complet, jamais tronqué
    venue: str            # lieu complet, retours à la ligne conservés
    date: str             # date en toutes lettres
    countdown: str        # « Ce soir », « J-12 »
    tracks: str           # « 18 titres »


def preview_content(key: DashboardKey) -> PreviewContent:
    c = key.concert
    venue = (c.venue or "").replace("\r\n", "\n").strip()
    return PreviewContent(
        address=key.address,
        tag=STATE_TAGS[key.state.value],
        emphasized=key.state.value in ("next", "today"),
        name=c.name,
        venue=venue,
        date=long_date(c.concert_date),
        countdown=countdown_label(key.countdown),
        tracks=tracks_label(c.track_count),
    )


def preview_description(key: DashboardKey) -> str:
    """Description accessible d'une touche et d'une carte : le contenu complet de l'aperçu."""
    p = preview_content(key)
    venue = ", ".join(x.strip() for x in p.venue.split("\n") if x.strip())
    parts = [f"{p.address}, {p.tag.capitalize()}.", f"{p.name}."]
    if venue:
        parts.append(f"{venue}.")
    parts.append(f"{p.date}, {p.countdown}.")
    parts.append(f"{p.tracks}.")
    return " ".join(parts)


def key_accessible_name(bank: int, position: int, key: DashboardKey | None) -> str:
    where = address(bank, position)
    return f"Touche {where} : {key.concert.name}" if key else f"Touche {where} : libre (INIT)"


def slot_accessible_name(bank: int, position: int, key: DashboardKey | None) -> str:
    where = address(bank, position)
    return f"Emplacement {where} : {key.concert.name}" if key else f"Emplacement {where} : libre (INIT)"


def bank_accessible_name(index: int, count: int) -> str:
    """Nom accessible d'un onglet : « Banque B : 4 concerts » ou « Banque C : vide »."""
    if count == 0:
        return f"Banque {bank_label(index)} : vide"
    return f"Banque {bank_label(index)} : {plural(count, 'concert', 'concerts')}"


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
