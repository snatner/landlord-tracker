"""Renovations screen: budget vs actual cost, and payback per project.

This is the feature landlords keep trying to build in spreadsheets: how much did
the works really cost, did it stay inside budget, and when does the extra rent
pay it back?
"""

from __future__ import annotations

from typing import Any

from ..i18n import tr
from ..models import RENOVATION_CATEGORIES, RENOVATION_STATUSES, Renovation
from ..services import calculations as calc
from ..services.formatting import format_money, format_months
from .base import Column, CrudView, Field, today_iso


class RenovationsView(CrudView):
    title_key = "nav_renovations"
    subtitle_key = "renovations_subtitle"
    columns = [
        Column("renovation", stretch=True),
        Column("property", 160),
        Column("category", 130),
        Column("status", 110),
        Column("start_date", 105),
        Column("end_date", 105),
        Column("budget", 115, money=True),
        Column("actual", 115, money=True),
        Column("payments", 105, align="right"),
        Column("variance", 115, money=True),
        Column("monthly_uplift", 120, money=True),
        Column("payback_months", 130, align="right", bold=True),
        Column("contractor", 150),
    ]

    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def fetch(self) -> list[dict]:
        return self.ctx.db.renovations()

    def row_values(self, record: dict) -> list[Any]:
        currency = self.ctx.currency
        budget = calc.to_float(record.get("budget"))
        # Actual is real money only, so it starts at €0 until a linked expense
        # exists. Variance is therefore meaningless until then and is shown as
        # "—" rather than a green minus-budget figure that looks like a saving.
        actual = calc.renovation_actual_cost([record.get("logged_cost")])
        payments = int(record.get("payment_count") or 0)

        if payments:
            variance = calc.renovation_variance(budget, actual)
            variance_text = format_money(variance, currency)
            variance_color = "#D0534B" if variance > 0.01 else (
                "#2E9E63" if variance < -0.01 else None)
        else:
            variance_text, variance_color = "—", None

        payback = calc.renovation_payback_months(
            actual, calc.to_float(record.get("expected_monthly_rent_increase")))
        return [
            record.get("title") or "",
            record.get("property_name") or "",
            tr(f"reno_cat_{record.get('category')}"),
            tr(f"reno_status_{record.get('status')}"),
            record.get("start_date") or "",
            record.get("end_date") or "",
            format_money(budget, currency),
            format_money(actual, currency),
            str(payments),
            (variance_text, variance_color),
            format_money(record.get("expected_monthly_rent_increase"), currency),
            (format_months(payback) if payback is not None else tr("payback_unknown")),
            record.get("contractor") or "",
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("title", tr("renovation"), required=True),
            Field("property_id", tr("property"), kind="combo",
                  options=self._property_options(), required=True),
            Field("category", tr("category"), kind="combo",
                  options=[(c, tr(f"reno_cat_{c}")) for c in RENOVATION_CATEGORIES]),
            Field("status", tr("status"), kind="combo",
                  options=[(s, tr(f"reno_status_{s}")) for s in RENOVATION_STATUSES]),
            Field("start_date", tr("start_date"), kind="date", default=today_iso()),
            Field("end_date", tr("end_date"), kind="date"),
            Field("budget", tr("budget"), kind="money"),
            Field("expected_monthly_rent_increase", tr("monthly_uplift"), kind="money"),
            Field("expected_value_increase", tr("expected_value_increase"), kind="money"),
            Field("contractor", tr("contractor")),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def create(self, values: dict) -> None:
        self.ctx.db.add_renovation(Renovation(**values))

    def update(self, record_id: int, values: dict) -> None:
        self.ctx.db.update_renovation(record_id, Renovation(**values))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_renovation(record_id)

    def footer_text(self) -> str:
        currency = self.ctx.currency
        budgets = sum(calc.to_float(r.get("budget")) for r in self._records)
        logged = sum(calc.to_float(r.get("logged_cost")) for r in self._records)
        payments = sum(int(r.get("payment_count") or 0) for r in self._records)
        uplift = sum(calc.to_float(r.get("expected_monthly_rent_increase"))
                     for r in self._records)
        # Payback is measured against real spend; with nothing logged there is no
        # investment to pay back yet, so it stays "unknown" rather than being
        # computed from the budget.
        payback = calc.renovation_payback_months(logged, uplift)
        payback_text = (f"{tr('payback_months')}: {format_months(payback)}"
                        if payback is not None else tr("payback_unknown"))
        return (
            f"{tr('budget')}: {format_money(budgets, currency)} · "
            f"{tr('actual')}: {format_money(logged, currency)} · "
            f"{tr('payments')}: {payments} · "
            f"{tr('monthly_uplift')}: {format_money(uplift, currency)} · {payback_text}"
        )
