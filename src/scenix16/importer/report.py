"""Rapport d'import en Markdown."""

from __future__ import annotations

from datetime import datetime

from scenix16.importer.excel import WorkbookData


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", "\\n")


def build_report(data: WorkbookData, tracks: int, setlists: int, entries: int) -> str:
    lines = [
        "# Rapport d'import du classeur SceniX16",
        "",
        f"- Date de l'import : {datetime.now():%d/%m/%Y %H:%M}",
        f"- Fichier source : `{data.source_path.name}` (lu en lecture seule, non modifié)",
        f"- Empreinte SHA-256 : `{data.sha256}`",
        f"- Importé : {tracks} morceaux, {setlists} setlists, {entries} entrées de setlist",
        "",
        "Les données sont reprises telles quelles : aucune valeur n'a été corrigée. "
        "Les points ci-dessous sont des particularités à vérifier, pas nécessairement des erreurs.",
        "",
        "## Setlists importées",
        "",
        "| Feuille | Nom (source) | Date | Salle / lieu | Titres |",
        "|---|---|---|---|---|",
    ]
    for s in data.setlists:
        when = s.concert_date.strftime("%d/%m/%Y") if s.concert_date else "DATE À DÉFINIR"
        lines.append(
            f"| {s.sheet} | {_cell(s.name)} ({s.name_source}) | {when} | "
            f"`{_cell(repr(s.venue))}` | {len(s.entries)} |"
        )
    lines += ["", f"## Particularités à vérifier ({len(data.findings)})", ""]
    if not data.findings:
        lines.append("Aucune particularité détectée.")
    for f in data.findings:
        lines += [f"### {f.title}", "", f.detail, "", "| Cellule | Précision |", "|---|---|"]
        lines += [f"| {_cell(ref)} | {_cell(note)} |" for ref, note in f.cells]
        lines.append("")
    return "\n".join(lines) + "\n"
