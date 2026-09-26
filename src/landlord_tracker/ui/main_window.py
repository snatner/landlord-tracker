"""Main application window: sidebar navigation + stacked pages."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..context import (
    APP_VERSION,
    BUYMEACOFFEE_URL,
    CRYPTO_DONATION_TEXT,
    KOFI_URL,
    AppContext,
)
from ..i18n import tr
from ..services import demo as demo_service
from ..services.formatting import format_path
from .dashboard_view import DashboardView
from .documents_view import DocumentsView
from .expenses_view import ExpensesView
from .feedback_view import FeedbackView
from .leases_view import LeasesView
from .properties_view import PropertiesView
from .rent_view import RentView
from .recurring_expenses_view import RecurringExpensesView
from .renovations_view import RenovationsView
from .settings_view import SettingsView
from .tenants_view import TenantsView


class Sidebar(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        # Use the real app icon rather than a text glyph: box-drawing characters
        # are missing from many font stacks and render as "tofu" rectangles.
        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setFixedSize(26, 26)
        icon_path = Path(__file__).resolve().parents[1] / "resources" / "app_icon.svg"
        if icon_path.exists():
            mark.setPixmap(QIcon(str(icon_path)).pixmap(26, 26))
        brand_row.addWidget(mark)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.brand_title = QLabel(tr("app_name"))
        self.brand_title.setObjectName("BrandTitle")
        self.brand_subtitle = QLabel(tr("privacy_short"))
        self.brand_subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(self.brand_title)
        brand_text.addWidget(self.brand_subtitle)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        layout.addSpacing(16)

        self.buttons: list[tuple[str, QPushButton]] = []
        self.nav_insert_index = layout.count()
        layout.addStretch(1)

        self.support_title = QLabel(tr("support_title"))
        self.support_title.setObjectName("SidebarSectionTitle")
        layout.addWidget(self.support_title)

        support_row_1 = QHBoxLayout()
        support_row_1.setSpacing(6)
        self.kofi_button = QPushButton(tr("support_kofi"))
        self.kofi_button.setObjectName("DonateButton")
        self.kofi_button.setCursor(Qt.PointingHandCursor)
        self.kofi_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(KOFI_URL)))
        self.bmc_button = QPushButton(tr("support_bmc"))
        self.bmc_button.setObjectName("DonateButton")
        self.bmc_button.setCursor(Qt.PointingHandCursor)
        self.bmc_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BUYMEACOFFEE_URL)))
        support_row_1.addWidget(self.kofi_button)
        support_row_1.addWidget(self.bmc_button)
        layout.addLayout(support_row_1)

        self.crypto_button = QPushButton(tr("support_crypto"))
        self.crypto_button.setObjectName("DonateButton")
        self.crypto_button.setCursor(Qt.PointingHandCursor)
        self.crypto_button.clicked.connect(self.copy_crypto_text)
        layout.addWidget(self.crypto_button)

        self.privacy_badge = QLabel("🔒  " + tr("privacy_line"))
        self.privacy_badge.setObjectName("PrivacyBadge")
        self.privacy_badge.setWordWrap(True)
        layout.addWidget(self.privacy_badge)

        version = QLabel(tr("app_version_label", version=APP_VERSION))
        version.setObjectName("BrandSubtitle")
        layout.addWidget(version)

    def add_nav(self, key: str, label: str, on_click) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(on_click)
        self.layout().insertWidget(self.nav_insert_index + len(self.buttons), button)
        self.buttons.append((key, button))
        return button

    def copy_crypto_text(self) -> None:
        QApplication.clipboard().setText(CRYPTO_DONATION_TEXT)
        self.crypto_button.setText("✓ " + tr("support_crypto"))


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{tr('app_name')} — {tr('privacy_short')}")
        self.resize(1440, 940)
        self.setMinimumSize(1080, 720)
        self.setStyleSheet(ctx.stylesheet())

        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.dashboard = DashboardView(ctx)
        self.properties = PropertiesView(ctx)
        self.tenants = TenantsView(ctx)
        self.leases = LeasesView(ctx)
        self.rent = RentView(ctx)
        self.expenses = ExpensesView(ctx)
        self.recurring = RecurringExpensesView(ctx)
        self.renovations = RenovationsView(ctx)
        self.documents = DocumentsView(ctx)
        self.feedback = FeedbackView(ctx)
        self.settings = SettingsView(ctx, on_language_changed=self.on_language_changed)

        self.pages = {
            "dashboard": self.dashboard,
            "properties": self.properties,
            "tenants": self.tenants,
            "leases": self.leases,
            "rent": self.rent,
            "expenses": self.expenses,
            "recurring": self.recurring,
            "renovations": self.renovations,
            "documents": self.documents,
            "feedback": self.feedback,
            "settings": self.settings,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        nav_order = [
            ("dashboard", "nav_dashboard"),
            ("properties", "nav_properties"),
            ("tenants", "nav_tenants"),
            ("leases", "nav_leases"),
            ("rent", "nav_rent"),
            ("expenses", "nav_expenses"),
            ("recurring", "nav_recurring"),
            ("renovations", "nav_renovations"),
            ("documents", "nav_documents"),
            ("feedback", "nav_feedback"),
            ("settings", "nav_settings"),
        ]
        for index, (key, label_key) in enumerate(nav_order):
            self.sidebar.add_nav(key, tr(label_key), self._make_switch(index))
        self._nav_order = nav_order

        # any CRUD change refreshes the dashboard numbers
        for key, page in self.pages.items():
            changed = getattr(page, "changed", None)
            if changed is not None:
                changed.connect(self.dashboard.refresh)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._update_status()

        self.switch_to("dashboard")
        self._maybe_offer_demo()

    # ------------------------------------------------------------------
    def _make_switch(self, index: int):
        return lambda: self.switch_to_index(index)

    def switch_to(self, key: str) -> None:
        index = list(self.pages).index(key)
        self.switch_to_index(index)

    def switch_to_index(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for position, (key, button) in enumerate(self.sidebar.buttons):
            button.setChecked(position == index)
        page = self.stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
        self._update_status()

    def _update_status(self) -> None:
        db = self.ctx.db
        self.status.showMessage(
            f"{tr('properties')}: {db.count('properties')} · "
            f"{tr('tenants')}: {db.count('tenants')} · "
            f"{tr('leases')}: {db.count('leases')} · "
            f"{tr('data_folder')}: {format_path(db.data_dir)}"
        )

    def _maybe_offer_demo(self) -> None:
        if self.ctx.db.is_empty() and not demo_service.is_demo(self.ctx.db):
            self.load_demo()

    def load_demo(self) -> None:
        demo_service.load_demo(self.ctx.db)
        self.refresh_all()

    def refresh_all(self) -> None:
        for page in self.pages.values():
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()
        self._update_status()

    # ------------------------------------------------------------------
    def on_language_changed(self) -> None:
        """Re-apply theme + translations after a settings change."""
        self.setStyleSheet(self.ctx.stylesheet())
        self.retranslate()
        self.refresh_all()

    def retranslate(self) -> None:
        self.setWindowTitle(f"{tr('app_name')} — {tr('privacy_short')}")
        self.sidebar.brand_title.setText(tr("app_name"))
        self.sidebar.brand_subtitle.setText(tr("privacy_short"))
        self.sidebar.support_title.setText(tr("support_title"))
        self.sidebar.kofi_button.setText(tr("support_kofi"))
        self.sidebar.bmc_button.setText(tr("support_bmc"))
        self.sidebar.crypto_button.setText(tr("support_crypto"))
        self.sidebar.privacy_badge.setText("🔒  " + tr("privacy_line"))
        for (key, label_key), (_, button) in zip(self._nav_order, self.sidebar.buttons):
            button.setText(tr(label_key))
        for page in self.pages.values():
            method = getattr(page, "retranslate", None)
            if callable(method):
                method()
        self._update_status()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.ctx.close()
        super().closeEvent(event)
