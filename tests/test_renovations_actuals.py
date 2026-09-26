"""Renovation actuals: real spend only, and a visible link to the payments.

Rodrigo's requirement (Sep 2026): money added through Expenses and linked to a
renovation is the right mechanism, but the link has to be visible, and a
renovation's Actual must start at €0 rather than borrowing the budget.
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
from landlord_tracker.models import Expense, Property, Renovation  # noqa: E402
from landlord_tracker.services import calculations as calc  # noqa: E402
from landlord_tracker.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _seed(db: Database) -> dict:
    prop = db.add_property(Property(name="Travessa do Forno 8"))
    job = db.add_renovation(Renovation(
        property_id=prop, title="Kitchen replacement", category="kitchen",
        status="in_progress", start_date="2026-02-01", budget=6500,
        expected_monthly_rent_increase=90,
    ))
    return {"property": prop, "renovation": job}


@pytest.fixture()
def ctx(tmp_path: Path):
    context = AppContext(data_dir=tmp_path)
    context.seed = _seed(context.db)
    yield context
    context.close()


@pytest.fixture()
def window(qapp, ctx):
    win = MainWindow(ctx)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


# --------------------------------------------------------------------------
# database: the link
# --------------------------------------------------------------------------
def test_unstarted_renovation_has_zero_payments_and_zero_actual(ctx):
    row = ctx.db.renovations()[0]
    assert row["payment_count"] == 0
    assert calc.to_float(row["logged_cost"]) == 0.0


def test_linked_expense_is_counted_and_summed(ctx):
    ctx.db.add_expense(Expense(
        property_id=ctx.seed["property"], date="2026-02-05", category="maintenance",
        amount=2400.0, description="Kitchen units deposit",
        renovation_id=ctx.seed["renovation"],
    ))
    ctx.db.add_expense(Expense(
        property_id=ctx.seed["property"], date="2026-03-02", category="maintenance",
        amount=1100.0, description="Worktop and tiling",
        renovation_id=ctx.seed["renovation"],
    ))
    row = ctx.db.renovations()[0]
    assert row["payment_count"] == 2
    assert calc.to_float(row["logged_cost"]) == 3500.0


def test_an_unlinked_expense_does_not_touch_the_renovation(ctx):
    """The link must be explicit; a random expense is not renovation spend."""
    ctx.db.add_expense(Expense(
        property_id=ctx.seed["property"], date="2026-02-09", category="repair",
        amount=999.0, description="Unrelated repair",
    ))
    row = ctx.db.renovations()[0]
    assert row["payment_count"] == 0
    assert calc.to_float(row["logged_cost"]) == 0.0


def test_the_link_is_visible_from_the_expense_side(ctx):
    ctx.db.add_expense(Expense(
        property_id=ctx.seed["property"], date="2026-02-05", category="maintenance",
        amount=2400.0, renovation_id=ctx.seed["renovation"],
    ))
    expense = ctx.db.expenses()[0]
    assert expense["renovation_title"] == "Kitchen replacement"


# --------------------------------------------------------------------------
# UI: what the landlord actually sees
# --------------------------------------------------------------------------
def test_renovation_row_starts_at_zero_not_budget(window):
    set_language("en")
    view = window.renovations
    view.refresh()
    cells = view.row_values(view._records[0])
    # Coloured cells are (text, colour) tuples, so compare on a flattened string
    # rather than by list membership.
    flat = " ".join(str(c) for c in cells)

    assert "€0.00" in flat, "Actual must start at zero"
    assert "€6,500.00" in flat, "the budget must still be visible as the plan"
    assert "—" in flat, "variance must not be invented before spending starts"

    headers = [view.table.horizontalHeaderItem(i).text()
               for i in range(view.table.columnCount())]
    assert str(cells[headers.index("Payments")]) == "0", "no payments linked yet"


def test_row_after_linking_a_payment_shows_actual_and_variance(window):
    set_language("en")
    ctx = window.ctx
    ctx.db.add_expense(Expense(
        property_id=ctx.seed["property"], date="2026-02-05", category="maintenance",
        amount=2400.0, description="Kitchen units deposit",
        renovation_id=ctx.seed["renovation"],
    ))
    view = window.renovations
    view.refresh()
    cells = view.row_values(view._records[0])
    flat = " ".join(str(c) for c in cells)

    assert "€2,400.00" in flat, "actual should be the real spend"
    assert "—" not in flat, "variance becomes meaningful once spending exists"

    headers = [view.table.horizontalHeaderItem(i).text()
               for i in range(view.table.columnCount())]
    assert str(cells[headers.index("Payments")]) == "1", "the visible link"


def test_footer_totals_use_real_spend(window):
    set_language("en")
    view = window.renovations
    view.refresh()
    footer = view.footer_text()
    assert "Payments" in footer
    assert "€0.00" in footer


def test_payments_header_and_no_lease_wording(window):
    """Renovation terms are its own; lease/rent-payment wording is not.

    Note: "Monthly rent uplift" IS correct here — a renovation exists to raise
    the rent. The guard is against *lease* concepts (due day, deposit, tenant)
    leaking in, which is the mistake that keeps happening on new screens.
    """
    set_language("en")
    view = window.renovations
    view.retranslate()
    headers = [view.table.horizontalHeaderItem(i).text()
               for i in range(view.table.columnCount())]
    assert "Payments" in headers

    lowered = " ".join(headers).lower()
    for word in ("lease", "tenant", "deposit", "due day"):
        assert word not in lowered, f"{word!r} leaked into renovation headers"
