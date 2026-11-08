"""Données de la fiche du concert en consultation (D16, D45, D69 — incrément 2.7a).

Lit la base en lecture seule et prépare ce que la fiche affiche, sans interface :
- adresse de touche (« A03 ») : calculée par le domaine du dashboard (build_dashboard), avec
  la même référence que lui (jour SceniX16, sens de tri, banques) ; aucune règle n'est
  redéfinie ici ; None si le concert n'est pas sur le dashboard ;
- ligne d'en-tête « salle · jj/mm/aa · N titres », les parties vides étant omises ; la salle y est
  mise sur une seule ligne propre (ses lignes jointes par « · » depuis 2.9, espaces multiples
  réduits), le champ complet restant disponible ; le dashboard n'est pas concerné ;
- setlist complète, dans l'ordre, répétitions comprises ; valeurs telles que stockées
  (« -/- » compris), « — » pour une valeur vide ;
- infos pratiques, et indicateur « au moins un champ renseigné » (bloc masqué sinon) ;
- résumé du bloc replié (2.9, arbitrage C2) : l'horaire « Passage » (casse ignorée), sinon le
  premier horaire, puis le nombre de contacts ; seules les informations présentes apparaissent.
L'instant courant et le sens de tri sont fournis par l'appelant : aucune lecture d'horloge ici.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scenix16.domain.dashboard import DEFAULT_SORT, ConcertState, SortOrder, build_dashboard
from scenix16.domain.models import Contact, ScheduleItem, SetlistStatus
from scenix16.services.dashboard_service import tracks_label
from scenix16.storage.repository import read_concert_detail, read_concert_summaries
from scenix16.storage.userdata import database_path

EMPTY = "—"                     # tiret cadratin : valeur vide (D69)
UNDATED = "DATE À DÉFINIR"      # D5
MODE = "Consultation"


def shown(value: str | None) -> str:
    """Valeur d'un morceau telle que stockée ; « — » seulement si elle est vide (D69)."""
    return EMPTY if value is None or not value.strip() else value


def one_line(text: str | None) -> str:
    """Salle sur une ligne pour l'en-tête : chaque ligne nettoyée (espaces multiples réduits), les
    lignes non vides jointes par « · » (2.9) : « La Sirène / La Rochelle (17) » sur deux lignes
    donne « La Sirène · La Rochelle (17) »."""
    lines = (" ".join(line.split()) for line in (text or "").splitlines())
    return " · ".join(line for line in lines if line)


def short_date(d) -> str:
    """Date au format jj/mm/aa (D16)."""
    return d.strftime("%d/%m/%y")


@dataclass(frozen=True)
class SheetTrack:
    number: str                 # « 01 », position dans la setlist
    title: str
    key: str
    mk: str
    virus: str
    virus_status: str           # « ON », « OFF », ou « — »


@dataclass(frozen=True)
class ConcertSheet:
    id: int
    name: str
    key_address: str | None     # « A03 », None si le concert n'est pas sur le dashboard
    state: ConcertState | None  # état sur le dashboard, None s'il n'y est pas
    status: SetlistStatus
    heading: str                # « Touche A03 · Consultation », ou « Consultation »
    venue: str | None           # salle / lieu tel que stocké (retours à la ligne compris)
    date: str                   # « 21/06/26 » ou « DATE À DÉFINIR »
    meta: str                   # « Le Kiosque · 21/06/26 · 26 titres »
    tracks: tuple[SheetTrack, ...]
    address: str | None         # adresse postale, retours à la ligne conservés
    organizer: str | None
    notes: str | None
    contacts: tuple[Contact, ...]
    schedule: tuple[ScheduleItem, ...]
    visual_file: str | None

    @property
    def has_practical_info(self) -> bool:
        """Au moins un champ des infos pratiques est renseigné (sinon le bloc est masqué, D69)."""
        def filled(value: str | None) -> bool:
            return value is not None and bool(value.strip())

        return (filled(self.address) or filled(self.organizer) or filled(self.notes)
                or any(filled(v) for c in self.contacts for v in (c.name, c.role, c.phone, c.email))
                or any(filled(v) for s in self.schedule for v in (s.label, s.time)))


def load_concert_sheet(userdata: Path | None, setlist_id: int, now: datetime,
                       order: SortOrder = DEFAULT_SORT) -> ConcertSheet | None:
    """Fiche d'un concert, ou None (identifiant inconnu, base absente ou illisible).

    Une seule connexion en lecture seule : le classement du dashboard et le détail sont lus
    dans le même état de la base. La base n'est jamais modifiée.
    """
    if userdata is None:
        return None
    path = database_path(userdata)
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        detail = read_concert_detail(connection, setlist_id)
        if detail is None:
            return None
        view = build_dashboard(read_concert_summaries(connection), now, order)
    except sqlite3.Error:
        return None
    finally:
        connection.close()

    key = view.key_of_concert(setlist_id)
    key_address = key.address if key is not None else None
    date_text = short_date(detail.concert_date) if detail.concert_date else UNDATED
    # salle sur une ligne propre ; le champ complet, retours à la ligne compris, reste dans venue
    meta = " · ".join(part for part in (one_line(detail.venue), date_text, tracks_label(len(detail.tracks)))
                      if part)
    return ConcertSheet(
        id=detail.id,
        name=detail.name,
        key_address=key_address,
        state=key.state if key is not None else None,
        status=detail.status,
        heading=f"Touche {key_address} · {MODE}" if key_address else MODE,
        venue=detail.venue,
        date=date_text,
        meta=meta,
        tracks=tuple(SheetTrack(f"{t.position:02d}", t.title, shown(t.key), shown(t.mk), shown(t.virus),
                                shown(t.virus_status)) for t in detail.tracks),
        address=detail.address,
        organizer=detail.organizer,
        notes=detail.notes,
        contacts=detail.contacts,
        schedule=detail.schedule,
        visual_file=detail.visual_file,
    )


PASSAGE_LABEL = "passage"


def filled(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def schedule_lines(sheet: ConcertSheet) -> list[tuple[str, str]]:
    """Horaires renseignés, dans l'ordre : (heure, libellé), sans espaces de bord."""
    return [((s.time or "").strip(), (s.label or "").strip())
            for s in sheet.schedule if filled(s.time) or filled(s.label)]


def listed_contacts(sheet: ConcertSheet) -> list[Contact]:
    """Contacts dont au moins un champ est renseigné."""
    return [c for c in sheet.contacts if any(filled(v) for v in (c.name, c.role, c.phone, c.email))]


def practical_summary(sheet: ConcertSheet) -> str:
    """Résumé du bloc « Infos pratiques » replié (C2) : « Passage 21:30 · 2 contacts ».

    Horaire « Passage » (casse ignorée), sinon le premier horaire ; nombre de contacts ; parties
    absentes omises ; chaîne vide s'il n'y a ni horaire ni contact."""
    parts = []
    lines = schedule_lines(sheet)
    if lines:
        time, label = next((line for line in lines if line[1].casefold() == PASSAGE_LABEL), lines[0])
        parts.append(" ".join(p for p in (label, time) if p))
    contacts = len(listed_contacts(sheet))
    if contacts:
        parts.append(f"{contacts} contact{'s' if contacts > 1 else ''}")
    return " · ".join(parts)
