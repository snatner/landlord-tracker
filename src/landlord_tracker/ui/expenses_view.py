"""Expenses screen: recurring costs, repairs and receipts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QPushButton

from ..i18n import tr
from ..models import EXPENSE_CATEGORIES, Expense
from ..services.formatting import format_money
from .base import Column, CrudView, Field, today_iso


class ExpensesView(CrudView):
    title_key = "nav_expenses"
    subtitle_key = "expenses_subtitle"
    columns = [
        Column("date", 110),
        Column("property", 170),
        Column("category", 150),
        Column("amount", 120, money=True, bold=True),
        Column("vendor", 160),
        Column("description", stretch=True),
        Column("renovation", 150),
        Column("receipt_state", 110),
    ]

    def __init__(self, ctx, parent=None):
        self._date_filter: str = ""
        super().__init__(ctx, parent)

    def _add_extra_controls(self, toolbar: QHBoxLayout) -> None:
        self.receipt_button = QPushButton(tr("attach_receipt"))
        self.receipt_button.clicked.connect(self.attach_receipt)
        toolbar.addWidget(self.receipt_button)

    # -- options --------------------------------------------------------
    def _property_options(self) -> list[tuple[int, str]]:
        return [(p["id"], p["name"]) for p in self.ctx.db.properties(include_inactive=False)]

    def _renovation_options(self) -> list[tuple[int, str]]:
        options = [(0, tr("none"))]
        for reno in self.ctx.db.renovations():
            options.append((reno["id"], reno["title"]))
        return options

    def _category_options(self) -> list[tuple[str, str]]:
        return [(c, tr(f"expense_cat_{c}")) for c in EXPENSE_CATEGORIES]

    # -- data -----------------------------------------------------------
    def fetch(self) -> list[dict]:
        return self.ctx.db.expenses()

    def row_values(self, record: dict) -> list[Any]:
        return [
            record.get("date") or "",
            record.get("property_name") or "",
            tr(f"expense_cat_{record.get('category')}"),
            format_money(record.get("amount"), self.ctx.currency),
            record.get("vendor") or "",
            record.get("description") or "",
            record.get("renovation_title") or "",
            tr("yes") if record.get("receipt_path") else tr("no"),
        ]

    def form_fields(self) -> list[Field]:
        return [
            Field("date", tr("date"), kind="date", required=True, default=today_iso()),
            Field("property_id", tr("property"), kind="combo",
                  options=self._property_options(), required=True),
            Field("category", tr("category"), kind="combo",
                  options=self._category_options()),
            Field("amount", tr("amount"), kind="money", required=True),
            Field("vendor", tr("vendor")),
            Field("description", tr("description")),
            Field("renovation_id", tr("linked_renovation"), kind="combo",
                  options=self._renovation_options()),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def form_values(self, record: dict) -> dict:
        values = dict(record)
        values["renovation_id"] = record.get("renovation_id") or 0
        return values

    def _normalise(self, values: dict) -> dict:
        data = dict(values)
        if not data.get("renovation_id"):
            data["renovation_id"] = None
        return data

    def create(self, values: dict) -> None:
        self.ctx.db.add_expense(Expense(**self._normalise(values)))

    def update(self, record_id: int, values: dict) -> None:
        existing = self.find_record(record_id) or {}
        data = self._normalise(values)
        data["receipt_path"] = existing.get("receipt_path") or ""
        self.ctx.db.update_expense(record_id, Expense(**data))

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_expense(record_id)

    # -- actions --------------------------------------------------------
    def attach_receipt(self) -> None:
        record_id = self.table.selected_id()
        if record_id is None:
            QMessageBox.information(self, tr("attach_receipt"), tr("none_selected"))
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("attach_receipt"), str(Path.home()),
            "Documents (*.pdf *.png *.jpg *.jpeg *.webp *.txt);;All files (*)",
        )
        if not path:
            return
        try:
            stored = self.ctx.db.copy_document_into_vault(Path(path), "receipts")
        except OSError as error:
            QMessageBox.warning(self, tr("error"), str(error))
            return
        record = self.find_record(record_id) or {}
        self.ctx.db.update_expense(record_id, Expense(
            property_id=int(record.get("property_id") or 0),
            date=record.get("date") or "",
            category=record.get("category") or "other",
            amount=record.get("amount") or 0.0,
            vendor=record.get("vendor") or "",
            description=record.get("description") or "",
            renovation_id=record.get("renovation_id"),
            receipt_path=str(stored),
            notes=record.get("notes") or "",
        ))
        self.after_change()

    def footer_text(self) -> str:
        currency = self.ctx.currency
        total = sum(r.get("amount") or 0 for r in self._records)
        by_category: dict[str, float] = {}
        for record in self._records:
            key = tr(f"expense_cat_{record.get('category')}")
            by_category[key] = by_category.get(key, 0.0) + (record.get("amount") or 0)
        top = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_text = " · ".join(f"{k}: {format_money(v, currency)}" for k, v in top)
        return f"{tr('total')}: {format_money(total, currency)}   |   {top_text}"
