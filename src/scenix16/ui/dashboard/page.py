"""Page MAIN : zone centrale du dashboard (section 07).

Incrément 2.3 : structure seulement. La colonne de contenu, centrée et
plafonnée à 1600 px (section 08), accueillera le séquenceur et les
emplacements à l'incrément 2.4.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from scenix16.ui.theme import tokens as t

CONTENT_MARGINS = (28, 24, 28, 24)   # marges de la zone centrale (maquette section 07)


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(*CONTENT_MARGINS)
        outer.setSpacing(0)
        self.content = QWidget(objectName="DashboardContent")
        self.content.setMaximumWidth(t.CONTENT_MAX_WIDTH)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(22)
        self.content_layout.addStretch(1)
        outer.addWidget(self.content)
        self._outer = outer

    def resizeEvent(self, event):
        # la colonne occupe toute la largeur jusqu'à 1600 px, puis reste centrée
        left, top, right, bottom = CONTENT_MARGINS
        extra = max(0, self.width() - left - right - t.CONTENT_MAX_WIDTH)
        self._outer.setContentsMargins(left + extra // 2, top, right + extra - extra // 2, bottom)
        super().resizeEvent(event)
