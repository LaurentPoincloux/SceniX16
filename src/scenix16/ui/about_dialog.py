"""Aide › À propos de SceniX16 (D59, Q10, Q14, Q18 — Design Book v0.43).

Boîte courte et sobre, en fond relevé : logo SceniX16, nom, version et fabrication,
trois lignes de crédits, lien « Licences et composants tiers… », bouton « Fermer »,
Échap pour fermer (D39). Aucun autre crédit, ni contact, ni site web ; aucune
connexion : tout est lu dans l'application.
Lancé depuis les sources : « Version de développement ». Exécutable fabriqué :
version, date de fabrication et identifiant court du commit ; si le code fabriqué
contenait des modifications non commitées, c'est indiqué, pour ne pas laisser
croire que l'identifiant suffit à désigner ce code.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from scenix16 import __version__
from scenix16.paths import resource
from scenix16.services.dashboard_service import day_month_year
from scenix16.ui.widgets.keyboard_focus_button import KeyboardFocusButton
from scenix16.ui.widgets.logo_label import LogoLabel
from scenix16.version import DEVELOPMENT_LABEL, BuildInfo, load_build_info

TITLE = "À propos de SceniX16"
LOGO_HEIGHT = 40
CREDITS = (
    "Conception et direction du projet : Laurent Poincloux.",
    "Développement logiciel : réalisé avec l'assistance de Claude Code (Anthropic), "
    "sous la direction de Laurent Poincloux.",
    "Conception, architecture et accompagnement : avec l'assistance de ChatGPT (OpenAI) pour la "
    "réflexion fonctionnelle, les choix d'architecture, la formalisation des spécifications et la "
    "revue des propositions de développement, sous la direction de Laurent Poincloux.",
)
LICENSES_LINK = "Licences et composants tiers…"
LOCAL_CHANGES = "modifications locales non commitées"


def version_lines(info: BuildInfo | None, version: str = __version__) -> tuple[str, str | None]:
    """(ligne de version, ligne de fabrication) ; sans fabrication : « Version de développement »."""
    if info is None:
        return DEVELOPMENT_LABEL, None
    build = f"Commit {info.commit}"
    if info.local_changes:
        build += f", avec {LOCAL_CHANGES}"
    return f"Version {version} · fabrication du {day_month_year(info.built_on)}", build


class AboutDialog(QDialog):
    def __init__(self, parent=None, build_info: BuildInfo | None = None, use_build_file: bool = True):
        super().__init__(parent)
        self.setObjectName("AboutDialog")
        self.setWindowTitle(TITLE)
        self.setModal(True)
        if build_info is None and use_build_file:
            build_info = load_build_info()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)

        self.logo = LogoLabel(resource("logos", "scenix16.png"), LOGO_HEIGHT)
        self.logo.setAccessibleName("SceniX16")
        layout.addWidget(self.logo)
        layout.addSpacing(4)
        self.name_label = QLabel("SceniX16", objectName="DialogTitle")
        layout.addWidget(self.name_label)

        version, build = version_lines(build_info)
        self.version_label = QLabel(version, objectName="AboutVersion")
        layout.addWidget(self.version_label)
        self.build_label = QLabel(build or "", objectName="AboutVersion")
        self.build_label.setVisible(build is not None)
        layout.addWidget(self.build_label)
        layout.addSpacing(6)

        self.credit_labels = []
        for text in CREDITS:
            label = QLabel(text, objectName="AboutCredit")
            label.setWordWrap(True)
            layout.addWidget(label)
            self.credit_labels.append(label)
        layout.addSpacing(6)

        self.licenses_button = QPushButton(LICENSES_LINK)
        self.licenses_button.setProperty("variant", "link")
        self.licenses_button.setCursor(Qt.PointingHandCursor)
        self.licenses_button.clicked.connect(self.show_licenses)
        row = QHBoxLayout()
        row.addWidget(self.licenses_button)
        row.addStretch(1)
        self.close_button = KeyboardFocusButton("Fermer")    # orange au focus clavier seulement (2.6d)
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self.setFixedWidth(500)

    def show_licenses(self) -> None:
        from scenix16.ui.licenses_dialog import LicensesDialog
        LicensesDialog(self).exec()
