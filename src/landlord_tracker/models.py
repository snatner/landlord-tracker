"""Domain models: enums + lightweight dataclasses.

Canonical keys are stored in SQLite (never translated text), so the database
stays language-independent and the UI can switch language at any time.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class StrEnum(str, enum.Enum):
    """str-based enum so values round-trip cleanly through SQLite."""

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.value


class RentStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    LATE = "late"


class LeaseStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class RenovationStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ExpenseCategory(StrEnum):
    MORTGAGE = "mortgage"
    CONDO = "condo"
    INSURANCE = "insurance"
    PROPERTY_TAX = "property_tax"
    UTILITIES = "utilities"
    REPAIR = "repair"
    MAINTENANCE = "maintenance"
    MANAGEMENT_FEE = "management_fee"
    LEGAL = "legal"
    OTHER = "other"


class RecurrenceFrequency(StrEnum):
    """How often a recurring template fires, in months."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


# Months between two consecutive charges. Single source of truth for both the
# due-date maths and the monthly-equivalent roll-up.
RECURRENCE_STEPS: dict[str, int] = {
    RecurrenceFrequency.MONTHLY.value: 1,
    RecurrenceFrequency.QUARTERLY.value: 3,
    RecurrenceFrequency.SEMIANNUAL.value: 6,
    RecurrenceFrequency.ANNUAL.value: 12,
}


class RenovationCategory(StrEnum):
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"
    PAINTING = "painting"
    FLOORING = "flooring"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    WINDOWS_DOORS = "windows_doors"
    ROOF = "roof"
    EXTERIOR = "exterior"
    INSULATION = "insulation"
    OTHER = "other"


class DocumentLink(StrEnum):
    PROPERTY = "property"
    TENANT = "tenant"
    LEASE = "lease"
    EXPENSE = "expense"
    RENOVATION = "renovation"


EXPENSE_CATEGORIES = [c.value for c in ExpenseCategory]
RENOVATION_CATEGORIES = [c.value for c in RenovationCategory]
RENT_STATUSES = [s.value for s in RentStatus]
RENOVATION_STATUSES = [s.value for s in RenovationStatus]
RECURRENCE_FREQUENCIES = [f.value for f in RecurrenceFrequency]


@dataclass
class Property:
    name: str
    id: Optional[int] = None
    address: str = ""
    city: str = ""
    postcode: str = ""
    property_type: str = ""
    purchase_price: float = 0.0
    purchase_date: str = ""
    current_value: float = 0.0
    monthly_fixed_costs: float = 0.0
    size_m2: float = 0.0
    notes: str = ""
    is_active: int = 1
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Tenant:
    full_name: str
    id: Optional[int] = None
    property_id: Optional[int] = None
    phone: str = ""
    email: str = ""
    tax_number: str = ""
    emergency_contact: str = ""
    notes: str = ""
    is_active: int = 1
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Lease:
    property_id: int
    tenant_id: int
    start_date: str
    id: Optional[int] = None
    end_date: str = ""
    monthly_rent: float = 0.0
    deposit_amount: float = 0.0
    due_day: int = 1
    last_increase_date: str = ""
    status: str = LeaseStatus.ACTIVE.value
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RentPayment:
    lease_id: int
    property_id: int
    tenant_id: int
    period: str  # YYYY-MM
    due_amount: float = 0.0
    id: Optional[int] = None
    due_date: str = ""
    paid_amount: float = 0.0
    paid_date: str = ""
    status: str = RentStatus.UNPAID.value
    method: str = ""
    notes: str = ""
    created_at: str = ""


@dataclass
class Expense:
    property_id: int
    date: str
    category: str
    amount: float
    id: Optional[int] = None
    vendor: str = ""
    description: str = ""
    renovation_id: Optional[int] = None
    receipt_path: str = ""
    notes: str = ""
    # Provenance for rows created by "generate month" from a recurring template.
    # ``period`` is the YYYY-MM the row belongs to; both stay empty for manual rows.
    recurring_id: Optional[int] = None
    period: str = ""
    created_at: str = ""


@dataclass
class RecurringExpense:
    """A reusable cost template (condo fee, insurance, IMI) that can be
    materialised into real expense rows one month at a time."""

    property_id: int
    category: str
    amount: float
    id: Optional[int] = None
    vendor: str = ""
    description: str = ""
    frequency: str = RecurrenceFrequency.MONTHLY.value
    day_of_month: int = 1
    start_month: str = ""      # YYYY-MM; empty -> "since the beginning of time"
    end_month: str = ""        # YYYY-MM; empty -> still running
    is_active: int = 1
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Renovation:
    property_id: int
    title: str
    id: Optional[int] = None
    category: str = RenovationCategory.OTHER.value
    status: str = RenovationStatus.PLANNED.value
    start_date: str = ""
    end_date: str = ""
    budget: float = 0.0
    expected_monthly_rent_increase: float = 0.0
    expected_value_increase: float = 0.0
    contractor: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Document:
    title: str
    related_type: str
    id: Optional[int] = None
    related_id: Optional[int] = None
    file_path: str = ""
    notes: str = ""
    created_at: str = ""


@dataclass
class UnitSummary:
    """Aggregated numbers for one property (used by dashboard + tables)."""

    property_id: int
    name: str
    current_value: float = 0.0
    purchase_price: float = 0.0
    rent_expected: float = 0.0
    rent_collected: float = 0.0
    expenses: float = 0.0
    renovation_invested: float = 0.0
    occupied: bool = False
    net_cashflow: float = 0.0
    extras: dict = field(default_factory=dict)
