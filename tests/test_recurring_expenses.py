"""Recurring expense templates: due maths, idempotent generation, migration.

The pure-function tests here are the contract for "is this cost due in this
month" — the one rule that decides whether the ledger gets a row, so it is
tested directly rather than through the UI.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from landlord_tracker.context import AppContext  # noqa: E402
from landlord_tracker.db import Database  # noqa: E402
from landlord_tracker.i18n import set_language  # noqa: E402
from landlord_tracker.models import Expense, Property, RecurringExpense  # noqa: E402
from landlord_tracker.services import calculations as calc  # noqa: E402
from landlord_tracker.ui.main_window import MainWindow  # noqa: E402


# --------------------------------------------------------------------------
# pure due maths
# --------------------------------------------------------------------------
def test_monthly_template_fires_every_month_from_start():
    template = {"frequency": "monthly", "start_month": "2026-09", "is_active": 1}
    assert calc.recurring_due(template, "2026-08") is False
    assert calc.recurring_due(template, "2026-09") is True
    assert calc.recurring_due(template, "2026-10") is True
    assert calc.recurring_due(template, "2027-03") is True


def test_monthly_template_without_start_month_fires_immediately():
    """A plain monthly condo fee must not require a start month to work."""
    template = {"frequency": "monthly", "start_month": "", "is_active": 1}
    assert calc.recurring_due(template, "2026-09") is True


def test_quarterly_fires_only_on_multiples_of_three():
    template = {"frequency": "quarterly", "start_month": "2026-01", "is_active": 1}
    due = [p for p in calc.month_sequence("2026-01", "2026-12")
           if calc.recurring_due(template, p)]
    assert due == ["2026-01", "2026-04", "2026-07", "2026-10"]


def test_annual_fires_once_a_year_on_the_start_month():
    template = {"frequency": "annual", "start_month": "2026-04", "is_active": 1}
    due = [p for p in calc.month_sequence("2026-01", "2028-12")
           if calc.recurring_due(template, p)]
    assert due == ["2026-04", "2027-04", "2028-04"]


def test_semiannual_fires_twice_a_year():
    template = {"frequency": "semiannual", "start_month": "2026-02", "is_active": 1}
    due = [p for p in calc.month_sequence("2026-01", "2026-12")
           if calc.recurring_due(template, p)]
    assert due == ["2026-02", "2026-08"]


def test_end_month_stops_the_template():
    template = {"frequency": "monthly", "start_month": "2026-01",
                "end_month": "2026-03", "is_active": 1}
    due = [p for p in calc.month_sequence("2026-01", "2026-06")
           if calc.recurring_due(template, p)]
    assert due == ["2026-01", "2026-02", "2026-03"]


def test_inactive_template_is_never_due():
    assert calc.recurring_due(
        {"frequency": "monthly", "start_month": "2026-01", "is_active": 0},
        "2026-05") is False
    # SQLite/bool-as-text variants must be treated as inactive too.
    assert calc.recurring_due(
        {"frequency": "monthly", "start_month": "2026-01", "is_active": "0"},
        "2026-05") is False
    assert calc.recurring_due(
        {"frequency": "monthly", "start_month": "2026-01", "is_active": "False"},
        "2026-05") is False


def test_unknown_frequency_falls_back_to_monthly():
    assert calc.recurrence_step("fortnightly") == 1
    assert calc.recurrence_step("") == 1
    assert calc.recurrence_step("MONTHLY") == 1


def test_bad_period_is_not_due():
    template = {"frequency": "monthly", "start_month": "2026-01", "is_active": 1}
    assert calc.recurring_due(template, "") is False
    assert calc.recurring_due(template, "not-a-month") is False


def test_due_date_clamps_to_month_length():
    template = {"day_of_month": 31}
    assert calc.recurring_due_date(template, "2026-01") == "2026-01-31"
    # February never has a 31st; clamp instead of rolling into March.
    assert calc.recurring_due_date(template, "2026-02") == "2026-02-28"
    assert calc.recurring_due_date(template, "2028-02") == "2028-02-29"
    assert calc.recurring_due_date({"day_of_month": 0}, "2026-05") == "2026-05-01"
    assert calc.recurring_due_date({"day_of_month": 40}, "2026-05") == "2026-05-31"


def test_monthly_equivalent_normalises_frequency():
    assert calc.recurring_monthly_equivalent(35, "monthly") == 35
    assert calc.recurring_monthly_equivalent(120, "quarterly") == 40
    assert calc.recurring_monthly_equivalent(240, "semiannual") == 40
    assert calc.recurring_monthly_equivalent(237.16, "annual") == pytest.approx(19.7633, rel=1e-4)


def test_monthly_equivalent_returns_none_without_an_amount():
    """Never invent a zero: callers render '—' for unknown amounts."""
    assert calc.recurring_monthly_equivalent(None, "monthly") is None
    assert calc.recurring_monthly_equivalent("", "monthly") is None


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
@pytest.fixture()
def db(tmp_path: Path):
    database = Database(data_dir=tmp_path)
    database.add_property(Property(name="P1 — Test flat"))
    yield database
    database.close()


def _prop_id(db) -> int:
    return db.properties()[0]["id"]


def _template(db, **overrides) -> RecurringExpense:
    data = dict(
        property_id=_prop_id(db),
        category="condo",
        amount=35.0,
        description="Condo contribution",
        frequency="monthly",
        day_of_month=5,
        start_month="2026-01",
    )
    data.update(overrides)
    return RecurringExpense(**data)


def test_add_and_list_templates(db):
    db.add_recurring_expense(_template(db))
    rows = db.recurring_expenses()
    assert len(rows) == 1
    assert rows[0]["amount"] == 35.0
    assert rows[0]["property_name"] == "P1 — Test flat"
    assert rows[0]["frequency"] == "monthly"


def test_update_and_delete_template(db):
    template_id = db.add_recurring_expense(_template(db))
    db.update_recurring_expense(template_id, _template(db, amount=42.5, is_active=0))
    row = db.recurring_expense(template_id)
    assert row["amount"] == 42.5
    assert row["is_active"] == 0
    assert db.recurring_expenses(active_only=True) == []
    db.delete_recurring_expense(template_id)
    assert db.recurring_expenses() == []


def test_generated_expense_carries_template_provenance(db):
    template_id = db.add_recurring_expense(_template(db))
    db.add_expense(Expense(
        property_id=_prop_id(db), date="2026-01-05", category="condo",
        amount=35.0, recurring_id=template_id, period="2026-01",
    ))
    row = db.expenses()[0]
    assert row["recurring_id"] == template_id
    assert row["period"] == "2026-01"


def test_expense_exists_per_period_is_the_idempotency_key(db):
    template_id = db.add_recurring_expense(_template(db))
    assert db.recurring_expense_exists(template_id, "2026-01") is None
    db.add_expense(Expense(
        property_id=_prop_id(db), date="2026-01-05", category="condo",
        amount=35.0, recurring_id=template_id, period="2026-01",
    ))
    assert db.recurring_expense_exists(template_id, "2026-01") is not None
    assert db.recurring_expense_exists(template_id, "2026-02") is None


def test_recurring_expenses_count_towards_empty_guard(tmp_path: Path):
    """The demo-data guard must see templates, not just expenses."""
    db = Database(data_dir=tmp_path)
    assert db.is_empty() is True
    prop_id = db.add_property(Property(name="Holding"))
    db.add_recurring_expense(RecurringExpense(
        property_id=prop_id, category="condo", amount=35.0, start_month="2026-01"))
    assert db.is_empty() is False

    db.wipe(["expenses", "recurring_expenses", "properties"])
    assert db.is_empty() is True
    db.close()


def test_v1_database_migrates_and_keeps_its_rows(tmp_path: Path):
    """An existing install must gain the new columns without losing data."""
    db_path = tmp_path / "landlord.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_info (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO schema_info(key, value) VALUES ('version', '1');
        CREATE TABLE properties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        INSERT INTO properties(name) VALUES ('Legacy flat');
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            renovation_id INTEGER,
            date TEXT DEFAULT '',
            category TEXT DEFAULT 'other',
            amount REAL DEFAULT 0,
            vendor TEXT DEFAULT '',
            description TEXT DEFAULT '',
            receipt_path TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        );
        INSERT INTO expenses(property_id, date, category, amount)
            VALUES (1, '2025-11-02', 'condo', 30);
        """
    )
    conn.commit()
    conn.close()

    database = Database(path=db_path)
    columns = {r["name"] for r in database.query("PRAGMA table_info(expenses)")}
    assert {"recurring_id", "period"} <= columns
    legacy = database.query_one("SELECT * FROM expenses WHERE date = '2025-11-02'")
    assert legacy["amount"] == 30
    assert legacy["period"] == ""
    assert legacy["recurring_id"] is None
    assert database.get_setting("version") == "2" or database.query_one(
        "SELECT value FROM schema_info WHERE key = 'version'")["value"] == "2"
    database.close()


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp, tmp_path: Path):
    ctx = AppContext(data_dir=tmp_path)
    prop_id = ctx.db.add_property(Property(name="P2 — Caldas"))
    ctx.db.add_recurring_expense(RecurringExpense(
        property_id=prop_id, category="condo", amount=35.0,
        description="Condo contribution", frequency="monthly",
        day_of_month=5, start_month="2026-01"))
    win = MainWindow(ctx)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_recurring_page_is_reachable(window):
    assert "recurring" in window.pages
    assert window.pages["recurring"] is window.recurring
    keys = [key for key, _ in window._nav_order]
    assert "recurring" in keys
    assert keys.index("recurring") == keys.index("expenses") + 1


def test_generate_month_creates_rows_once(window):
    view = window.recurring
    period = "2026-03"
    assert view.create_expenses_for_period(period) == 1
    # Second run for the same month must create nothing (no double-charge).
    assert view.create_expenses_for_period(period) == 0

    rows = window.ctx.db.expenses()
    assert len(rows) == 1
    assert rows[0]["amount"] == 35.0
    assert rows[0]["date"] == "2026-03-05"
    assert rows[0]["period"] == period


def test_generated_row_shows_up_on_the_expenses_page(window):
    window.recurring.create_expenses_for_period("2026-04")
    window.expenses.refresh()
    assert len(window.expenses._records) == 1
    assert "35" in window.expenses._records[0]["description"] or \
        window.expenses._records[0]["amount"] == 35.0


def test_template_list_and_footer_render(window):
    view = window.recurring
    view.refresh()
    assert len(view._records) == 1
    footer = view.footer_text()
    assert "35" in footer
    labels = [view.table.horizontalHeaderItem(i).text()
              for i in range(view.table.columnCount())]
    assert "Per month" in labels
    assert "How often" in labels
    # Every header must be translated, never a raw key.
    assert not any(label.startswith(("monthly_", "day_of_", "active_", "freq_"))
                   for label in labels)


def test_deleting_template_keeps_generated_expenses(window):
    window.recurring.create_expenses_for_period("2026-05")
    assert window.ctx.db.count("expenses") == 1
    template_id = window.ctx.db.recurring_expenses()[0]["id"]
    window.ctx.db.delete_recurring_expense(template_id)
    assert window.ctx.db.recurring_expenses() == []
    assert window.ctx.db.count("expenses") == 1


def test_generate_expenses_survives_language_switch(window):
    for language in ("pt", "en"):
        set_language(language)
        window.retranslate()
        window.recurring.refresh()
        assert window.recurring.footer_text()
    set_language("en")


def test_generate_button_is_actually_wired(window, monkeypatch):
    """A generator nobody can click is not a feature — drive the real button."""
    from PySide6.QtWidgets import QMessageBox

    messages = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *args, **kwargs: messages.append(args[1] if len(args) > 1 else ""),
    )

    view = window.recurring
    view.month_combo.setCurrentIndex(view.month_combo.findData("2026-06"))
    view.generate_button.click()

    assert window.ctx.db.count("expenses") == 1
    assert messages, "the user must be told what happened"

    # Clicking again for the same month must not double-charge.
    view.generate_button.click()
    assert window.ctx.db.count("expenses") == 1


def test_add_template_through_the_form_widgets(window):
    """Exercise the real dialog widget path: blanks must not reach SQL as NULL."""
    from landlord_tracker.ui.base import build_widget, read_widget

    view = window.recurring
    fields = view.form_fields()
    widgets = {f.name: build_widget(f) for f in fields}

    prop_id = window.ctx.db.properties()[0]["id"]
    fields_by_name = {f.name: f for f in fields}
    widgets["property_id"].setCurrentIndex(widgets["property_id"].findData(prop_id))
    widgets["amount"].setValue(35.0)
    widgets["category"].setCurrentIndex(widgets["category"].findData("condo"))
    widgets["frequency"].setCurrentIndex(widgets["frequency"].findData("monthly"))
    widgets["day_of_month"].setValue(5)
    widgets["start_month"].setText("2026-02")
    # vendor / description / notes deliberately left blank

    values = {name: read_widget(fields_by_name[name], widget)
              for name, widget in widgets.items()}
    view.create(values)
    view.refresh()

    assert window.ctx.db.count("recurring_expenses") == 2
    created = [r for r in view._records if r["start_month"] == "2026-02"]
    assert len(created) == 1
    row = created[0]
    assert row["amount"] == 35.0
    assert row["day_of_month"] == 5
    assert row["vendor"] == "" and row["notes"] == "", "blank fields must be '', not NULL"
    assert row["end_month"] == ""
    assert row["is_active"] == 1


def test_recurring_screen_does_not_borrow_rent_or_lease_wording(window):
    """Guard the whole screen against reusing rent/lease labels.

    A rent-specific key ("Rent due day") leaked onto this screen three separate
    times: as the form label, the table header, and the XLSX header. Each was
    fixed individually. This checks the entire view at once, in one language, so
    the next one is caught here instead of in a screenshot from Rodrigo.
    """
    set_language("en")
    view = window.recurring
    view.retranslate()

    labels = [f.label for f in view.form_fields()]
    headers = [view.table.horizontalHeaderItem(i).text()
               for i in range(view.table.columnCount())]
    assert labels, "the form must declare fields"

    borrowed = ("rent", "lease", "deposit", "tenant")
    for text in labels + headers:
        lowered = text.lower()
        for word in borrowed:
            assert word not in lowered, (
                f"{word!r} wording leaked onto the recurring screen: {text!r}"
            )

    # The day field must say what it does, not what rents do.
    assert view.form_fields()[4].label == "Charged on day"
