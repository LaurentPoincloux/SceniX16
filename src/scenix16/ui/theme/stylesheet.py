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
    QDialog#MessageDialog {{
        background: {t.RAISED};
        color: {t.TEXT};
        font-family: {_family(t.FONT_UI)};
    }}
    QLabel#DialogTitle {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 17px;
        font-weight: 600;
    }}
    QLabel#DialogText {{
        color: {t.MUTED};
        font-size: 13px;
    }}
    QPushButton {{
        min-height: 34px;
        padding: 0 16px;
        border-radius: 5px;
        font-family: {_family(t.FONT_LABEL)};
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton[variant="primary"] {{
        background: {t.BRAND};
        color: {t.INK};
        border: 1px solid {t.BRAND};
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {t.CELL};
        color: {t.DIM};
        border: 1px solid {t.LINE};
    }}
    QPushButton[variant="secondary"] {{
        background: transparent;
        color: {t.TEXT};
        border: 1px solid {t.LINE_STRONG};
    }}
    QPushButton:focus {{
        outline: none;
        border: 2px solid {t.BRAND};
    }}
    QToolButton#GearButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 5px;
    }}
    QToolButton#GearButton:hover {{
        background: {t.RAISED};
    }}
    QToolButton#GearButton[active="true"] {{
        background: {t.RAISED};
        border: 1px solid {t.LINE_STRONG};
    }}
    QToolButton#GearButton:focus {{
        border: 2px solid {t.BRAND};
    }}
    QWidget#SettingsPage {{
        background: {t.GROUND};
    }}
    QLabel#PageTitle {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 22px;
        font-weight: 600;
        letter-spacing: 2px;
    }}
    QWidget#SettingsSection {{
        border-top: 1px solid {t.LINE_SOFT};
    }}
    QLabel#SectionLabel {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 2px;
    }}
    QLabel#HintLabel {{
        color: {t.DIM};
        font-size: 12px;
    }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        color: {t.TEXT};
        border: 1px solid transparent;
        padding: 0 8px;
        text-align: left;
    }}
    QPushButton[variant="ghost"]:hover {{
        background: {t.RAISED};
    }}
    QPushButton[variant="ghost"]:disabled {{
        color: {t.DIM};
        background: transparent;
    }}
    QPushButton[variant="back"] {{
        background: transparent;
        color: {t.TEXT};
        border: 1px solid {t.LINE_STRONG};
        padding: 0 10px;
    }}
    QPushButton[variant="back"]:hover {{
        background: {t.RAISED};
    }}
    QStatusBar QLabel {{
        color: {t.MUTED};
        padding-left: 12px;
    }}
    """
