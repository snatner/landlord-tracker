"""Recurring expenses: costs that come back every month without being retyped.

A condo contribution of €35/month, a quarterly insurance premium or the yearly
IMI are all the same shape: one amount, one day of the month, a frequency. This
screen stores those as templates and materialises them into real expense rows
with one click, exactly like Rent does for active leases.

Design rules (deliberate):
* Templates are *plans*, not money. Nothing here touches the expense ledger
  until the user generates — so the ledger stays a record of facts.
* ``(recurring_id, period)`` is the idempotency key. Generating the same month
  twice creates nothing the second time; it never double-charges.
* Deleting a template keeps already-generated expense rows as history.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QMessageBox, QPushButton

from ..i18n import tr
from ..models import EXPENSE_CATEGORIES, RECURRENCE_FREQUENCIES, Expense, RecurringExpense
from ..services import calculations as calc
from ..services.formatting import format_money
from .base import Column, CrudView, Field, month_keys, today_iso


class RecurringExpensesView(CrudView):
    title_key = "nav_recurring"
    subtitle_key = "recurring_subtitle"
    add_label_key = "add_recurring"
    columns = [
        Column("property", stretch=True),
        Column("category", 150),
        Column("amount", 110, money=True, bold=True),
        Column("monthly_equivalent", 120, money=True),
        Column("frequency", 120),
        Column("day_of_month", 110),
        Column("active_window", 170),
        Column("is_active", 100),
    ]

    def __init__(self, ctx, parent=None):
        self._period_filter: Optional[str] = None
        super().__init__(ctx, parent)

    # -- toolbar extras -------------------------------------------------
    def _add_extra_controls(self, toolbar: QHBoxLayout) -> None:
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(140)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        toolbar.addWidget(self.month_combo)

        self.generate_button = QPushButton(tr("generate_expenses"))
        self.generate_button.clicked.connect(self.generate_month)
        toolbar.addWidget(self.generate_button)

    def _reload_month_combo(self) -> None:
        current = self._period_filter
        periods = month_keys(count=18, include_future=3)
        for existing in self._generated_periods():
            if existing not in periods:
                periods.append(existing)
        periods = sorted(set(periods), reverse=True)
        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        for period in periods:
            self.month_combo.addItem(calc.month_label(period, self.ctx.language), period)
        target = current or _dt.date.today().strftime("%Y-%m")
        index = self.month_combo.findData(target)
        self.month_combo.setCurrentIndex(index if index >= 0 else 0)
        self._period_filter = self.month_combo.currentData()
        self.month_combo.blockSignals(False)

    def _generated_periods(self) -> list[str]:
        rows = self.ctx.db.query(
            "SELECT DISTINCT period FROM expenses WHERE period != '' ORDER BY period DESC"
        )
        return [r["period"] for r in rows]

    def _on_month_changed(self, _index: int) -> None:
        self._period_filter = self.month_combo.currentData()
        self.refresh()

    # -- options --------------------------------------------------------
    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def _category_options(self) -> list[tuple[str, str]]:
        return [(c, tr(f"expense_cat_{c}")) for c in EXPENSE_CATEGORIES]

    def _frequency_options(self) -> list[tuple[str, str]]:
        return [(f, tr(f"freq_{f}")) for f in RECURRENCE_FREQUENCIES]

    # -- data -----------------------------------------------------------
    def fetch(self) -> list[dict]:
        if self._period_filter is None:
            self._reload_month_combo()
        return self.ctx.db.recurring_expenses()

    def row_values(self, record: dict) -> list[Any]:
        currency = self.ctx.currency
        monthly = calc.recurring_monthly_equivalent(
            record.get("amount"), record.get("frequency")
        )
        start = record.get("start_month") or ""
        end = record.get("end_month") or ""
        if start and end:
            window = f"{start} → {end}"
        elif start:
            window = f"{start} →"
        elif end:
            window = f"→ {end}"
        else:
            window = tr("no_end_date")
        return [
            record.get("property_name") or "",
            tr(f"expense_cat_{record.get('category')}"),
            format_money(record.get("amount"), currency),
            format_money(monthly, currency) if monthly is not None else "—",
            tr(f"freq_{record.get('frequency')}"),
            str(int(record.get("day_of_month") or 1)),
            window,
            tr("yes") if calc.as_flag(record.get("is_active", 1)) else tr("no"),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("property_id", tr("property"), kind="combo",
                  options=self._property_options(), required=True),
            Field("category", tr("category"), kind="combo",
                  options=self._category_options(), default="condo"),
            Field("amount", tr("amount"), kind="money", required=True),
            Field("frequency", tr("frequency"), kind="combo",
                  options=self._frequency_options(), default="monthly"),
            Field("day_of_month", tr("charged_on_day"), kind="int", minimum=1, maximum=31,
                  default=1),
            Field("start_month", tr("start_month"), required=True,
                  placeholder="YYYY-MM", default=self._period_filter or "",
                  span=True),
            Field("end_month", tr("end_month"), placeholder="YYYY-MM"),
            Field("vendor", tr("vendor")),
            Field("description", tr("description")),
            Field("is_active", tr("is_active"), kind="check", default=1),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def form_values(self, record: dict) -> dict:
        values = dict(record)
        values["is_active"] = 1 if calc.as_flag(record.get("is_active", 1)) else 0
        return values

    def create(self, values: dict) -> None:
        self.ctx.db.add_recurring_expense(RecurringExpense(**self._normalise(values)))

    def update(self, record_id: int, values: dict) -> None:
        self.ctx.db.update_recurring_expense(
            record_id, RecurringExpense(**self._normalise(values))
        )

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_recurring_expense(record_id)

    @staticmethod
    def _normalise(values: dict) -> dict:
        data = dict(values)
        data["day_of_month"] = int(calc.to_float(data.get("day_of_month")) or 1)
        data["is_active"] = 1 if calc.as_flag(data.get("is_active", 1)) else 0
        data["frequency"] = str(data.get("frequency") or "monthly")
        return data

    # -- actions --------------------------------------------------------
    def generate_month(self) -> None:
        period = self._period_filter or _dt.date.today().strftime("%Y-%m")
        created = self.create_expenses_for_period(period)
        title = f"{tr('generate_expenses')} · {calc.month_label(period, self.ctx.language)}"
        if created:
            self.after_change()
            QMessageBox.information(self, title, tr("generated_expense_rows", count=created))
        else:
            QMessageBox.information(self, title, tr("nothing_to_generate_expenses"))

    def create_expenses_for_period(self, period: str) -> int:
        """Create the missing expense rows for every due template. Returns count."""
        if not period:
            return 0
        created = 0
        for template in self.ctx.db.recurring_expenses():
            if not calc.recurring_due(template, period):
                continue
            if self.ctx.db.recurring_expense_exists(template["id"], period):
                continue
            self.ctx.db.add_expense(Expense(
                property_id=int(template["property_id"]),
                date=calc.recurring_due_date(template, period),
                category=template.get("category") or "other",
                amount=calc.to_float(template.get("amount")),
                vendor=template.get("vendor") or "",
                description=template.get("description") or "",
                notes=template.get("notes") or "",
                recurring_id=int(template["id"]),
                period=period,
            ))
            created += 1
        return created

    # -- footer ---------------------------------------------------------
    def footer_text(self) -> str:
        currency = self.ctx.currency
        monthly = 0.0
        for record in self._records:
            value = calc.recurring_monthly_equivalent(
                record.get("amount"), record.get("frequency")
            )
            if value and calc.as_flag(record.get("is_active", 1)):
                monthly += value
        period = self._period_filter or _dt.date.today().strftime("%Y-%m")
        due_now = sum(
            1
            for r in self._records
            if calc.recurring_due(r, period)
            and not self.ctx.db.recurring_expense_exists(r["id"], period)
        )
        return (
            f"{tr('recurring_monthly_total')}: {format_money(monthly, currency)} · "
            f"{tr('templates')}: {len(self._records)} · "
            f"{tr('pending_for_month')}: {due_now}"
        )

    def retranslate(self) -> None:
        super().retranslate()
        if hasattr(self, "generate_button"):
            self.generate_button.setText(tr("generate_expenses"))
        self._reload_month_combo()
