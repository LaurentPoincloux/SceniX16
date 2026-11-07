"""Lecture fidèle du classeur SceniX16 (lecture seule).

Le fichier est lu une seule fois en mémoire ; openpyxl travaille sur cette
copie et le classeur original n'est jamais ouvert en écriture.

Règles appliquées (plan technique, décision « import tel quel ») :
- les valeurs sont reprises sans aucune correction (espaces, retours à la
  ligne, casse, doublons) ;
- les réglages des morceaux viennent de TRACKS ; les colonnes KEY / MK /
  VIRUS|TI des feuilles de concert sont des formules qui recopient TRACKS et
  ne servent pas de source ;
- le nom d'un concert vient de l'étiquette MAIN qui pointe vers sa feuille,
  sa date de la cellule K2, sa salle / lieu de la cellule I2 (D16) ;
- les concerts importés sont ceux listés dans SETLISTS ;
- les particularités sont signalées comme « à vérifier », jamais corrigées.
"""

from __future__ import annotations

import hashlib
import io
import re
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl

TRACKS_SHEET = "TRACKS"
SETLISTS_SHEET = "SETLISTS"
MAIN_SHEET = "MAIN"
SETLIST_PREFIX = "SETLIST_"
PLACEHOLDER = "-/-"


@dataclass
class TrackRow:
    position: int
    title: str
    key: str | None
    mk: str | None
    virus: str | None
    virus_status: str | None
    source_row: int

    @property
    def source_cell(self) -> str:
        return f"{TRACKS_SHEET}!A{self.source_row}"


@dataclass
class EntryRow:
    position: int
    title: str
    source_cell: str


@dataclass
class SetlistSheet:
    sheet: str
    name: str
    name_source: str
    concert_date: date | None
    venue: str | None
    entries: list[EntryRow] = field(default_factory=list)


@dataclass
class Finding:
    code: str
    title: str
    detail: str
    cells: list[tuple[str, str]] = field(default_factory=list)  # (cellule, précision)


@dataclass
class WorkbookData:
    source_path: Path
    sha256: str
    tracks: list[TrackRow]
    setlists: list[SetlistSheet]
    findings: list[Finding]


def _text(value) -> str | None:
    """Valeur de cellule en texte, sans aucune retouche."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _has_edge_spaces(value: str) -> bool:
    """Espace en début ou fin de texte, ou juste avant / après un retour à la ligne."""
    if not value.strip():
        return False
    return any(line != line.strip(" ") for line in value.split("\n"))


def _show(value: str) -> str:
    """Rend visibles espaces de bord et retours à la ligne pour le rapport."""
    return repr(value)


class WorkbookFormatError(Exception):
    """Le fichier n'est pas un classeur SceniX16 lisible. Message destiné à l'utilisateur."""


NOT_SCENIX16 = "Ce fichier n'a pas la structure du classeur SceniX16"


def _header(ws, ref: str) -> str:
    value = ws[ref].value
    return str(value).strip().casefold() if value is not None else ""


def validate_structure(wb) -> None:
    """Vérifie les éléments indispensables à la lecture, avant toute lecture des données."""
    missing = [s for s in (MAIN_SHEET, SETLISTS_SHEET, TRACKS_SHEET) if s not in wb.sheetnames]
    if missing:
        raise WorkbookFormatError(f"{NOT_SCENIX16} : feuille(s) absente(s) : {', '.join(missing)}.")

    tracks = wb[TRACKS_SHEET]
    expected = {"A1": ("title",), "B1": ("key",), "D1": ("virus",), "E1": ("virus status",)}
    wrong = [ref for ref, starts in expected.items()
             if not _header(tracks, ref).startswith(starts)]
    if wrong:
        raise WorkbookFormatError(
            f"{NOT_SCENIX16} : en-têtes de la feuille TRACKS inattendus "
            f"({', '.join(f'TRACKS!{r}' for r in wrong)}).")

    if not _header(wb[SETLISTS_SHEET], "A1").startswith("shows"):
        raise WorkbookFormatError(f"{NOT_SCENIX16} : en-tête SETLISTS!A1 inattendu.")

    listed = wb[SETLISTS_SHEET]
    for r in range(2, listed.max_row + 1):
        sheet = listed.cell(r, 1).value
        if not sheet or str(sheet) not in wb.sheetnames:
            continue  # feuille absente : signalée comme particularité, non importée
        ws = wb[str(sheet)]
        if not (_header(ws, "B1") == "title" and _header(ws, "I1").startswith("lieu")
                and _header(ws, "K1").startswith("date")):
            raise WorkbookFormatError(
                f"{NOT_SCENIX16} : la feuille {sheet} n'a pas les colonnes TITLE / Lieu / Date "
                "attendues (B1, I1, K1).")


def read_workbook(path: Path) -> WorkbookData:
    try:
        raw = Path(path).read_bytes()  # lecture seule, une seule fois
    except OSError as exc:
        raise WorkbookFormatError(f"Le fichier ne peut pas être lu : {exc.strerror or exc}.") from exc
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        with warnings.catch_warnings():
            # extensions Excel (validations, MFC) non gérées par openpyxl : sans effet sur les données
            warnings.simplefilter("ignore", UserWarning)
            wb = openpyxl.load_workbook(io.BytesIO(raw))
            cached = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    except Exception as exc:  # fichier non Excel, archive endommagée, format .xls…
        raise WorkbookFormatError(
            "Ce fichier n'est pas un classeur Excel (.xlsx) lisible.") from exc

    validate_structure(wb)
    try:
        findings: list[Finding] = []
        tracks = _read_tracks(wb, findings)
        setlists = _read_setlists(wb, cached, tracks, findings)
        _track_findings(tracks, findings)
    except Exception as exc:
        raise WorkbookFormatError(
            f"{NOT_SCENIX16} : lecture impossible ({type(exc).__name__}).") from exc
    return WorkbookData(Path(path), sha256, tracks, setlists, findings)


# --- TRACKS -----------------------------------------------------------------

def _read_tracks(wb, findings: list[Finding]) -> list[TrackRow]:
    ws = wb[TRACKS_SHEET]
    headers = [ws.cell(1, col).value for col in range(1, 6)]
    blank = [
        (f"{TRACKS_SHEET}!{ws.cell(1, col).column_letter}1", _show(h if h is not None else ""))
        for col, h in enumerate(headers, start=1)
        if h is None or str(h).strip() == ""
    ]
    if blank:
        findings.append(Finding(
            "entete-vide", "Colonne sans en-tête dans TRACKS",
            "L'en-tête ne contient que des espaces (ou rien). Dans les feuilles de concert, "
            "cette colonne s'appelle « MK ». La valeur est reprise telle quelle.",
            blank,
        ))

    rows: list[TrackRow] = []
    for r in range(2, ws.max_row + 1):
        title = _text(ws.cell(r, 1).value)
        if title is None:
            continue
        rows.append(TrackRow(
            position=len(rows) + 1,
            title=title,
            key=_text(ws.cell(r, 2).value),
            mk=_text(ws.cell(r, 3).value),
            virus=_text(ws.cell(r, 4).value),
            virus_status=_text(ws.cell(r, 5).value),
            source_row=r,
        ))
    return rows


def _track_findings(tracks: list[TrackRow], findings: list[Finding]) -> None:
    columns = (("title", "A", "titre"), ("key", "B", "KEY"), ("mk", "C", "MK"),
               ("virus", "D", "VIRUS|TI"), ("virus_status", "E", "Virus Status"))

    # Patchs attribués à plusieurs morceaux
    for attr, col, label in (("virus", "D", "VIRUS|TI"), ("mk", "C", "MK")):
        groups: dict[str, list[TrackRow]] = defaultdict(list)
        for t in tracks:
            value = getattr(t, attr)
            if value and value != PLACEHOLDER:
                groups[value].append(t)
        for value, items in groups.items():
            if len(items) > 1:
                findings.append(Finding(
                    "patch-partage", f"Patch {label} {_show(value)} attribué à {len(items)} morceaux",
                    "Plusieurs morceaux utilisent le même patch. Ce peut être voulu ; à vérifier.",
                    [(f"{TRACKS_SHEET}!{col}{t.source_row}", t.title) for t in items],
                ))

    # Écriture de patch Virus différente de la forme majoritaire « RAM-D 75 »
    odd = [t for t in tracks if t.virus and re.match(r"^RAM-D\S", t.virus)]
    if odd:
        findings.append(Finding(
            "format-patch", "Patch VIRUS|TI écrit sans espace",
            "Ces valeurs s'écrivent « RAM-D96 » alors que les autres suivent la forme « RAM-D 75 ».",
            [(f"{TRACKS_SHEET}!D{t.source_row}", f"{t.title} : {_show(t.virus)}") for t in odd],
        ))

    # Retours à la ligne et espaces en début ou fin de texte
    breaks, spaces = [], []
    for t in tracks:
        for attr, col, label in columns:
            value = getattr(t, attr)
            if not value:
                continue
            ref = f"{TRACKS_SHEET}!{col}{t.source_row}"
            if "\n" in value:
                breaks.append((ref, f"{label} : {_show(value)}"))
            if _has_edge_spaces(value):
                spaces.append((ref, f"{label} : {_show(value)}"))
    if breaks:
        findings.append(Finding(
            "retour-ligne-tracks", "Retours à la ligne dans TRACKS",
            "Le texte contient un retour à la ligne ; il est conservé et s'affichera sur deux lignes.",
            breaks,
        ))
    if spaces:
        findings.append(Finding(
            "espaces-tracks", "Espaces en bord de ligne dans TRACKS",
            "Les espaces sont conservés tels quels.",
            spaces,
        ))

    missing = [(f"{TRACKS_SHEET}!D{t.source_row}", t.title) for t in tracks if not t.virus]
    if missing:
        findings.append(Finding(
            "sans-patch-virus", "Morceau sans patch VIRUS|TI",
            "La case VIRUS|TI est vide.",
            missing,
        ))

    placeholders = [
        (f"{TRACKS_SHEET}!{col}{t.source_row}", f"{t.title} : {label}")
        for t in tracks for attr, col, label in columns[1:4]
        if getattr(t, attr) == PLACEHOLDER
    ]
    if placeholders:
        findings.append(Finding(
            "valeur-tiret", "Valeur « -/- »",
            "Valeur saisie « -/- » (absence de réglage indiquée explicitement), conservée telle quelle.",
            placeholders,
        ))


# --- SETLISTS ---------------------------------------------------------------

def _main_labels(wb) -> dict[str, tuple[str, str]]:
    """Feuille ciblée -> (étiquette, cellule MAIN), d'après les liens de MAIN."""
    labels: dict[str, tuple[str, str]] = {}
    ws = wb[MAIN_SHEET]
    for row in ws.iter_rows():
        for cell in row:
            link = cell.hyperlink
            if link is None or not link.location or cell.value is None:
                continue
            sheet = link.location.split("!")[0].strip("'")
            labels.setdefault(sheet, (_text(cell.value), f"{MAIN_SHEET}!{cell.coordinate}"))
    return labels


def _read_setlists(wb, cached, tracks: list[TrackRow], findings: list[Finding]) -> list[SetlistSheet]:
    ws = wb[SETLISTS_SHEET]
    labels = _main_labels(wb)
    by_title = {t.title: t for t in tracks}
    by_fold: dict[str, list[TrackRow]] = defaultdict(list)
    for t in tracks:
        by_fold[t.title.casefold()].append(t)

    listed: list[tuple[str, date | None, str]] = []
    for r in range(2, ws.max_row + 1):
        sheet = _text(ws.cell(r, 1).value)
        if sheet:
            listed.append((sheet, _as_date(ws.cell(r, 2).value), f"{SETLISTS_SHEET}!B{r}"))

    result: list[SetlistSheet] = []
    venue_breaks, venue_spaces, date_gaps, zeros = [], [], [], defaultdict(list)
    for sheet, listed_date, listed_ref in listed:
        if sheet not in wb.sheetnames:
            findings.append(Finding(
                "feuille-absente", f"Feuille {sheet} introuvable",
                "Listée dans SETLISTS mais absente du classeur ; non importée.",
                [(listed_ref.replace("!B", "!A"), sheet)],
            ))
            continue
        sh = wb[sheet]
        label, label_ref = labels.get(sheet, (None, None))
        if label:
            name, name_source = label, label_ref
        else:
            name, name_source = sheet, f"{SETLISTS_SHEET} (nom de feuille)"
            findings.append(Finding(
                "nom-sans-etiquette", f"Aucune étiquette MAIN pour {sheet}",
                "Le nom de la feuille est utilisé comme nom du concert.", [(sheet, sheet)],
            ))
        concert_date = _as_date(sh["K2"].value)
        venue = _text(sh["I2"].value)
        if venue and "\n" in venue:
            venue_breaks.append((f"{sheet}!I2", _show(venue)))
        if venue and _has_edge_spaces(venue):
            venue_spaces.append((f"{sheet}!I2", _show(venue)))
        if listed_date != concert_date:
            date_gaps.append((f"{sheet}!K2", f"K2 = {concert_date} ; {listed_ref} = {listed_date}"))

        item = SetlistSheet(sheet, name, name_source, concert_date, venue)
        csh = cached[sheet]
        for r in range(2, sh.max_row + 1):
            title = _text(sh.cell(r, 2).value)
            if title is None:
                continue
            ref = f"{sheet}!B{r}"
            track = by_title.get(title)
            if track is None:
                candidates = by_fold.get(title.casefold(), [])
                if len(candidates) == 1:
                    track = candidates[0]
                    findings.append(Finding(
                        "titre-casse", f"Titre retrouvé sans tenir compte de la casse : {_show(title)}",
                        "Excel associe ce titre à TRACKS sans distinguer majuscules et minuscules.",
                        [(ref, track.source_cell)],
                    ))
                else:
                    findings.append(Finding(
                        "titre-absent", f"Titre absent de TRACKS : {_show(title)}",
                        "Ce morceau n'a pas pu être relié à la bibliothèque ; il n'est pas importé.",
                        [(ref, title)],
                    ))
                    continue
            item.entries.append(EntryRow(len(item.entries) + 1, title, ref))
            # « 0 » affiché par Excel alors que la case de TRACKS est vide
            for col, attr, label, tcol in ((3, "key", "KEY", "B"), (4, "mk", "MK", "C"),
                                           (5, "virus", "VIRUS|TI", "D")):
                shown = csh.cell(r, col).value
                if shown in (0, "0") and not getattr(track, attr):
                    zeros[label].append((f"{sheet}!{csh.cell(r, col).column_letter}{r}",
                                         f"{track.title} ({TRACKS_SHEET}!{tcol}{track.source_row} vide)"))
        result.append(item)

    if venue_breaks:
        findings.append(Finding(
            "lieu-deux-lignes", "Salle / lieu réparti sur deux lignes",
            "La cellule I2 contient un retour à la ligne ; il est conservé tel quel.",
            venue_breaks,
        ))
    if venue_spaces:
        findings.append(Finding(
            "lieu-espaces", "Espace en bord de ligne dans la salle / lieu",
            "Les espaces sont conservés tels quels.",
            venue_spaces,
        ))
    if date_gaps:
        findings.append(Finding(
            "date-ecart", "Date différente entre SETLISTS et la feuille du concert",
            "La date de la cellule K2 est retenue (D16).", date_gaps,
        ))
    for label, cells in zeros.items():
        findings.append(Finding(
            "zero-affiche", f"« 0 » affiché dans des cases {label} vides",
            f"Excel affiche 0 parce que la case {label} du morceau est vide dans TRACKS. "
            "La valeur reprise est celle de TRACKS (vide).",
            cells,
        ))

    listed_names = {s for s, _, _ in listed}
    for sheet in wb.sheetnames:
        if sheet.startswith(SETLIST_PREFIX) and sheet not in listed_names:
            sh = wb[sheet]
            titles = sum(1 for r in range(2, sh.max_row + 1) if sh.cell(r, 2).value is not None)
            findings.append(Finding(
                "feuille-non-listee", f"Feuille {sheet} non listée dans SETLISTS",
                f"Non importée comme concert. Contenu : I2 = {_show(_text(sh['I2'].value) or '')}, "
                f"K2 = {_as_date(sh['K2'].value)}, {titles} titre(s). "
                "Il s'agit du modèle de setlist du classeur.",
                [(f"{sheet}!I2", "salle / lieu"), (f"{sheet}!K2", "date")],
            ))
    return result
