"""Licences et composants tiers (D59, section 12 — Design Book v0.45, incrément 2.6e).

Fenêtre en lecture seule, ouverte depuis « À propos », avec la même identité visuelle :
fond relevé, titre, marges 24/22/24/20, bouton « Fermer » neutre (orange au focus clavier).

- Navigation latérale par catégories (Présentation, Polices, Composants, Textes de
  référence) ; chaque élément affiche le nom, puis la licence et la version. Sélection :
  fond relevé et barre crème ; focus clavier : anneau orange autour de l'élément courant.
  ↑ ↓ passent d'un élément à l'autre (les intitulés de catégorie sont ignorés).
- Panneau de lecture : en-tête (nom, licence, version, fichier), puis le texte avec retour
  automatique à la ligne et défilement vertical seul. Les textes juridiques sont lus dans le
  dossier LICENCES et affichés tels quels, sans réécriture ni recomposition.
- Page « Présentation » : le contenu du LISEZ-MOI, structuré en titres, paragraphes et listes,
  produit à partir du catalogue (services/licenses_catalog.py), vérifié par les tests.
Aucune connexion : les adresses sont du texte, sans lien actif.
"""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QStyle, QStyledItemDelegate, QTextBrowser, QVBoxLayout)

from scenix16.paths import resource
from scenix16.services import licenses_catalog as cat
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY
from scenix16.ui.widgets.keyboard_focus_button import KEYBOARD_REASONS, KeyboardFocusButton

TITLE = "Licences et composants tiers"
SUMMARY = cat.SUMMARY_FILE
NAV_WIDTH = 272
ENTRY_ROLE = Qt.UserRole + 1          # LicenseEntry, ou None pour la page « Présentation »
KIND_ROLE = Qt.UserRole + 2           # « category » ou « entry »


def licenses_dir() -> Path:
    return resource("LICENCES")


def license_files(folder: Path | None = None) -> list[Path]:
    """Le LISEZ-MOI d'abord, puis les textes de licence par ordre alphabétique."""
    folder = folder or licenses_dir()
    files = sorted((p for p in folder.glob("*.txt") if p.name != SUMMARY), key=lambda p: p.name.lower())
    summary = folder / SUMMARY
    return ([summary] if summary.is_file() else []) + files


def read_legal_text(name: str, folder: Path | None = None) -> str:
    """Texte juridique tel qu'il est dans le fichier (seules les fins de ligne sont normalisées)."""
    return ((folder or licenses_dir()) / name).read_text(encoding="utf-8")


def _font(family: str, px: int, weight=QFont.Weight.Normal, spacing: float = 0.0, caps=False) -> QFont:
    font = QFont(family)
    font.setPixelSize(px)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    if caps:
        font.setCapitalization(QFont.AllUppercase)
    return font


# --- page « Présentation » ----------------------------------------------------------------------

def presentation_html() -> str:
    """Le LISEZ-MOI en titres, paragraphes et listes, à partir du catalogue (aucune donnée perdue)."""
    e = html.escape
    by_key = {x.key: x for x in cat.CATALOG}

    def item(entry: cat.LicenseEntry) -> str:
        return (f"<li><span class='name'>{e(entry.summary)}</span>"
                f"<br><span class='file'>{e(entry.file)}</span></li>")

    obligations = cat.OBLIGATIONS.split(" : ", 1)[1]
    parts = [
        f"<p>{e(cat.INTRO)}</p>",
        f"<h2>Polices</h2><p class='note'>{e(cat.FONTS_NOTE.capitalize())}.</p><ul>",
        *(f"<li><span class='name'>{e(x.summary)}</span><br>{e(x.licence)}"
          f"<br><span class='file'>{e(x.file)}</span></li>" for x in cat.entries(cat.FONTS)),
        "</ul><h2>Composants</h2><ul>",
        item(by_key["python"]),
        (f"<li><span class='name'>{e(by_key['qt'].summary)}</span>"
         f"<br><span class='file'>{e(by_key['qt'].file)}, {e(by_key['gpl3'].file)}</span>"
         f"<p class='sub'>{e(cat.QT_LIBRARIES_NOTE)}</p>"
         "<p class='sub'>Code source :<br>"
         + "<br>".join(f"{e(label)} — <span class='file'>{e(url)}</span>" for label, url in cat.QT_SOURCES)
         + "</p></li>"),
        item(by_key["openpyxl"]),
        (f"<li><span class='name'>{e(by_key['et_xmlfile'].summary)}</span>"
         f"<br><span class='file'>{e(by_key['et_xmlfile'].file)}</span>"
         f"<p class='sub'>({e(by_key['et_xmlfile_python'].summary)} : "
         f"<span class='file'>{e(by_key['et_xmlfile_python'].file)}</span>)</p></li>"),
        item(by_key["pyinstaller"]),
        "</ul><h2>Obligations de redistribution</h2>",
        f"<p>{e(obligations[0].upper() + obligations[1:])}</p>",
    ]
    style = (f"<style>"
             f"body {{ color:{t.TEXT}; font-family:'{t.FONT_UI[0]}'; font-size:13px; }}"
             f"h2 {{ color:{t.MUTED}; font-family:'{LABEL_FAMILY}'; font-size:11px; font-weight:600;"
             f" letter-spacing:1.4px; text-transform:uppercase; margin:18px 0 6px 0; }}"
             f"p {{ margin:0 0 8px 0; line-height:140%; }}"
             f"p.note {{ color:{t.MUTED}; }}"
             f"p.sub {{ color:{t.MUTED}; margin:4px 0 0 0; }}"
             f"ul {{ margin:0 0 4px 0; -qt-list-indent:1; }}"
             f"li {{ margin:0 0 10px 0; line-height:140%; }}"
             f"span.name {{ color:{t.TEXT}; font-weight:600; }}"
             f"span.file {{ color:{t.MUTED}; font-family:'{MONO_FAMILY}'; font-size:12px; }}"
             f"</style>")
    return style + "".join(parts)


# --- navigation -------------------------------------------------------------------------------------

class NavDelegate(QStyledItemDelegate):
    """Intitulés de catégorie en capitales grises ; éléments sur deux lignes (nom, licence · version)."""

    def __init__(self, view: "LicensesNav"):
        super().__init__(view)
        self.view = view

    def sizeHint(self, option, index) -> QSize:
        if index.data(KIND_ROLE) == "category":
            return QSize(option.rect.width(), 30)
        return QSize(option.rect.width(), 48 if index.data(ENTRY_ROLE) is not None else 36)

    def paint(self, p: QPainter, option, index) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect)
        if index.data(KIND_ROLE) == "category":
            p.setFont(_font(LABEL_FAMILY, 10, QFont.Weight.DemiBold, 1.4, caps=True))
            p.setPen(QColor(t.DIM))
            p.drawText(r.adjusted(12, 8, -8, 0), Qt.AlignLeft | Qt.AlignVCenter, index.data(Qt.DisplayRole))
            p.restore()
            return
        box = r.adjusted(4, 2, -4, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.RAISED if selected else t.LINE_SOFT))
            p.drawRoundedRect(box, 5, 5)
        if selected:                                               # barre crème : élément sélectionné
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.SILK))
            p.drawRoundedRect(QRectF(box.left() + 6, box.top() + 9, 3, box.height() - 18), 1.5, 1.5)
        if self.view.keyboard_focus and index == self.view.currentIndex() and self.view.hasFocus():
            p.setPen(QPen(QColor(t.BRAND), 2))                     # focus clavier : anneau orange
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(1, 1, -1, -1), 5, 5)
        entry = index.data(ENTRY_ROLE)
        x = box.left() + 18
        width = box.width() - 26
        name_font = _font(t.FONT_UI[0], 13, QFont.Weight.DemiBold if selected else QFont.Weight.Medium)
        p.setFont(name_font)
        p.setPen(QColor(t.SILK if selected else t.TEXT))
        name = QFontMetrics(name_font).elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, int(width))
        if entry is None:
            p.drawText(QRectF(x, box.top(), width, box.height()), Qt.AlignLeft | Qt.AlignVCenter, name)
        else:
            p.drawText(QRectF(x, box.top() + 6, width, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
            meta_font = _font(MONO_FAMILY, 11)
            p.setFont(meta_font)
            p.setPen(QColor(t.MUTED))
            meta = QFontMetrics(meta_font).elidedText(cat.entry_meta(entry), Qt.ElideRight, int(width))
            p.drawText(QRectF(x, box.top() + 24, width, 16), Qt.AlignLeft | Qt.AlignVCenter, meta)
        p.restore()


class LicensesNav(QListWidget):
    """Liste de navigation : l'anneau orange n'apparaît qu'au focus clavier."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LicensesNav")
        self.keyboard_focus = False
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setItemDelegate(NavDelegate(self))
        self.setFixedWidth(NAV_WIDTH)

    def focusInEvent(self, event):
        if event.reason() in KEYBOARD_REASONS:
            self.keyboard_focus = True
        elif event.reason() != Qt.ActiveWindowFocusReason:
            self.keyboard_focus = False
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event):
        if event.reason() != Qt.ActiveWindowFocusReason:
            self.keyboard_focus = False
        super().focusOutEvent(event)
        self.viewport().update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.keyboard_focus = True                # navigation au clavier dans la liste
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.keyboard_focus = False                   # clic : pas d'anneau
        super().mousePressEvent(event)


# --- fenêtre ------------------------------------------------------------------------------------------

class LicensesDialog(QDialog):
    def __init__(self, parent=None, folder: Path | None = None):
        super().__init__(parent)
        self.setObjectName("LicensesDialog")
        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.resize(980, 640)
        self.folder = folder or licenses_dir()
        self.files = license_files(self.folder)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)            # mêmes marges que « À propos »
        layout.setSpacing(10)
        self.title_label = QLabel(TITLE, objectName="DialogTitle")
        layout.addWidget(self.title_label)
        self.subtitle_label = QLabel("Textes officiels complets, en lecture seule", objectName="AboutVersion")
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(6)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.list = LicensesNav()
        body.addWidget(self.list)

        self.reader = QFrame(objectName="LicensesReader")
        reader = QVBoxLayout(self.reader)
        reader.setContentsMargins(20, 16, 12, 12)
        reader.setSpacing(4)
        self.header_name = QLabel(objectName="LicensesHeaderName")
        self.header_meta = QLabel(objectName="LicensesHeaderMeta")
        self.header_meta.setWordWrap(True)
        reader.addWidget(self.header_name)
        reader.addWidget(self.header_meta)
        reader.addSpacing(8)
        self.text = QTextBrowser(objectName="LicensesText")
        self.text.setReadOnly(True)
        self.text.setOpenLinks(False)                         # aucune connexion
        self.text.setLineWrapMode(QTextBrowser.WidgetWidth)    # retour automatique à la ligne
        self.text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text.setFrameShape(QFrame.NoFrame)
        reader.addWidget(self.text, 1)
        body.addWidget(self.reader, 1)
        layout.addLayout(body, 1)

        layout.addSpacing(6)
        row = QHBoxLayout()
        row.addStretch(1)
        self.close_button = KeyboardFocusButton("Fermer")    # même bouton que « À propos »
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        row.addWidget(self.close_button)
        layout.addLayout(row)

        self._fill_navigation()
        self.list.currentItemChanged.connect(lambda current, _previous: self._show(current))
        self.list.setCurrentRow(self._first_entry_row())

    # --- navigation -----------------------------------------------------------------------------
    def _add(self, text: str, kind: str, entry: cat.LicenseEntry | None = None) -> None:
        item = QListWidgetItem(text)
        item.setData(KIND_ROLE, kind)
        item.setData(ENTRY_ROLE, entry)
        if kind == "category":
            item.setFlags(Qt.NoItemFlags)                     # intitulé : ni sélection, ni focus
        else:
            label = text if entry is None else f"{entry.name}, {cat.entry_meta(entry)}"
            item.setData(Qt.AccessibleTextRole, label)
        self.list.addItem(item)

    def _fill_navigation(self) -> None:
        self._add(cat.PRESENTATION, "category")
        self._add("Vue d'ensemble", "entry", None)
        for category in cat.CATEGORIES[1:]:
            self._add(category, "category")
            for entry in cat.entries(category):
                self._add(entry.name, "entry", entry)

    def _first_entry_row(self) -> int:
        for row in range(self.list.count()):
            if self.list.item(row).data(KIND_ROLE) == "entry":
                return row
        return 0

    def entry_rows(self) -> list[int]:
        return [r for r in range(self.list.count()) if self.list.item(r).data(KIND_ROLE) == "entry"]

    # --- lecture --------------------------------------------------------------------------------
    def _show(self, item: QListWidgetItem | None) -> None:
        if item is None or item.data(KIND_ROLE) != "entry":
            return
        entry = item.data(ENTRY_ROLE)
        if entry is None:
            self.header_name.setText(cat.PRESENTATION)
            self.header_meta.setText(f"Dossier LICENCES · {SUMMARY}")
            self.text.setHtml(presentation_html())
        else:
            self.header_name.setText(entry.name)
            details = [entry.licence] + ([f"version {entry.version}"] if entry.version else []) + [entry.file]
            self.header_meta.setText(" · ".join(details))
            self.text.document().setDefaultFont(_font(MONO_FAMILY, 12))
            self.text.setPlainText(read_legal_text(entry.file, self.folder))   # texte juridique tel quel
        self.text.document().setDocumentMargin(4)
        self.text.verticalScrollBar().setValue(0)

    def current_entry(self) -> cat.LicenseEntry | None:
        item = self.list.currentItem()
        return item.data(ENTRY_ROLE) if item is not None else None
