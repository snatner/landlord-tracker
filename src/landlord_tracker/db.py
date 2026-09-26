"""Local SQLite storage.

Privacy contract implemented here:
* the database is a plain file on the user's own disk (``~/.local/share/...``)
* no network, no ORM telemetry, no cloud sync
* WAL mode so an unexpected shutdown never corrupts the ledger
* automatic timestamped backups into ``<data>/backups`` (local, user owned)
"""

from __future__ import annotations

import datetime as _dt
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from .models import (
    Document,
    Expense,
    Lease,
    Property,
    RecurringExpense,
    Renovation,
    RentPayment,
    Tenant,
)

SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    address             TEXT DEFAULT '',
    city                TEXT DEFAULT '',
    postcode            TEXT DEFAULT '',
    property_type       TEXT DEFAULT '',
    purchase_price      REAL DEFAULT 0,
    purchase_date       TEXT DEFAULT '',
    current_value       REAL DEFAULT 0,
    monthly_fixed_costs REAL DEFAULT 0,
    size_m2             REAL DEFAULT 0,
    notes               TEXT DEFAULT '',
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT '',
    updated_at          TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tenants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id       INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    full_name         TEXT NOT NULL,
    phone             TEXT DEFAULT '',
    email             TEXT DEFAULT '',
    tax_number        TEXT DEFAULT '',
    emergency_contact TEXT DEFAULT '',
    notes             TEXT DEFAULT '',
    is_active         INTEGER DEFAULT 1,
    created_at        TEXT DEFAULT '',
    updated_at        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS leases (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id        INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    tenant_id          INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    start_date         TEXT DEFAULT '',
    end_date           TEXT DEFAULT '',
    monthly_rent       REAL DEFAULT 0,
    deposit_amount     REAL DEFAULT 0,
    due_day            INTEGER DEFAULT 1,
    last_increase_date TEXT DEFAULT '',
    status             TEXT DEFAULT 'active',
    notes              TEXT DEFAULT '',
    created_at         TEXT DEFAULT '',
    updated_at         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rent_payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id     INTEGER REFERENCES leases(id) ON DELETE CASCADE,
    property_id  INTEGER REFERENCES properties(id) ON DELETE CASCADE,
    tenant_id    INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    period       TEXT NOT NULL,
    due_amount   REAL DEFAULT 0,
    due_date     TEXT DEFAULT '',
    paid_amount  REAL DEFAULT 0,
    paid_date    TEXT DEFAULT '',
    status       TEXT DEFAULT 'unpaid',
    method       TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    created_at   TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_rent_period ON rent_payments(period);
CREATE INDEX IF NOT EXISTS idx_rent_property ON rent_payments(property_id);

CREATE TABLE IF NOT EXISTS expenses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id   INTEGER REFERENCES properties(id) ON DELETE CASCADE,
    renovation_id INTEGER REFERENCES renovations(id) ON DELETE SET NULL,
    recurring_id  INTEGER REFERENCES recurring_expenses(id) ON DELETE SET NULL,
    period        TEXT DEFAULT '',
    date          TEXT DEFAULT '',
    category      TEXT DEFAULT 'other',
    amount        REAL DEFAULT 0,
    vendor        TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    receipt_path  TEXT DEFAULT '',
    notes         TEXT DEFAULT '',
    created_at    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_expense_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_expense_property ON expenses(property_id);

-- Recurring cost templates (condo fee, insurance, IMI). Rows here are plans,
-- not money spent; "generate month" copies a template into `expenses` once per
-- period, and the (recurring_id, period) pair makes that idempotent.
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id   INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    category      TEXT DEFAULT 'other',
    amount        REAL DEFAULT 0,
    vendor        TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    frequency     TEXT DEFAULT 'monthly',
    day_of_month  INTEGER DEFAULT 1,
    start_month   TEXT DEFAULT '',
    end_month     TEXT DEFAULT '',
    is_active     INTEGER DEFAULT 1,
    notes         TEXT DEFAULT '',
    created_at    TEXT DEFAULT '',
    updated_at    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_recurring_property ON recurring_expenses(property_id);

CREATE TABLE IF NOT EXISTS renovations (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id                   INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    title                         TEXT NOT NULL,
    category                      TEXT DEFAULT 'other',
    status                        TEXT DEFAULT 'planned',
    start_date                    TEXT DEFAULT '',
    end_date                      TEXT DEFAULT '',
    budget                        REAL DEFAULT 0,
    expected_monthly_rent_increase REAL DEFAULT 0,
    expected_value_increase       REAL DEFAULT 0,
    contractor                    TEXT DEFAULT '',
    notes                         TEXT DEFAULT '',
    created_at                    TEXT DEFAULT '',
    updated_at                    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    related_type TEXT DEFAULT '',
    related_id   INTEGER,
    file_path    TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    created_at   TEXT DEFAULT ''
);
"""


def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def default_data_dir() -> Path:
    """XDG data dir, honouring ``LANDLORD_TRACKER_DATA`` for tests/portable use."""
    import os

    override = os.environ.get("LANDLORD_TRACKER_DATA")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "landlord-tracker"


class Database:
    """Thin, explicit SQLite wrapper. One row = one dict, no ORM magic."""

    def __init__(self, path: Optional[Path] = None, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = self.data_dir / "documents"
        self.backups_dir = self.data_dir / "backups"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.path = Path(path) if path else self.data_dir / "landlord.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    # -- schema ---------------------------------------------------------
    def _create_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.execute(
            "INSERT INTO schema_info(key, value) VALUES('version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def _table_columns(self, table: str) -> set[str]:
        return {r["name"] for r in self.query(f"PRAGMA table_info({table})")}

    def _migrate(self) -> None:
        """Bring an existing database up to the current schema.

        ``CREATE TABLE IF NOT EXISTS`` never adds columns to a database that
        already exists, so every column added after v1 needs an explicit ALTER
        here. Older databases must keep working untouched apart from this.
        """
        expense_columns = self._table_columns("expenses")
        if "recurring_id" not in expense_columns:
            self.execute(
                "ALTER TABLE expenses ADD COLUMN recurring_id INTEGER "
                "REFERENCES recurring_expenses(id) ON DELETE SET NULL"
            )
        if "period" not in expense_columns:
            self.execute("ALTER TABLE expenses ADD COLUMN period TEXT DEFAULT ''")
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_recurring "
            "ON expenses(recurring_id, period)"
        )

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.close()
        except sqlite3.Error:  # pragma: no cover
            pass

    # -- generic helpers ------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        cur = self.conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def _insert(self, table: str, data: dict) -> int:
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _update(self, table: str, row_id: int, data: dict) -> None:
        assignments = ", ".join(f"{col} = ?" for col in data)
        self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            (*data.values(), row_id),
        )
        self.conn.commit()

    # -- settings -------------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.query_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def all_settings(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.query("SELECT key, value FROM settings")}

    # -- counters -------------------------------------------------------
    def count(self, table: str) -> int:
        row = self.query_one(f"SELECT COUNT(*) AS n FROM {table}")
        return int(row["n"]) if row else 0

    def is_empty(self) -> bool:
        return all(
            self.count(t) == 0
            for t in ("properties", "tenants", "leases", "rent_payments",
                      "expenses", "recurring_expenses", "renovations", "documents")
        )

    # -- properties -----------------------------------------------------
    def add_property(self, prop: Property) -> int:
        data = {
            "name": prop.name,
            "address": prop.address,
            "city": prop.city,
            "postcode": prop.postcode,
            "property_type": prop.property_type,
            "purchase_price": prop.purchase_price,
            "purchase_date": prop.purchase_date,
            "current_value": prop.current_value,
            "monthly_fixed_costs": prop.monthly_fixed_costs,
            "size_m2": prop.size_m2,
            "notes": prop.notes,
            "is_active": prop.is_active,
            "created_at": prop.created_at or now_iso(),
            "updated_at": now_iso(),
        }
        return self._insert("properties", data)

    def update_property(self, prop_id: int, prop: Property) -> None:
        self._update(
            "properties",
            prop_id,
            {
                "name": prop.name,
                "address": prop.address,
                "city": prop.city,
                "postcode": prop.postcode,
                "property_type": prop.property_type,
                "purchase_price": prop.purchase_price,
                "purchase_date": prop.purchase_date,
                "current_value": prop.current_value,
                "monthly_fixed_costs": prop.monthly_fixed_costs,
                "size_m2": prop.size_m2,
                "notes": prop.notes,
                "is_active": prop.is_active,
                "updated_at": now_iso(),
            },
        )

    def delete_property(self, prop_id: int) -> None:
        self.execute("DELETE FROM properties WHERE id = ?", (prop_id,))

    def properties(self, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT * FROM properties"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self.query(sql + " ORDER BY name COLLATE NOCASE")

    def property(self, prop_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM properties WHERE id = ?", (prop_id,))

    # -- tenants --------------------------------------------------------
    def add_tenant(self, tenant: Tenant) -> int:
        return self._insert(
            "tenants",
            {
                "property_id": tenant.property_id,
                "full_name": tenant.full_name,
                "phone": tenant.phone,
                "email": tenant.email,
                "tax_number": tenant.tax_number,
                "emergency_contact": tenant.emergency_contact,
                "notes": tenant.notes,
                "is_active": tenant.is_active,
                "created_at": tenant.created_at or now_iso(),
                "updated_at": now_iso(),
            },
        )

    def update_tenant(self, tenant_id: int, tenant: Tenant) -> None:
        self._update(
            "tenants",
            tenant_id,
            {
                "property_id": tenant.property_id,
                "full_name": tenant.full_name,
                "phone": tenant.phone,
                "email": tenant.email,
                "tax_number": tenant.tax_number,
                "emergency_contact": tenant.emergency_contact,
                "notes": tenant.notes,
                "is_active": tenant.is_active,
                "updated_at": now_iso(),
            },
        )

    def delete_tenant(self, tenant_id: int) -> None:
        self.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))

    def tenants(self, include_inactive: bool = True) -> list[dict]:
        sql = (
            "SELECT t.*, p.name AS property_name FROM tenants t "
            "LEFT JOIN properties p ON p.id = t.property_id"
        )
        if not include_inactive:
            sql += " WHERE t.is_active = 1"
        return self.query(sql + " ORDER BY t.full_name COLLATE NOCASE")

    def tenant(self, tenant_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM tenants WHERE id = ?", (tenant_id,))

    # -- leases ---------------------------------------------------------
    def add_lease(self, lease: Lease) -> int:
        return self._insert(
            "leases",
            {
                "property_id": lease.property_id,
                "tenant_id": lease.tenant_id,
                "start_date": lease.start_date,
                "end_date": lease.end_date,
                "monthly_rent": lease.monthly_rent,
                "deposit_amount": lease.deposit_amount,
                "due_day": lease.due_day,
                "last_increase_date": lease.last_increase_date,
                "status": lease.status,
                "notes": lease.notes,
                "created_at": lease.created_at or now_iso(),
                "updated_at": now_iso(),
            },
        )

    def update_lease(self, lease_id: int, lease: Lease) -> None:
        self._update(
            "leases",
            lease_id,
            {
                "property_id": lease.property_id,
                "tenant_id": lease.tenant_id,
                "start_date": lease.start_date,
                "end_date": lease.end_date,
                "monthly_rent": lease.monthly_rent,
                "deposit_amount": lease.deposit_amount,
                "due_day": lease.due_day,
                "last_increase_date": lease.last_increase_date,
                "status": lease.status,
                "notes": lease.notes,
                "updated_at": now_iso(),
            },
        )

    def delete_lease(self, lease_id: int) -> None:
        self.execute("DELETE FROM leases WHERE id = ?", (lease_id,))

    def leases(self, include_ended: bool = True) -> list[dict]:
        sql = (
            "SELECT l.*, p.name AS property_name, t.full_name AS tenant_name "
            "FROM leases l "
            "LEFT JOIN properties p ON p.id = l.property_id "
            "LEFT JOIN tenants t ON t.id = l.tenant_id"
        )
        if not include_ended:
            sql += " WHERE l.status != 'ended'"
        return self.query(sql + " ORDER BY l.start_date DESC")

    def lease(self, lease_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM leases WHERE id = ?", (lease_id,))

    def active_leases(self) -> list[dict]:
        return self.query(
            "SELECT l.*, p.name AS property_name, t.full_name AS tenant_name "
            "FROM leases l "
            "LEFT JOIN properties p ON p.id = l.property_id "
            "LEFT JOIN tenants t ON t.id = l.tenant_id "
            "WHERE l.status != 'ended' ORDER BY p.name COLLATE NOCASE"
        )

    # -- rent -----------------------------------------------------------
    def add_rent(self, rent: RentPayment) -> int:
        return self._insert(
            "rent_payments",
            {
                "lease_id": rent.lease_id,
                "property_id": rent.property_id,
                "tenant_id": rent.tenant_id,
                "period": rent.period,
                "due_amount": rent.due_amount,
                "due_date": rent.due_date,
                "paid_amount": rent.paid_amount,
                "paid_date": rent.paid_date,
                "status": rent.status,
                "method": rent.method,
                "notes": rent.notes,
                "created_at": rent.created_at or now_iso(),
            },
        )

    def set_rent_status(self, rent_id: int, status: str) -> None:
        self._update("rent_payments", rent_id, {"status": status})

    def update_rent(self, rent_id: int, rent: RentPayment) -> None:
        self._update(
            "rent_payments",
            rent_id,
            {
                "lease_id": rent.lease_id,
                "property_id": rent.property_id,
                "tenant_id": rent.tenant_id,
                "period": rent.period,
                "due_amount": rent.due_amount,
                "due_date": rent.due_date,
                "paid_amount": rent.paid_amount,
                "paid_date": rent.paid_date,
                "status": rent.status,
                "method": rent.method,
                "notes": rent.notes,
            },
        )

    def delete_rent(self, rent_id: int) -> None:
        self.execute("DELETE FROM rent_payments WHERE id = ?", (rent_id,))

    def rent_payments(self, period: Optional[str] = None) -> list[dict]:
        sql = (
            "SELECT r.*, p.name AS property_name, t.full_name AS tenant_name "
            "FROM rent_payments r "
            "LEFT JOIN properties p ON p.id = r.property_id "
            "LEFT JOIN tenants t ON t.id = r.tenant_id "
        )
        params: tuple = ()
        if period:
            sql += "WHERE r.period = ? "
            params = (period,)
        return self.query(sql + "ORDER BY r.period DESC, p.name COLLATE NOCASE", params)

    def rent_periods(self) -> list[str]:
        return [r["period"] for r in self.query(
            "SELECT DISTINCT period FROM rent_payments ORDER BY period DESC"
        )]

    def rent_exists(self, lease_id: int, period: str) -> Optional[dict]:
        return self.query_one(
            "SELECT * FROM rent_payments WHERE lease_id = ? AND period = ?",
            (lease_id, period),
        )

    # -- expenses -------------------------------------------------------
    def add_expense(self, expense: Expense) -> int:
        return self._insert(
            "expenses",
            {
                "property_id": expense.property_id,
                "renovation_id": expense.renovation_id,
                "recurring_id": expense.recurring_id,
                "period": expense.period,
                "date": expense.date,
                "category": expense.category,
                "amount": expense.amount,
                "vendor": expense.vendor,
                "description": expense.description,
                "receipt_path": expense.receipt_path,
                "notes": expense.notes,
                "created_at": expense.created_at or now_iso(),
            },
        )

    def update_expense(self, expense_id: int, expense: Expense) -> None:
        self._update(
            "expenses",
            expense_id,
            {
                "property_id": expense.property_id,
                "renovation_id": expense.renovation_id,
                "recurring_id": expense.recurring_id,
                "period": expense.period,
                "date": expense.date,
                "category": expense.category,
                "amount": expense.amount,
                "vendor": expense.vendor,
                "description": expense.description,
                "receipt_path": expense.receipt_path,
                "notes": expense.notes,
            },
        )

    def delete_expense(self, expense_id: int) -> None:
        self.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    def expenses(self, start_date: str = "", end_date: str = "") -> list[dict]:
        sql = (
            "SELECT e.*, p.name AS property_name, r.title AS renovation_title "
            "FROM expenses e "
            "LEFT JOIN properties p ON p.id = e.property_id "
            "LEFT JOIN renovations r ON r.id = e.renovation_id "
        )
        clauses, params = [], []
        if start_date:
            clauses.append("e.date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("e.date <= ?")
            params.append(end_date)
        if clauses:
            sql += "WHERE " + " AND ".join(clauses) + " "
        return self.query(sql + "ORDER BY e.date DESC, e.id DESC", tuple(params))

    # -- recurring expenses ---------------------------------------------
    def add_recurring_expense(self, template: RecurringExpense) -> int:
        return self._insert(
            "recurring_expenses",
            {
                "property_id": template.property_id,
                "category": template.category,
                "amount": template.amount,
                "vendor": template.vendor,
                "description": template.description,
                "frequency": template.frequency,
                "day_of_month": template.day_of_month,
                "start_month": template.start_month,
                "end_month": template.end_month,
                "is_active": template.is_active,
                "notes": template.notes,
                "created_at": template.created_at or now_iso(),
                "updated_at": now_iso(),
            },
        )

    def update_recurring_expense(self, template_id: int, template: RecurringExpense) -> None:
        self._update(
            "recurring_expenses",
            template_id,
            {
                "property_id": template.property_id,
                "category": template.category,
                "amount": template.amount,
                "vendor": template.vendor,
                "description": template.description,
                "frequency": template.frequency,
                "day_of_month": template.day_of_month,
                "start_month": template.start_month,
                "end_month": template.end_month,
                "is_active": template.is_active,
                "notes": template.notes,
                "updated_at": now_iso(),
            },
        )

    def delete_recurring_expense(self, template_id: int) -> None:
        """Delete a template. Generated expense rows are kept as history."""
        self.execute("DELETE FROM recurring_expenses WHERE id = ?", (template_id,))

    def recurring_expenses(self, active_only: bool = False) -> list[dict]:
        sql = (
            "SELECT r.*, p.name AS property_name "
            "FROM recurring_expenses r "
            "LEFT JOIN properties p ON p.id = r.property_id "
        )
        if active_only:
            sql += "WHERE r.is_active = 1 "
        return self.query(sql + "ORDER BY p.name COLLATE NOCASE, r.category, r.id")

    def recurring_expense(self, template_id: int) -> Optional[dict]:
        return self.query_one(
            "SELECT * FROM recurring_expenses WHERE id = ?", (template_id,)
        )

    def recurring_expense_exists(self, template_id: int, period: str) -> Optional[dict]:
        """The idempotency check for "generate month" — one row per period."""
        return self.query_one(
            "SELECT * FROM expenses WHERE recurring_id = ? AND period = ?",
            (template_id, period),
        )

    def expenses_for_period(self, period: str) -> list[dict]:
        return self.query(
            "SELECT * FROM expenses e WHERE e.period = ? OR e.date LIKE ?",
            (period, f"{period}%"),
        )

    # -- renovations ----------------------------------------------------
    def add_renovation(self, reno: Renovation) -> int:
        return self._insert(
            "renovations",
            {
                "property_id": reno.property_id,
                "title": reno.title,
                "category": reno.category,
                "status": reno.status,
                "start_date": reno.start_date,
                "end_date": reno.end_date,
                "budget": reno.budget,
                "expected_monthly_rent_increase": reno.expected_monthly_rent_increase,
                "expected_value_increase": reno.expected_value_increase,
                "contractor": reno.contractor,
                "notes": reno.notes,
                "created_at": reno.created_at or now_iso(),
                "updated_at": now_iso(),
            },
        )

    def update_renovation(self, reno_id: int, reno: Renovation) -> None:
        self._update(
            "renovations",
            reno_id,
            {
                "property_id": reno.property_id,
                "title": reno.title,
                "category": reno.category,
                "status": reno.status,
                "start_date": reno.start_date,
                "end_date": reno.end_date,
                "budget": reno.budget,
                "expected_monthly_rent_increase": reno.expected_monthly_rent_increase,
                "expected_value_increase": reno.expected_value_increase,
                "contractor": reno.contractor,
                "notes": reno.notes,
                "updated_at": now_iso(),
            },
        )

    def delete_renovation(self, reno_id: int) -> None:
        self.execute("DELETE FROM renovations WHERE id = ?", (reno_id,))

    def renovations(self) -> list[dict]:
        return self.query(
            "SELECT r.*, p.name AS property_name, "
            "COALESCE((SELECT SUM(e.amount) FROM expenses e WHERE e.renovation_id = r.id), 0) "
            "AS logged_cost, "
            # The visible link between a job and the expense rows that fund it.
            "COALESCE((SELECT COUNT(*) FROM expenses e WHERE e.renovation_id = r.id), 0) "
            "AS payment_count "
            "FROM renovations r "
            "LEFT JOIN properties p ON p.id = r.property_id "
            "ORDER BY r.start_date DESC, r.id DESC"
        )

    def renovation(self, reno_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM renovations WHERE id = ?", (reno_id,))

    # -- documents ------------------------------------------------------
    def add_document(self, doc: Document) -> int:
        return self._insert(
            "documents",
            {
                "title": doc.title,
                "related_type": doc.related_type,
                "related_id": doc.related_id,
                "file_path": doc.file_path,
                "notes": doc.notes,
                "created_at": doc.created_at or now_iso(),
            },
        )

    def delete_document(self, doc_id: int) -> None:
        self.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def documents(self) -> list[dict]:
        return self.query("SELECT * FROM documents ORDER BY created_at DESC, id DESC")

    def document_counts_by_property(self) -> dict[int, int]:
        rows = self.query(
            "SELECT related_id, COUNT(*) AS n FROM documents "
            "WHERE related_type = 'property' GROUP BY related_id"
        )
        return {int(r["related_id"]): int(r["n"]) for r in rows if r["related_id"]}

    # -- maintenance ----------------------------------------------------
    def vacuum(self) -> None:
        self.conn.execute("VACUUM")
        self.conn.commit()

    def integrity_check(self) -> str:
        row = self.query_one("PRAGMA integrity_check")
        return list(row.values())[0] if row else "unknown"

    # -- backups --------------------------------------------------------
    def backup_to(self, destination: Optional[Path] = None) -> Path:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        if destination is None:
            destination = self.backups_dir / f"landlord-{stamp}.db"
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.conn.commit()
        target = sqlite3.connect(str(destination))
        with target:
            self.conn.backup(target)
        target.close()
        return destination

    def list_backups(self) -> list[Path]:
        return sorted(self.backups_dir.glob("*.db"), reverse=True)

    def prune_backups(self, keep: int = 20) -> int:
        backups = self.list_backups()
        removed = 0
        for path in backups[keep:]:
            try:
                path.unlink()
                removed += 1
            except OSError:  # pragma: no cover
                pass
        return removed

    def copy_document_into_vault(self, source: Path, subfolder: str = "") -> Path:
        """Copy an external file into the local document vault (never move)."""
        source = Path(source)
        target_dir = self.documents_dir / subfolder if subfolder else self.documents_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        counter = 1
        while target.exists():
            target = target_dir / f"{source.stem}-{counter}{source.suffix}"
            counter += 1
        shutil.copy2(source, target)
        return target

    def export_rows(self) -> dict[str, list[dict]]:
        """Everything needed by the XLSX export and by full-data backups."""
        return {
            "Properties": self.properties(),
            "Tenants": self.tenants(),
            "Leases": self.leases(),
            "Rent": self.rent_payments(),
            "Expenses": self.expenses(),
            "Recurring": self.recurring_expenses(),
            "Renovations": self.renovations(),
            "Documents": self.documents(),
        }

    def wipe(self, tables: Iterable[str]) -> None:
        """Used by the demo-data loader only."""
        for table in tables:
            self.execute(f"DELETE FROM {table}")
