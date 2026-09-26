"""Tenants screen: contacts, tax numbers, emergency contacts, linked property."""

from __future__ import annotations

from typing import Any

from ..i18n import tr
from ..models import Tenant
from .base import Column, CrudView, Field


class TenantsView(CrudView):
    title_key = "nav_tenants"
    subtitle_key = "tenants_subtitle"
    columns = [
        Column("full_name", stretch=True),
        Column("property", 190),
        Column("phone", 140),
        Column("email", 200),
        Column("tax_number", 110),
        Column("leases_count", 110, align="right"),
        Column("is_active", 100),
    ]

    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def fetch(self) -> list[dict]:
        return self.ctx.db.tenants()

    def row_values(self, record: dict) -> list[Any]:
        leases = [l for l in self.ctx.db.leases(include_ended=False)
                  if l["tenant_id"] == record["id"]]
        return [
            record["full_name"],
            record.get("property_name") or "",
            record.get("phone") or "",
            record.get("email") or "",
            record.get("tax_number") or "",
            str(len(leases)),
            tr("yes") if record.get("is_active") else tr("no"),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("full_name", tr("full_name"), required=True),
            Field("property_id", tr("property"), kind="combo",
                  options=self._property_options(), required=True),
            Field("phone", tr("phone")),
            Field("email", tr("email")),
            Field("tax_number", tr("tax_number")),
            Field("emergency_contact", tr("emergency_contact")),
            Field("notes", tr("notes"), kind="multiline"),
            Field("is_active", tr("is_active"), kind="check", default=1),
        ]

    def form_values(self, record: dict) -> dict:
        values = dict(record)
        if values.get("property_id") == 0:
            values["property_id"] = None
        return values

    def create(self, values: dict) -> None:
        self.ctx.db.add_tenant(Tenant(**values))

    def update(self, record_id: int, values: dict) -> None:
        self.ctx.db.update_tenant(record_id, Tenant(**values))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_tenant(record_id)

    def footer_text(self) -> str:
        active = [r for r in self._records if r.get("is_active")]
        return f"{len(self._records)} × {tr('tenants')} · {tr('lease_status_active')}: {len(active)}"
