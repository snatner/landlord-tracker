"""UI smoke tests.

Run headless via Qt's ``offscreen`` platform plugin, so the whole window,
every page and every chart are actually constructed and painted. This catches
layout crashes that unit tests on pure functions would miss.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from landlord_tracker.context import AppContext  # noqa: E402
from landlord_tracker.db import Database  # noqa: E402
from landlord_tracker.i18n import set_language  # noqa: E402
from landlord_tracker.services.demo import clear_demo, load_demo  # noqa: E402
from landlord_tracker.ui.main_window import MainWindow  # noqa: E402

PAGE_KEYS = ["dashboard", "properties", "tenants", "leases", "rent",
             "expenses", "recurring", "renovations", "documents", "feedback",
             "settings"]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp, tmp_path: Path):
    ctx = AppContext(data_dir=tmp_path)
    load_demo(ctx.db)
    win = MainWindow(ctx)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_window_constructs_with_all_pages(window):
    assert len(window.pages) == len(PAGE_KEYS)
    assert window.stack.count() == len(PAGE_KEYS)
    assert window.styleSheet(), "Main window must apply the theme stylesheet"


def test_sidebar_has_compact_donation_buttons(window):
    assert window.sidebar.support_title.text() == "Support"
    assert window.sidebar.kofi_button.text() == "Ko-fi"
    assert window.sidebar.bmc_button.text() == "Buy Me a Coffee"
    assert window.sidebar.crypto_button.text() == "Crypto"
    assert window.sidebar.kofi_button.objectName() == "DonateButton"
    assert window.sidebar.bmc_button.objectName() == "DonateButton"
    assert window.sidebar.crypto_button.objectName() == "DonateButton"


def test_sidebar_crypto_button_copies_local_text(window):
    window.sidebar.copy_crypto_text()
    copied = QApplication.clipboard().text()
    assert "USDC on Base: 0x5e22326c91Ad8bf751c4c4CAdE26d3eb5F947898" in copied
    assert "Litecoin: ltc1qmpwgk4uqxgteypf644r43c6estk7wx4n5hvacx" in copied
    assert "Bitcoin: bc1qwz8k0tss6649fpgjhhgc29tjsaxzzq0sqfkw0y" in copied
    assert "not added yet" not in copied
    assert "generate with official" not in copied
    assert window.sidebar.crypto_button.text().startswith("✓")


def test_every_page_opens_and_repaints(window, qapp):
    for key in PAGE_KEYS:
        window.switch_to(key)
        qapp.processEvents()
        assert window.stack.currentWidget() is window.pages[key]


def test_dashboard_populates_kpis_and_charts(window, qapp):
    window.switch_to("dashboard")
    qapp.processEvents()
    data = window.dashboard._data
    assert data is not None
    assert data.kpi("properties") == 3
    tile = window.dashboard._kpi_cards["portfolio_value"]
    assert tile.value.text() not in ("", "—")


def test_charts_paint_without_error(window, qapp):
    window.switch_to("dashboard")
    qapp.processEvents()
    for chart in (window.dashboard.cashflow_chart, window.dashboard.portfolio_chart,
                  window.dashboard.rent_status_chart, window.dashboard.purchase_chart,
                  window.dashboard.expense_chart, window.dashboard.ranking_chart):
        pixmap = chart.grab()
        assert pixmap.width() > 0 and pixmap.height() > 0


def test_every_crud_view_lists_demo_rows(window, qapp):
    for key in ("properties", "tenants", "leases", "rent", "expenses",
                "renovations", "documents"):
        window.switch_to(key)
        qapp.processEvents()
        page = window.pages[key]
        assert page.table.rowCount() > 0, f"{key} table should not be empty"


def test_rent_generate_month_creates_rows(window, qapp):
    window.switch_to("rent")
    qapp.processEvents()
    page = window.rent
    period = page._period_filter
    window.ctx.db.execute("DELETE FROM rent_payments WHERE period = ?", (period,))
    page.refresh()
    created = page.create_rent_for_period(period)
    assert created == 2  # two active leases
    assert page.create_rent_for_period(period) == 0, "must not duplicate rows"
    page.refresh()
    assert page.table.rowCount() >= 2


def test_language_switch_retranslates_live_ui(window, qapp):
    window.switch_to("dashboard")
    qapp.processEvents()
    set_language("pt")
    window.on_language_changed()
    qapp.processEvents()
    assert window.dashboard.title.text() == "Painel"
    assert window.sidebar.buttons[0][1].text() == "Painel"
    set_language("en")
    window.on_language_changed()
    qapp.processEvents()
    assert window.dashboard.title.text() == "Dashboard"


def test_theme_switch_reapplies_stylesheet(window, qapp):
    window.ctx.set_theme("dark")
    window.on_language_changed()
    qapp.processEvents()
    assert window.ctx.theme.name == "dark"
    window.ctx.set_theme("light")
    window.on_language_changed()
    qapp.processEvents()
    assert window.ctx.theme.name == "light"


def test_search_filter_hides_non_matching_rows(window, qapp):
    window.switch_to("properties")
    qapp.processEvents()
    page = window.properties
    page.search.setText("Afonso")
    qapp.processEvents()
    visible = [row for row in range(page.table.rowCount())
               if not page.table.isRowHidden(row)]
    assert len(visible) == 1


def test_feedback_compose_builds_local_text_only(window):
    window.switch_to("feedback")
    page = window.feedback
    page.message.setPlainText("Please add partial rent tracking.")
    subject, body = page.compose()
    assert "Feature request" in subject
    assert "partial rent tracking" in body
    assert "Landlord Tracker" in body


def test_export_from_settings_produces_workbook(window, tmp_path: Path):
    from landlord_tracker.services.exports import export_workbook

    target = tmp_path / "ui-export.xlsx"
    export_workbook(window.ctx.db, target, window.ctx.language)
    assert target.exists() and target.stat().st_size > 5000


def test_demo_can_be_cleared(window, qapp):
    clear_demo(window.ctx.db)
    window.refresh_all()
    qapp.processEvents()
    assert window.ctx.db.count("properties") == 0
    window.switch_to("dashboard")
    qapp.processEvents()
    assert window.dashboard.empty_state.isVisible() is True


def test_settings_offers_removing_sample_data(qapp, tmp_path: Path, monkeypatch):
    """The seeded example data must be removable from the UI.

    Regression: the app auto-seeds example data on first run (so the dashboard is
    not empty) but there was no way to delete it again, which would leave a real
    user mixing fake tenants into their own records.
    """
    from PySide6.QtWidgets import QMessageBox

    from landlord_tracker.i18n import tr
    from landlord_tracker.services.demo import is_demo

    ctx = AppContext(data_dir=tmp_path / "sample-ui")
    load_demo(ctx.db)
    assert is_demo(ctx.db) is True

    win = MainWindow(ctx)
    settings = win.pages["settings"]
    assert settings.sample_state.text() == tr("sample_loaded")
    assert settings.remove_sample_button.isEnabled() is True

    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: QMessageBox.Ok))
    settings._remove_sample()

    assert is_demo(ctx.db) is False
    assert ctx.db.is_empty() is True
    assert settings.sample_state.text() == tr("sample_none")
    assert settings.remove_sample_button.isEnabled() is False
    win.close()


def test_first_run_auto_seeds_sample_and_allows_removal(qapp, tmp_path: Path):
    """A brand new install seeds examples, and the removal button is live."""
    from landlord_tracker.i18n import tr
    from landlord_tracker.services.demo import is_demo

    ctx = AppContext(data_dir=tmp_path / "first-run-ui")
    win = MainWindow(ctx)
    settings = win.pages["settings"]
    assert is_demo(ctx.db) is True
    assert settings.sample_state.text() == tr("sample_loaded")
    assert settings.remove_sample_button.isEnabled() is True
    win.close()


def test_settings_no_sample_state_when_user_has_own_data(qapp, tmp_path: Path):
    """Once the user has their own records, nothing is seeded and the button is off."""
    from landlord_tracker.i18n import tr
    from landlord_tracker.models import Property

    ctx = AppContext(data_dir=tmp_path / "own-data-ui")
    ctx.db.add_property(Property(name="My real flat", purchase_price=120000.0))
    win = MainWindow(ctx)
    settings = win.pages["settings"]
    assert settings.sample_state.text() == tr("sample_none")
    assert settings.remove_sample_button.isEnabled() is False
    win.close()
