"""Rent screen: the ledger landlords check every month.

Includes a one-click "generate this month's rent from active leases" action and
quick paid/unpaid toggles, because that is the repetitive chore the app exists
to remove.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from typing import Any, Optional

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QMessageBox, QPushButton

from ..i18n import tr
from ..models import RentPayment, RentStatus
from ..services import calculations as calc
from ..services.formatting import format_money
from .base import Column, CrudView, Field, month_keys, today_iso


class RentView(CrudView):
    title_key = "nav_rent"
    subtitle_key = "rent_subtitle"
    columns = [
        Column("period", 110),
        Column("property", stretch=True),
        Column("tenant", 160),
        Column("due_amount", 120, money=True),
        Column("due_date", 110),
        Column("paid_amount", 120, money=True),
        Column("paid_date", 110),
        Column("balance", 110, money=True),
        Column("status", 110, bold=True),
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

        self.generate_button = QPushButton(tr("generate_month"))
        self.generate_button.clicked.connect(self.generate_month)
        toolbar.addWidget(self.generate_button)

        self.paid_button = QPushButton(tr("mark_paid"))
        self.paid_button.clicked.connect(self.mark_paid)
        toolbar.addWidget(self.paid_button)

        self.unpaid_button = QPushButton(tr("mark_unpaid"))
        self.unpaid_button.clicked.connect(self.mark_unpaid)
        toolbar.addWidget(self.unpaid_button)

    def _reload_month_combo(self) -> None:
        current = self._period_filter
        periods = self.ctx.db.rent_periods()
        for period in month_keys(count=18, include_future=3):
            if period not in periods:
                periods.append(period)
        periods = sorted(set(periods), reverse=True)
        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        for period in periods:
            self.month_combo.addItem(self._label_for(period), period)
        target = current or _dt.date.today().strftime("%Y-%m")
        index = self.month_combo.findData(target)
        self.month_combo.setCurrentIndex(index if index >= 0 else 0)
        self._period_filter = self.month_combo.currentData()
        self.month_combo.blockSignals(False)

    def _label_for(self, period: str) -> str:
        from ..services.calculations import month_label

        return month_label(period, self.ctx.language)

    def _on_month_changed(self, _index: int) -> None:
        self._period_filter = self.month_combo.currentData()
        self.refresh()

    # -- data -----------------------------------------------------------
    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def _lease_options(self) -> list[tuple[int, str]]:
        return [
            (l["id"], f"{l.get('property_name') or ''} — {l.get('tenant_name') or ''}")
            for l in self.ctx.db.active_leases()
        ]

    def fetch(self) -> list[dict]:
        if self._period_filter is None:
            self._reload_month_combo()
        return self.ctx.db.rent_payments(self._period_filter)

    def row_values(self, record: dict) -> list[Any]:
        currency = self.ctx.currency
        balance = calc.rent_balance(record.get("due_amount"), record.get("paid_amount"))
        status = record.get("status") or RentStatus.UNPAID.value
        color = self.ctx.theme.status_color(status)
        return [
            self._label_for(record["period"]),
            record.get("property_name") or "",
            record.get("tenant_name") or "",
            format_money(record.get("due_amount"), currency),
            record.get("due_date") or "",
            format_money(record.get("paid_amount"), currency),
            record.get("paid_date") or "",
            (format_money(balance, currency), color if balance > 0 else None),
            (tr(f"rent_status_{status}"), color),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("lease_id", tr("lease"), kind="combo",
                  options=self._lease_options(), required=True),
            Field("period", tr("period"), kind="text", required=True,
                  placeholder="YYYY-MM", default=self._period_filter or ""),
            Field("due_amount", tr("due_amount"), kind="money"),
            Field("due_date", tr("due_date"), kind="date"),
            Field("paid_amount", tr("paid_amount"), kind="money"),
            Field("paid_date", tr("paid_date"), kind="date"),
            Field("method", tr("method")),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def form_values(self, record: dict) -> dict:
        return dict(record)

    def create(self, values: dict) -> None:
        lease = self.ctx.db.lease(int(values["lease_id"]))
        if not lease:
            return
        status = calc.compute_rent_status(
            values.get("due_amount", 0), values.get("paid_amount", 0),
            values.get("due_date"), values.get("paid_date"),
        )
        self.ctx.db.add_rent(RentPayment(
            lease_id=lease["id"],
            property_id=lease["property_id"],
            tenant_id=lease["tenant_id"],
            period=values.get("period") or _dt.date.today().strftime("%Y-%m"),
            due_amount=values.get("due_amount", 0),
            due_date=values.get("due_date", ""),
            paid_amount=values.get("paid_amount", 0),
            paid_date=values.get("paid_date", ""),
            status=status,
            method=values.get("method", ""),
            notes=values.get("notes", ""),
        ))

    def update(self, record_id: int, values: dict) -> None:
        existing = self.ctx.db.query_one("SELECT * FROM rent_payments WHERE id = ?", (record_id,))
        if not existing:
            return
        lease = self.ctx.db.lease(int(values["lease_id"])) or existing
        status = calc.compute_rent_status(
            values.get("due_amount", 0), values.get("paid_amount", 0),
            values.get("due_date"), values.get("paid_date"),
        )
        self.ctx.db.update_rent(record_id, RentPayment(
            lease_id=int(values["lease_id"]),
            property_id=lease["property_id"],
            tenant_id=lease["tenant_id"],
            period=values.get("period") or existing["period"],
            due_amount=values.get("due_amount", 0),
            due_date=values.get("due_date", ""),
            paid_amount=values.get("paid_amount", 0),
            paid_date=values.get("paid_date", ""),
            status=status,
            method=values.get("method", ""),
            notes=values.get("notes", ""),
        ))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_rent(record_id)

    # -- actions --------------------------------------------------------
    def generate_month(self) -> None:
        period = self._period_filter or _dt.date.today().strftime("%Y-%m")
        if not self._lease_options():
            QMessageBox.information(self, tr("generate_month"), tr("no_results"))
            return
        created = self.create_rent_for_period(period)
        if created:
            self.after_change()
            QMessageBox.information(self, tr("generate_month"),
                                    tr("generated_rows", count=created))
        else:
            QMessageBox.information(self, tr("generate_month"), tr("nothing_to_generate"))

    def create_rent_for_period(self, period: str) -> int:
        """Create missing rent rows for every active lease. Returns count."""
        try:
            year, month = (int(x) for x in period.split("-"))
        except (ValueError, AttributeError):
            return 0
        last_day = calendar.monthrange(year, month)[1]
        created = 0
        for lease in self.ctx.db.active_leases():
            if self.ctx.db.rent_exists(lease["id"], period):
                continue
            due_day = min(max(int(lease.get("due_day") or 1), 1), last_day)
            self.ctx.db.add_rent(RentPayment(
                lease_id=lease["id"],
                property_id=lease["property_id"],
                tenant_id=lease["tenant_id"],
                period=period,
                due_amount=calc.to_float(lease.get("monthly_rent")),
                due_date=f"{period}-{due_day:02d}",
                paid_amount=0.0,
                status=RentStatus.UNPAID.value,
            ))
            created += 1
        return created

    def _set_paid(self, paid: bool) -> None:
        record_id = self.table.selected_id()
        if record_id is None:
            QMessageBox.information(self, tr("mark_paid"), tr("none_selected"))
            return
        record = self.find_record(record_id) or {}
        if paid:
            due = calc.to_float(record.get("due_amount"))
            self.ctx.db.update_rent(record_id, RentPayment(
                lease_id=int(record.get("lease_id") or 0),
                property_id=int(record.get("property_id") or 0),
                tenant_id=int(record.get("tenant_id") or 0),
                period=record.get("period") or "",
                due_amount=due,
                due_date=record.get("due_date") or "",
                paid_amount=due,
                paid_date=today_iso(),
                status=RentStatus.PAID.value,
                method=record.get("method") or "",
                notes=record.get("notes") or "",
            ))
        else:
            self.ctx.db.update_rent(record_id, RentPayment(
                lease_id=int(record.get("lease_id") or 0),
                property_id=int(record.get("property_id") or 0),
                tenant_id=int(record.get("tenant_id") or 0),
                period=record.get("period") or "",
                due_amount=calc.to_float(record.get("due_amount")),
                due_date=record.get("due_date") or "",
                paid_amount=0.0,
                paid_date="",
                status=calc.compute_rent_status(
                    record.get("due_amount"), 0, record.get("due_date"), None),
                method=record.get("method") or "",
                notes=record.get("notes") or "",
            ))
        self.after_change()

    def mark_paid(self) -> None:
        self._set_paid(True)

    def mark_unpaid(self) -> None:
        self._set_paid(False)

    # -- footer ---------------------------------------------------------
    def footer_text(self) -> str:
        currency = self.ctx.currency
        expected = sum(calc.to_float(r.get("due_amount")) for r in self._records)
        collected = sum(calc.to_float(r.get("paid_amount")) for r in self._records)
        rate = calc.rent_collection_rate(collected, expected)
        outstanding = calc.arrears(self._records)
        from ..services.formatting import format_percent

        return (
            f"{tr('rent_expected')}: {format_money(expected, currency)} · "
            f"{tr('rent_collected')}: {format_money(collected, currency)} · "
            f"{tr('rent_collection_rate')}: {format_percent(rate)} · "
            f"{tr('arrears')}: {format_money(outstanding, currency)}"
        )

    def retranslate(self) -> None:
        super().retranslate()
        self.generate_button.setText(tr("generate_month"))
        self.paid_button.setText(tr("mark_paid"))
        self.unpaid_button.setText(tr("mark_unpaid"))
        self._reload_month_combo()
