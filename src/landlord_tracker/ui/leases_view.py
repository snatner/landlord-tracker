"""Leases screen: contract terms, dates and rent increases."""

from __future__ import annotations

from typing import Any

from ..i18n import tr
from ..models import Lease, LeaseStatus
from ..services.formatting import format_money
from .base import Column, CrudView, Field


class LeasesView(CrudView):
    title_key = "nav_leases"
    subtitle_key = "leases_subtitle"
    columns = [
        Column("property", stretch=True),
        Column("tenant", 180),
        Column("start_date", 115),
        Column("end_date", 115),
        Column("monthly_rent", 125, money=True),
        Column("deposit", 115, money=True),
        Column("due_day", 95, align="right"),
        Column("last_increase", 130),
        Column("status", 105),
    ]

    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def _tenant_options(self) -> list[tuple[int, str]]:
        return [(t["id"], t["full_name"]) for t in self.ctx.db.tenants(include_inactive=False)]

    def fetch(self) -> list[dict]:
        return self.ctx.db.leases()

    def row_values(self, record: dict) -> list[Any]:
        return [
            record.get("property_name") or "",
            record.get("tenant_name") or "",
            record.get("start_date") or "",
            record.get("end_date") or "",
            format_money(record.get("monthly_rent"), self.ctx.currency),
            format_money(record.get("deposit_amount"), self.ctx.currency),
            str(record.get("due_day") or 1),
            record.get("last_increase_date") or "",
            tr(f"lease_status_{record.get('status')}"),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("property_id", tr("property"), kind="combo",
                  options=self._property_options(), required=True),
            Field("tenant_id", tr("tenant"), kind="combo",
                  options=self._tenant_options(), required=True),
            Field("start_date", tr("start_date"), kind="date", required=True),
            Field("end_date", tr("end_date"), kind="date"),
            Field("monthly_rent", tr("monthly_rent"), kind="money"),
            Field("deposit_amount", tr("deposit"), kind="money"),
            Field("due_day", tr("due_day"), kind="int", minimum=1, maximum=31, default=1),
            Field("last_increase_date", tr("last_increase"), kind="date"),
            Field("status", tr("status"), kind="combo", default=LeaseStatus.ACTIVE.value,
                  options=[(LeaseStatus.ACTIVE.value, tr("lease_status_active")),
                           (LeaseStatus.ENDED.value, tr("lease_status_ended"))]),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def create(self, values: dict) -> None:
        self.ctx.db.add_lease(Lease(**values))

    def update(self, record_id: int, values: dict) -> None:
        self.ctx.db.update_lease(record_id, Lease(**values))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_lease(record_id)

    def footer_text(self) -> str:
        active = [r for r in self._records if r.get("status") != LeaseStatus.ENDED.value]
        rent_roll = sum(r.get("monthly_rent") or 0 for r in active)
        deposits = sum(r.get("deposit_amount") or 0 for r in active)
        return (
            f"{tr('lease_status_active')}: {len(active)} · "
            f"{tr('monthly_rent')}: {format_money(rent_roll, self.ctx.currency)} · "
            f"{tr('deposit')}: {format_money(deposits, self.ctx.currency)}"
        )
