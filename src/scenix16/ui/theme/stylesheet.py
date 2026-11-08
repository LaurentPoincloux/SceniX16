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
    QMenuBar#AppMenuBar {{
        background: transparent;
        color: {t.TEXT};
        font-family: {_family(t.FONT_UI)};
        font-size: 13px;
        font-weight: 500;
        spacing: 2px;
    }}
    QMenuBar#AppMenuBar::item {{
        background: transparent;
        padding: 5px 10px;
        border-radius: 5px;
    }}
    QMenuBar#AppMenuBar::item:selected, QMenuBar#AppMenuBar::item:pressed {{
        background: {t.RAISED};
    }}
    QWidget#NavRail {{
        background: {t.PANEL};
        border-right: 1px solid {t.LINE_SOFT};
    }}
    QFrame#RailRule {{
        background: {t.LINE_SOFT};
        border: none;
    }}
    QLabel#RailGroupLabel {{
        color: {t.DIM};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1.4px;
        margin: 6px 4px 2px 4px;
    }}
    QPushButton#NewSetlistButton {{
        min-height: 36px;
        background: {t.BRAND};
        color: {t.INK};
        border: 1px solid {t.BRAND};
        border-radius: 5px;
        font-family: {_family(t.FONT_LABEL)};
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 1.4px;
    }}
    QPushButton#NewSetlistButton:disabled {{
        background: {t.BRAND_INACTIVE_BG};
        color: {t.BRAND};
        border: 1px solid {t.BRAND_INACTIVE_BORDER};
    }}
    QWidget#DashboardPage, QWidget#DashboardCanvas, QWidget#DashboardContent {{
        background: {t.GROUND};
    }}
    QScrollArea#DashboardScroll {{
        background: {t.GROUND};
        border: none;
    }}
    QScrollArea#DashboardScroll QScrollBar:vertical {{
        background: {t.GROUND};
        width: 10px;
        margin: 2px 2px 2px 0;
    }}
    QScrollArea#DashboardScroll QScrollBar::handle:vertical {{
        background: {t.LINE_STRONG};
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollArea#DashboardScroll QScrollBar::add-line:vertical,
    QScrollArea#DashboardScroll QScrollBar::sub-line:vertical,
    QScrollArea#DashboardScroll QScrollBar::add-page:vertical,
    QScrollArea#DashboardScroll QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
    }}
    QLabel#SectionTitle {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 1.5px;
    }}
    QWidget#SetlistsIndicator, QWidget#EmptyState {{
        background: {t.PANEL};
        border: 1px solid {t.LINE_SOFT};
        border-radius: 6px;
    }}
    QLabel#IndicatorText {{
        color: {t.MUTED};
        font-size: 13px;
    }}
    QLabel#EmptyTitle {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 16px;
        font-weight: 600;
        letter-spacing: 1.6px;
    }}
    QLabel#InactiveLink {{
        color: {t.DIM};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 12px;
        font-weight: 600;
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
    QDialog#AboutDialog, QDialog#LicensesDialog {{
        background: {t.RAISED};
        color: {t.TEXT};
        font-family: {_family(t.FONT_UI)};
    }}
    QLabel#AboutVersion {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
    }}
    QLabel#AboutCredit {{
        color: {t.TEXT};
        font-size: 13px;
    }}
    QPushButton[variant="link"] {{
        background: transparent;
        color: {t.BRAND};
        border: 1px solid transparent;
        padding: 0 4px;
        font-family: {_family(t.FONT_UI)};
        font-weight: 500;
    }}
    QPushButton[variant="link"]:hover {{
        text-decoration: underline;
    }}
    QListWidget#LicensesNav {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QFrame#LicensesReader {{
        background: {t.CELL};
        border: 1px solid {t.LINE};
        border-radius: 6px;
    }}
    QTextBrowser#LicensesText {{
        background: {t.CELL};
        color: {t.TEXT};
        border: none;
        selection-background-color: {t.LINE_STRONG};
    }}
    QLabel#LicensesHeaderName {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 16px;
        font-weight: 600;
    }}
    QLabel#LicensesHeaderMeta {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
    }}
    QDialog#LicensesDialog QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QDialog#LicensesDialog QScrollBar::handle:vertical {{
        background: {t.LINE_STRONG};
        border-radius: 3px;
        min-height: 32px;
    }}
    QDialog#LicensesDialog QScrollBar::add-line:vertical, QDialog#LicensesDialog QScrollBar::sub-line:vertical,
    QDialog#LicensesDialog QScrollBar::add-page:vertical, QDialog#LicensesDialog QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
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
    QPushButton#DialogCloseButton {{
        background: transparent;
        color: {t.TEXT};
        border: 1px solid {t.LINE_STRONG};
    }}
    QPushButton#DialogCloseButton:hover {{
        background: {t.LINE_SOFT};
    }}
    QPushButton#DialogCloseButton:focus {{
        border: 1px solid {t.LINE_STRONG};
    }}
    QPushButton#DialogCloseButton[kbfocus="true"]:focus {{
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
    QWidget#ConcertSheetPage, QWidget#SheetCanvas, QScrollArea#SheetScroll {{
        background: {t.GROUND};
        border: none;
    }}
    QScrollArea#SheetScroll QScrollBar:vertical {{
        background: {t.GROUND};
        width: 10px;
        margin: 2px 0 2px 2px;
    }}
    QScrollArea#SheetScroll QScrollBar::handle:vertical {{
        background: {t.LINE_STRONG};
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollArea#SheetScroll QScrollBar::add-line:vertical, QScrollArea#SheetScroll QScrollBar::sub-line:vertical,
    QScrollArea#SheetScroll QScrollBar::add-page:vertical, QScrollArea#SheetScroll QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
    }}
    QFrame#ConcertSheet {{
        background: {t.CELL};
        border: 1px solid {t.LINE_SOFT};
        border-radius: 6px;
    }}
    QFrame#SheetHead {{
        background: {t.PANEL};
        border: none;
        border-bottom: 1px solid {t.LINE};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QLabel#SheetHeading {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
    }}
    QLabel#SheetName {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 24px;
        font-weight: 600;
    }}
    QLabel#SheetMeta {{
        color: {t.MUTED};
        font-size: 13px;
    }}
    QFrame#SheetHeaderRow {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {t.LINE};
    }}
    QLabel#SheetHeaderCell {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.4px;
    }}
    QFrame#SheetRow {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {t.LINE_SOFT};
    }}
    QLabel#SheetTitle {{
        color: {t.TEXT};
        font-size: 13px;
    }}
    QLabel#SheetValue {{
        color: {t.TEXT};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
    }}
    QLabel#VirusStatusEmpty {{
        color: {t.DIM};
        font-family: {_family(t.FONT_MONO)};
        font-size: 11px;
    }}
    QLabel#VirusStatus, QLabel#VirusStatusOn {{
        font-family: {_family(t.FONT_MONO)};
        font-size: 10px;
        border-radius: 3px;
        padding: 1px 0;
    }}
    QLabel#VirusStatus {{
        color: {t.DIM};
        border: 1px solid {t.LINE};
    }}
    QLabel#VirusStatusOn {{
        color: {t.OK};
        background: {t.OK_BG};
        border: 1px solid {t.OK_BG};
    }}
    QFrame#SheetInfo {{
        background: transparent;
        border: none;
        border-top: 1px solid {t.LINE};
    }}
    QToolButton#SheetInfoToggle {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        color: {t.MUTED};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1.4px;
        padding: 4px 6px;
    }}
    QToolButton#SheetInfoToggle:hover {{
        background: {t.RAISED};
    }}
    QToolButton#SheetInfoToggle:focus {{
        border: 2px solid {t.BRAND};
    }}
    QLabel#SheetInfoLabel {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.6px;
    }}
    QLabel#SheetInfoValue {{
        color: {t.TEXT};
        font-size: 13px;
    }}
    QLabel#SheetInfoSummary {{
        color: {t.MUTED};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 13px;
    }}
    QLabel#SheetScheduleTime {{
        color: {t.SILK};
        font-family: {_family(t.FONT_MONO)};
        font-size: 13px;
    }}
    QFrame#SheetNotes {{
        background: {t.RAISED};
        border: 1px solid {t.LINE_SOFT};
        border-radius: 6px;
    }}
    QFrame#SheetContact {{
        background: {t.PANEL};
        border: 1px solid {t.LINE_SOFT};
        border-radius: 6px;
    }}
    QLabel#SheetContactName {{
        color: {t.SILK};
        font-family: {_family(t.FONT_LABEL)};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel#SheetContactRole {{
        color: {t.MUTED};
        font-size: 12px;
    }}
    QLabel#SheetContactDetail {{
        color: {t.TEXT};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
    }}
    QLabel#SheetCopied {{
        color: {t.OK};
        font-size: 12px;
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
    QStatusBar QLabel#StatusPart {{
        color: {t.DIM};
        font-family: {_family(t.FONT_MONO)};
        font-size: 12px;
        padding-left: 20px;
    }}
    QStatusBar QLabel#DiagnosticLabel {{
        color: {t.LINE_STRONG};
        font-family: {_family(t.FONT_MONO)};
        font-size: 11px;
        padding-right: 12px;
    }}
    QStatusBar::item {{
        border: none;
    }}
    """
