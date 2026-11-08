"""Barre de menus de l'application (D59, Design Book v0.43) : « Fichier » et « Aide ».

Conventions de Windows, vérifiées par un prototype avant 2.6c :
- Alt (appui puis relâchement) met « Fichier » en évidence sans l'ouvrir ; Alt+F ouvre
  Fichier, Alt+A ouvre Aide ; flèches et Échap pour naviguer et refermer. Qt le fait
  nativement, y compris pour une barre placée dans la barre supérieure.
- F10 : sans effet dans Qt ; la fenêtre principale le relie à activate_from_keyboard(),
  qui suit le même chemin que Alt.
- Lettres soulignées : visibles seulement en navigation clavier (Alt maintenu, F10,
  barre ou menu ouverts au clavier) ; masquées au repos et à l'ouverture à la souris.
  Le réglage ne concerne que la barre et ses menus (style propre à ces widgets).

Apparence : police d'interface 13 px ; survol et menu ouvert en fond relevé ; menus
déroulants en fond relevé, bordure line/strong, rayon 6 px, raccourcis alignés à droite
en gris. Le panneau et les éléments des menus déroulants sont dessinés par
KeyboardMenuStyle, sans règle de feuille de style : une telle règle ferait dessiner les
éléments par Qt avec la palette claire par défaut (texte noir, défaut corrigé en 2.6d).
"""

from __future__ import annotations

import weakref

import shiboken6
from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeyEvent, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QMenu, QMenuBar, QProxyStyle, QStyle, QStyleOptionMenuItem)

from scenix16.ui.theme import tokens as t

FILE_MENU = "&Fichier"
HELP_MENU = "&Aide"
QUIT_ITEM = "&Quitter"
ABOUT_ITEM = "À &propos de SceniX16"
QUIT_SHORTCUT = "Ctrl+Q"

ITEM_PAD_X, ITEM_PAD_Y = 10, 7
SHORTCUT_GAP = 24
MENU_MIN_WIDTH = 230
MENU_RADIUS = 6
MENU_PADDING = 4


def _ui_font(px: int = 13) -> QFont:
    font = QFont(t.FONT_UI[0])
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.Medium)
    return font


def _shortcut_font() -> QFont:
    font = QFont(t.FONT_MONO[0])
    font.setPixelSize(12)
    font.setWeight(QFont.Weight.Medium)
    return font


class KeyboardMenuStyle(QProxyStyle):
    """Style de la barre et de ses menus : soulignés en navigation clavier seulement,
    éléments de menu dessinés selon le Design Book (raccourci gris aligné à droite)."""

    def __init__(self):
        super().__init__("Fusion")
        self.show_mnemonics = False

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_MenuBar_AltKeyNavigation:
            return 1
        if hint == QStyle.SH_UnderlineShortcut:
            return 1 if self.show_mnemonics else 0
        return super().styleHint(hint, option, widget, returnData)

    def _mnemonic_flag(self) -> int:
        return int(Qt.TextShowMnemonic if self.show_mnemonics else Qt.TextHideMnemonic)

    def pixelMetric(self, metric, option=None, widget=None):
        if isinstance(widget, QMenu):
            if metric == QStyle.PM_MenuPanelWidth:
                return 1
            if metric in (QStyle.PM_MenuHMargin, QStyle.PM_MenuVMargin):
                return MENU_PADDING
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_PanelMenu:
            # menu déroulant : fond relevé, bordure line/strong, rayon 6 px (D59)
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(t.LINE_STRONG), 1))
            painter.setBrush(QColor(t.RAISED))
            painter.drawRoundedRect(QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5), MENU_RADIUS, MENU_RADIUS)
            painter.restore()
            return
        if element == QStyle.PE_FrameMenu:
            return                                  # bordure déjà tracée avec le panneau
        super().drawPrimitive(element, option, painter, widget)

    def sizeFromContents(self, ct, option, size, widget=None):
        if ct == QStyle.CT_MenuItem and isinstance(option, QStyleOptionMenuItem):
            if option.menuItemType == QStyleOptionMenuItem.Separator:
                return QSize(size.width(), 9)
            label, _, shortcut = option.text.partition("\t")
            fm, sm = QFontMetrics(_ui_font()), QFontMetrics(_shortcut_font())
            width = (2 * ITEM_PAD_X + fm.horizontalAdvance(label.replace("&", ""))
                     + (SHORTCUT_GAP + sm.horizontalAdvance(shortcut) if shortcut else 0))
            return QSize(max(width, MENU_MIN_WIDTH - 10), fm.height() + 2 * ITEM_PAD_Y)
        return super().sizeFromContents(ct, option, size, widget)

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.CE_MenuItem and isinstance(option, QStyleOptionMenuItem):
            self._draw_menu_item(option, painter)
            return
        super().drawControl(element, option, painter, widget)

    def _draw_menu_item(self, option: QStyleOptionMenuItem, p: QPainter) -> None:
        r = QRectF(option.rect)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if option.menuItemType == QStyleOptionMenuItem.Separator:
            p.fillRect(QRectF(r.left() + 6, r.center().y(), r.width() - 12, 1), QColor(t.LINE_SOFT))
            p.restore()
            return
        enabled = bool(option.state & QStyle.State_Enabled)
        if enabled and option.state & QStyle.State_Selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.CELL))
            p.drawRoundedRect(r, 4, 4)
        label, _, shortcut = option.text.partition("\t")
        text_rect = r.adjusted(ITEM_PAD_X, 0, -ITEM_PAD_X, 0)
        p.setFont(_ui_font())
        p.setPen(QColor(t.TEXT if enabled else t.DIM))
        p.drawText(text_rect, int(Qt.AlignLeft | Qt.AlignVCenter) | self._mnemonic_flag(), label)
        if shortcut:
            p.setFont(_shortcut_font())
            p.setPen(QColor(t.MUTED))
            p.drawText(text_rect, int(Qt.AlignRight | Qt.AlignVCenter), shortcut)
        p.restore()


class AppMenu(QMenu):
    """Menu déroulant : fond relevé, bordure line/strong, coins arrondis (6 px)."""

    def __init__(self, title: str, style: KeyboardMenuStyle, parent=None):
        super().__init__(title, parent)
        self.setObjectName("AppMenu")
        self.setStyle(style)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)


class _KeyboardModeTracker(QObject):
    """Soulignés visibles pendant la navigation au clavier, masqués sinon.

    Un seul filtre pour toute l'application (installé une fois), quel que soit le nombre de
    fenêtres : la touche Alt arrive au widget qui a le focus, pas à la barre. Le filtre propre
    de QMenuBar (navigation par Alt) reste intact.
    """

    _instance: "_KeyboardModeTracker | None" = None

    def __init__(self):
        super().__init__()
        self.bars: "weakref.WeakSet[AppMenuBar]" = weakref.WeakSet()

    @classmethod
    def register(cls, bar: "AppMenuBar") -> None:
        app = QApplication.instance()
        if cls._instance is None or cls._instance.parent() is not app:
            cls._instance = cls()
            cls._instance.setParent(app)
            app.installEventFilter(cls._instance)
        cls._instance.bars.add(bar)

    def _live_bars(self):
        return [bar for bar in list(self.bars) if shiboken6.isValid(bar)]

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind in (QEvent.KeyPress, QEvent.KeyRelease) and event.key() == Qt.Key_Alt                 and not event.isAutoRepeat():
            for bar in self._live_bars():
                if bar._concerns(watched):
                    bar._alt_down = kind == QEvent.KeyPress
                    if bar._alt_down:
                        bar._set_mnemonics(True)
                    else:
                        QTimer.singleShot(0, bar._sync)
        elif kind in (QEvent.MouseButtonPress, QEvent.NonClientAreaMouseButtonPress):
            for bar in self._live_bars():
                bar._set_mnemonics(False)
        elif kind in (QEvent.KeyRelease, QEvent.FocusOut, QEvent.Hide, QEvent.WindowDeactivate):
            for bar in self._live_bars():
                if bar.keyboard_style.show_mnemonics:
                    QTimer.singleShot(0, bar._sync)
        return False


class AppMenuBar(QMenuBar):
    quit_requested = Signal()
    about_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppMenuBar")
        self.setNativeMenuBar(False)
        self.keyboard_style = KeyboardMenuStyle()
        self.keyboard_style.setParent(self)
        self.setStyle(self.keyboard_style)
        self._alt_down = False

        self.file_menu = AppMenu(FILE_MENU, self.keyboard_style, self)
        self.addMenu(self.file_menu)
        self.quit_action = QAction(QUIT_ITEM, self)
        self.quit_action.setShortcut(QKeySequence(QUIT_SHORTCUT))
        # contexte par défaut (fenêtre) : inactif sous une boîte modale (D66, vérifié sous Windows)
        self.quit_action.setShortcutContext(Qt.WindowShortcut)
        self.quit_action.triggered.connect(self.quit_requested)
        self.file_menu.addAction(self.quit_action)

        self.help_menu = AppMenu(HELP_MENU, self.keyboard_style, self)
        self.addMenu(self.help_menu)
        self.about_action = QAction(ABOUT_ITEM, self)
        self.about_action.triggered.connect(self.about_requested)
        self.help_menu.addAction(self.about_action)

        _KeyboardModeTracker.register(self)          # suivi du mode clavier (soulignés)

    # --- soulignés en mode clavier --------------------------------------------
    def mnemonics_visible(self) -> bool:
        return self.keyboard_style.show_mnemonics

    def _set_mnemonics(self, on: bool) -> None:
        if self.keyboard_style.show_mnemonics != on:
            self.keyboard_style.show_mnemonics = on
            self.update()
            for menu in (self.file_menu, self.help_menu):
                if menu.isVisible():
                    menu.update()

    def _sync(self) -> None:
        """Fin du mode clavier : barre inactive, aucun menu ouvert, Alt relâché."""
        menus_open = self.file_menu.isVisible() or self.help_menu.isVisible()
        if self.activeAction() is None and not menus_open and not self._alt_down:
            self._set_mnemonics(False)

    def _concerns(self, watched: QObject) -> bool:
        """Touche Alt reçue par un widget de la fenêtre de la barre (ou par ses menus)."""
        window_of = getattr(watched, "window", None)
        if not callable(window_of):
            return False
        window = window_of()
        return window is self.window() or window in (self.file_menu, self.help_menu)

    def activate_from_keyboard(self) -> None:
        """F10 : même chemin que Alt — « Fichier » en évidence, sans ouvrir le menu."""
        self._set_mnemonics(True)
        window = self.window()
        QApplication.sendEvent(window, QKeyEvent(QEvent.KeyPress, Qt.Key_Alt, Qt.AltModifier))
        QApplication.sendEvent(window, QKeyEvent(QEvent.KeyRelease, Qt.Key_Alt, Qt.NoModifier))
