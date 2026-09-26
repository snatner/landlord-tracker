"""Visual theme.

A single source of truth for colours, spacing and the Qt stylesheet so the
whole app looks deliberate instead of default-Qt. Light theme is the default;
a dark theme is included because landlords use the app at night too.
"""

from __future__ import annotations

from dataclasses import dataclass

LIGHT = {
    "bg": "#F4F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFD",
    "border": "#E1E8F2",
    "text": "#1B2431",
    "muted": "#6B7A90",
    "primary": "#20456F",
    "primary_hover": "#2A5A8F",
    "primary_text": "#FFFFFF",
    "accent": "#3E8ED0",
    "success": "#2E9E63",
    "warning": "#D89A22",
    "danger": "#D0534B",
    "sidebar": "#152C47",
    "sidebar_text": "#D7E2F0",
    "sidebar_active": "#1E4C7A",
    "grid": "#E8EDF5",
    "shadow": "rgba(20, 40, 70, 0.08)",
}

DARK = {
    "bg": "#12161C",
    "surface": "#1A2029",
    "surface_alt": "#212936",
    "border": "#2B3441",
    "text": "#E7EDF5",
    "muted": "#93A2B5",
    "primary": "#3E8ED0",
    "primary_hover": "#4E9EE0",
    "primary_text": "#0E1218",
    "accent": "#5AA9E6",
    "success": "#48B87C",
    "warning": "#E0AE43",
    "danger": "#E07068",
    "sidebar": "#0D1117",
    "sidebar_text": "#B9C6D6",
    "sidebar_active": "#1E4C7A",
    "grid": "#28313D",
    "shadow": "rgba(0, 0, 0, 0.35)",
}

# Categorical palette used by every chart, so colours stay consistent app-wide.
CHART_COLORS = [
    "#3E8ED0", "#2E9E63", "#D89A22", "#8A63D2", "#D0534B",
    "#2FA8A0", "#C77D3A", "#5A7FBF", "#A8547E", "#7A8B99",
]

STATUS_COLORS = {
    "paid": "#2E9E63",
    "partial": "#D89A22",
    "unpaid": "#8C99A8",
    "late": "#D0534B",
}

STATUS_COLORS_DARK = {
    "paid": "#48B87C",
    "partial": "#E0AE43",
    "unpaid": "#7C8797",
    "late": "#E07068",
}


@dataclass
class Theme:
    name: str = "light"
    colors: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.colors is None:
            self.colors = dict(LIGHT if self.name == "light" else DARK)

    def __getitem__(self, key: str) -> str:
        return self.colors[key]

    def status_color(self, status: str) -> str:
        table = STATUS_COLORS if self.name == "light" else STATUS_COLORS_DARK
        return table.get(status, self.colors["muted"])

    def chart_color(self, index: int) -> str:
        return CHART_COLORS[index % len(CHART_COLORS)]


def build_stylesheet(theme: Theme) -> str:
    c = theme.colors
    return f"""
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: "Inter", "Ubuntu", "Noto Sans", "DejaVu Sans", sans-serif;
        font-size: 14px;
    }}
    QWidget#Root, QMainWindow {{
        background: {c['bg']};
    }}
    /* The global QWidget rule above paints a background behind *every* widget,
       including labels. Inside the dark sidebar that produced a pale rectangle
       sitting on top of the brand text. Labels must stay transparent and inherit
       the surface they are placed on. Id-scoped rules (e.g. QLabel#AlertChip)
       are more specific and still win over this. */
    QLabel, QCheckBox, QRadioButton, QGroupBox {{
        background: transparent;
    }}

    /* ---------- sidebar ---------- */
    QFrame#Sidebar {{
        background: {c['sidebar']};
        border: none;
    }}
    QLabel#BrandTitle {{
        color: #FFFFFF;
        font-size: 15px;
        font-weight: 700;
        padding: 0;
    }}
    QLabel#BrandSubtitle {{
        color: {c['sidebar_text']};
        font-size: 10px;
    }}
    QLabel#BrandMark {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 700;
    }}
    QPushButton#NavButton {{
        background: transparent;
        color: {c['sidebar_text']};
        border: none;
        border-radius: 8px;
        padding: 10px 14px;
        text-align: left;
        font-size: 14px;
    }}
    QPushButton#NavButton:hover {{
        background: {c['sidebar_active']};
        color: #FFFFFF;
    }}
    QPushButton#NavButton:checked {{
        background: {c['sidebar_active']};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QLabel#PrivacyBadge {{
        color: #9FE0B8;
        font-size: 11px;
        padding: 8px 10px 6px 10px;
    }}
    QLabel#SidebarSectionTitle {{
        color: #FFFFFF;
        font-size: 11px;
        font-weight: 700;
        padding: 0 2px 2px 2px;
    }}
    QPushButton#DonateButton {{
        background: rgba(255, 255, 255, 0.08);
        color: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 8px;
        padding: 7px 8px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton#DonateButton:hover {{
        background: {c['sidebar_active']};
        border-color: #6CAAE0;
    }}

    /* ---------- cards ---------- */
    /* id-only selectors: PySide6 subclasses register their own metaobject
       class name, so "QFrame#KpiCard" would not match a KpiCard instance. */
    #Card {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    #KpiCard {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    QFrame#Card {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    QLabel#KpiLabel {{
        color: {c['muted']};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#KpiValue {{
        color: {c['text']};
        font-size: 23px;
        font-weight: 700;
    }}
    QLabel#KpiHint {{
        color: {c['muted']};
        font-size: 11px;
    }}
    QLabel#SectionTitle {{
        font-size: 16px;
        font-weight: 700;
        color: {c['text']};
    }}
    QLabel#PageTitle {{
        font-size: 24px;
        font-weight: 700;
        color: {c['text']};
    }}
    QLabel#PageSubtitle {{
        color: {c['muted']};
        font-size: 13px;
    }}
    QLabel#Muted {{
        color: {c['muted']};
    }}
    QLabel#ChartTitle {{
        font-size: 13px;
        font-weight: 600;
        color: {c['text']};
    }}
    QLabel#AlertChip {{
        background: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 11px;
        color: {c['text']};
        font-size: 12px;
    }}
    QLabel#AlertChipOk {{
        background: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 11px;
        color: {c['success']};
        font-size: 12px;
    }}
    QLabel#Positive {{
        color: {c['success']};
        font-weight: 600;
    }}
    QLabel#Negative {{
        color: {c['danger']};
        font-weight: 600;
    }}

    /* ---------- buttons ---------- */
    QPushButton {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 13px;
    }}
    QPushButton:hover {{
        border-color: {c['accent']};
    }}
    QPushButton:disabled {{
        color: {c['muted']};
        background: {c['surface_alt']};
    }}
    QPushButton#Primary {{
        background: {c['primary']};
        color: {c['primary_text']};
        border: 1px solid {c['primary']};
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{
        background: {c['primary_hover']};
        border-color: {c['primary_hover']};
    }}
    QPushButton#Danger {{
        color: {c['danger']};
    }}
    QPushButton#LinkButton {{
        background: transparent;
        border: none;
        color: {c['accent']};
        text-decoration: underline;
        padding: 2px;
    }}

    /* ---------- inputs ---------- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {c['accent']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QDateEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border-color: {c['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent']};
        selection-color: #FFFFFF;
        outline: none;
    }}
    QCheckBox {{
        spacing: 8px;
    }}

    /* ---------- tables ---------- */
    QTableView, QTableWidget {{
        background: {c['surface']};
        alternate-background-color: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        gridline-color: {c['grid']};
        selection-background-color: {c['sidebar_active']};
        selection-color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: {c['surface_alt']};
        color: {c['muted']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 9px 10px;
        font-weight: 600;
        font-size: 12px;
    }}
    QTableCornerButton::section {{
        background: {c['surface_alt']};
        border: none;
    }}

    /* ---------- tabs / misc ---------- */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: 10px;
        background: {c['surface']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {c['muted']};
        padding: 8px 16px;
        border: none;
        font-size: 13px;
    }}
    QTabBar::tab:selected {{
        color: {c['accent']};
        font-weight: 600;
        border-bottom: 2px solid {c['accent']};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['muted']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: 5px;
        min-width: 30px;
    }}
    QProgressBar {{
        border: 1px solid {c['border']};
        border-radius: 8px;
        background: {c['surface_alt']};
        height: 10px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {c['accent']};
        border-radius: 7px;
    }}
    QToolTip {{
        background: {c['text']};
        color: {c['surface']};
        border: none;
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QStatusBar {{
        background: {c['surface']};
        color: {c['muted']};
        border-top: 1px solid {c['border']};
    }}
    QDialog {{
        background: {c['bg']};
    }}
    QMenu {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 22px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {c['sidebar_active']};
        color: #FFFFFF;
    }}
    """
