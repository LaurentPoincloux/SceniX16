"""Feuille de style Qt construite à partir des jetons du Design Book."""

from scenix16.ui.theme import tokens as t


def _family(fonts: list[str]) -> str:
    return ", ".join(f'"{name}"' for name in fonts)


def application_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#Body {{
        background: {t.GROUND};
        color: {t.TEXT};
        font-family: {_family(t.FONT_UI)};
    }}
    QWidget#TopBar {{
        background: {t.GROUND};
        border-bottom: 1px solid {t.LINE_SOFT};
    }}
    QLabel#Placeholder {{
        color: {t.DIM};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 12px;
        letter-spacing: 1px;
    }}
    QStatusBar {{
        background: {t.GROUND};
        color: {t.DIM};
        border-top: 1px solid {t.LINE_SOFT};
        font-family: {_family(t.FONT_MONO)};
        font-size: 11px;
    }}
    QStatusBar QLabel {{
        color: {t.MUTED};
        padding-left: 12px;
    }}
    """
