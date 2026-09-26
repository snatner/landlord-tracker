"""Properties / units screen."""

from __future__ import annotations

from typing import Any, Optional

from ..i18n import tr
from ..models import Property
from ..services.formatting import format_money
from .base import Column, CrudView, Field


class PropertiesView(CrudView):
    title_key = "nav_properties"
    subtitle_key = "properties_subtitle"
    columns = [
        Column("property_name", stretch=True),
        Column("city", 150),
        Column("purchase_price", 130, money=True),
        Column("current_value", 130, money=True),
        Column("monthly_fixed_costs", 140, money=True),
        Column("capital_gain", 130, money=True),
        Column("is_active", 120),
    ]

    def fetch(self) -> list[dict]:
        return self.ctx.db.properties()

    def row_values(self, record: dict) -> list[Any]:
        currency = self.ctx.currency
        gain = (record.get("current_value") or 0) - (record.get("purchase_price") or 0)
        color = "#2E9E63" if gain > 0 else ("#D0534B" if gain < 0 else None)
        return [
            record["name"],
            record.get("city") or "",
            format_money(record.get("purchase_price"), currency),
            format_money(record.get("current_value"), currency),
            format_money(record.get("monthly_fixed_costs"), currency),
            (format_money(gain, currency), color),
            tr("yes") if record.get("is_active") else tr("no"),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("name", tr("property_name"), required=True),
            Field("address", tr("address")),
            Field("city", tr("city")),
            Field("postcode", tr("postcode")),
            Field("property_type", tr("property_type"), default=""),
            Field("purchase_price", tr("purchase_price"), kind="money"),
            Field("purchase_date", tr("purchase_date"), kind="date"),
            Field("current_value", tr("current_value"), kind="money"),
            Field("monthly_fixed_costs", tr("monthly_fixed_costs"), kind="money"),
            Field("size_m2", tr("size_m2"), kind="float"),
            Field("notes", tr("notes"), kind="multiline"),
            Field("is_active", tr("is_active"), kind="check", default=1),
        ]

    def create(self, values: dict) -> None:
        self.ctx.db.add_property(Property(**values))

    def update(self, record_id: int, values: dict) -> None:
        self.ctx.db.update_property(record_id, Property(**values))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_property(record_id)

    def footer_text(self) -> str:
        records = self._records
        if not records:
            return ""
        currency = self.ctx.currency
        total_value = sum(r.get("current_value") or 0 for r in records)
        total_purchase = sum(r.get("purchase_price") or 0 for r in records)
        total_fixed = sum(r.get("monthly_fixed_costs") or 0 for r in records)
        return (
            f"{len(records)} × {tr('properties')} · "
            f"{tr('portfolio_value')}: {format_money(total_value, currency)} · "
            f"{tr('purchase_total')}: {format_money(total_purchase, currency)} · "
            f"{tr('monthly_fixed_costs')}: {format_money(total_fixed, currency)}"
        )
