"""Écran de démarrage de SceniX16 (D72, Design Book v0.49 — incrément 2.8d).

QSplashScreen dont l'image est dessinée par SceniX16 (arbitrage B1) :
- environ 480 × 280 px logiques, fond sombre du thème, centré dans la zone disponible de
  l'écran de lancement (B6 mis à jour : écran sous le pointeur, sinon écran principal — le même
  que CONCERTS, voir ui.screens), image dessinée au facteur de cet écran ;
- logo scenix16.png, nom « SceniX16 », version (Q18) — seule dans l'exécutable (P1), suivie de
  « Version de développement » lancé depuis les sources — et le message de l'étape en cours ;
- statique : ni animation, ni pourcentage, ni barre (la réduction des animations est donc
  respectée d'office) ; image dessinée au facteur de l'écran (nette à 200 %) ;
- aucun bouton de barre des tâches, aucune priorité permanente au premier plan (P6) ;
- un clic ou Alt+F4 ne le ferment pas (P5) : seule la fermeture programmée est acceptée
  (finish() quand CONCERTS est affichée, dismiss() avant une boîte de démarrage ou en cas
  d'échec), et elle reste toujours possible.
Les messages des étapes sont regroupés ici, en français (D71 : traduction ultérieure).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPixmap, QScreen
from PySide6.QtWidgets import QSplashScreen

from scenix16 import __version__
from scenix16.paths import resource
from scenix16.startup import Step
from scenix16.ui.screens import centered_geometry, rect_of
from scenix16.ui.theme import tokens as t
from scenix16.ui.theme.fonts import LABEL_FAMILY, MONO_FAMILY
from scenix16.version import DEVELOPMENT_LABEL, BuildInfo, load_build_info

WIDTH, HEIGHT = 480, 280           # dimensions logiques (B6)
LOGO_HEIGHT = 56
MESSAGE_HEIGHT = 52                # bandeau du message, en bas
ACCESSIBLE_NAME = "SceniX16 — démarrage"

# Libellés des étapes réelles du démarrage (B2) ; le verrou d'instance n'a pas de message propre.
STEP_MESSAGES = {
    Step.STARTING: "Démarrage de SceniX16…",
    Step.STORAGE: "Vérification du dossier de données…",
    Step.DATABASE: "Ouverture de la base de données…",
    Step.INTERFACE: "Préparation de l'écran CONCERTS…",
}
# Nom des étapes dans le message et le rapport d'échec (B5)
STEP_NAMES = {
    Step.STARTING: "Démarrage de SceniX16",
    Step.STORAGE: "Vérification du dossier de données",
    Step.LOCK: "Vérification qu'aucun autre SceniX16 n'est ouvert",
    Step.DATABASE: "Ouverture de la base de données",
    Step.INTERFACE: "Préparation de l'écran CONCERTS",
}


def version_lines(info: BuildInfo | None, version: str = __version__) -> tuple[str, str | None]:
    """(version, mention) : « Version 0.1.0-dev » ; « Version de développement » sans fabrication."""
    return f"Version {version}", (None if info is not None else DEVELOPMENT_LABEL)


def _font(family: str, px: int, weight=QFont.Weight.Normal) -> QFont:
    font = QFont(family)
    font.setPixelSize(px)
    font.setWeight(weight)
    return font


def splash_pixmap(dpr: float, info: BuildInfo | None) -> QPixmap:
    """Image fixe de l'écran (sans le message), dessinée au facteur de l'écran."""
    pixmap = QPixmap(round(WIDTH * dpr), round(HEIGHT * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(QColor(t.GROUND))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setPen(QPen(QColor(t.LINE), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(0.5, 0.5, WIDTH - 1, HEIGHT - 1))

    y = 44.0
    logo = QPixmap(str(resource("logos", "scenix16.png")))
    if not logo.isNull():
        scaled = logo.scaledToHeight(round(LOGO_HEIGHT * dpr), Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        w = scaled.width() / dpr
        p.drawPixmap(QRectF((WIDTH - w) / 2, y, w, LOGO_HEIGHT), scaled,
                     QRectF(0, 0, scaled.width(), scaled.height()))
    y += LOGO_HEIGHT + 18

    p.setPen(QColor(t.SILK))
    p.setFont(_font(LABEL_FAMILY, 24, QFont.Weight.DemiBold))
    p.drawText(QRectF(0, y, WIDTH, 30), Qt.AlignHCenter | Qt.AlignVCenter, "SceniX16")
    y += 34
    version, mention = version_lines(info)
    p.setPen(QColor(t.MUTED))
    p.setFont(_font(MONO_FAMILY, 12, QFont.Weight.Medium))
    p.drawText(QRectF(0, y, WIDTH, 18), Qt.AlignHCenter | Qt.AlignVCenter, version)
    if mention:
        y += 20
        p.setPen(QColor(t.DIM))
        p.setFont(_font(MONO_FAMILY, 11))
        p.drawText(QRectF(0, y, WIDTH, 18), Qt.AlignHCenter | Qt.AlignVCenter, mention)

    p.setPen(QPen(QColor(t.LINE_SOFT), 1))
    line_y = HEIGHT - MESSAGE_HEIGHT + 0.5
    p.drawLine(QPointF(24, line_y), QPointF(WIDTH - 24, line_y))
    p.end()
    return pixmap


class StartupSplash(QSplashScreen):
    def __init__(self, screen: QScreen | None = None, build_info: BuildInfo | None = None,
                 use_build_file: bool = True):
        screen = screen or QGuiApplication.primaryScreen()
        super().__init__(screen)                 # créé directement sur l'écran de lancement (B6)
        self.setScreen(screen)
        if build_info is None and use_build_file:
            build_info = load_build_info()
        self.build_info = build_info
        dpr = screen.devicePixelRatio() if screen is not None else 1.0   # facteur de CET écran
        self.setPixmap(splash_pixmap(dpr, build_info))
        self.setObjectName("StartupSplash")
        self.setAccessibleName(ACCESSIBLE_NAME)
        self.message = ""
        self._may_close = False
        if screen is not None:                   # centré dans la zone disponible de l'écran (B6)
            x, y, _w, _h = centered_geometry(rect_of(screen.availableGeometry()), (WIDTH, HEIGHT))
            self.move(x, y)
        self.set_step(Step.STARTING)

    # --- étapes -------------------------------------------------------------------------------
    def set_step(self, step: Step) -> None:
        """Affiche le message de l'étape réelle ; redessin immédiat (boucle d'événements bloquée)."""
        message = STEP_MESSAGES.get(step)
        if message is None or message == self.message:
            return
        self.message = message
        self.setAccessibleDescription(message)
        if self.isVisible():
            self.repaint()

    def drawContents(self, painter: QPainter) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setPen(QColor(t.TEXT))
        painter.setFont(_font(LABEL_FAMILY, 14, QFont.Weight.Medium))
        painter.drawText(QRectF(24, HEIGHT - MESSAGE_HEIGHT, WIDTH - 48, MESSAGE_HEIGHT),
                         Qt.AlignHCenter | Qt.AlignVCenter, self.message)

    # --- fermeture : programmée uniquement (P5) -------------------------------------------------
    def mousePressEvent(self, event):
        event.accept()                           # un clic ne ferme pas l'écran

    def closeEvent(self, event):
        if self._may_close:
            super().closeEvent(event)
        else:
            event.ignore()                       # Alt+F4, fermeture demandée par l'utilisateur

    def dismiss(self) -> None:
        """Fermeture programmée : boîte de démarrage, échec, sortie anticipée. Toujours possible."""
        self._may_close = True
        self.close()
        self.hide()

    def finish(self, window) -> None:
        """Fermeture dès que la fenêtre CONCERTS est affichée (aucun délai artificiel)."""
        self._may_close = True
        super().finish(window)
        self.hide()
