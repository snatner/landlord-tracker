"""Pure business calculations.

Everything in this module is side-effect free and unit tested in
``tests/test_calculations.py``. The UI and the dashboard service only ever
consume these functions, so the numbers shown to a landlord are never
computed ad-hoc inside a widget.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Mapping, Optional

from ..models import RECURRENCE_STEPS, RentStatus

EPSILON = 1e-9


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def safe_div(numerator: float, denominator: float) -> Optional[float]:
    """Divide, returning ``None`` instead of raising/lying when denom is 0."""
    if denominator is None or abs(denominator) < EPSILON:
        return None
    return numerator / denominator


def to_float(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_date(value) -> Optional[_dt.date]:
    """Parse an ISO date, tolerating empty strings and junk."""
    if not value:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return _dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def month_key(value) -> str:
    """Return ``YYYY-MM`` for a date/datetime/ISO string, or '' if unusable."""
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m") if parsed else ""


def month_key_from_parts(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def month_label(period: str, locale: str = "en") -> str:
    """'2026-03' -> 'Mar 2026' (en) / 'mar 2026' (pt)."""
    try:
        year, month = period.split("-")
        date = _dt.date(int(year), int(month), 1)
    except (ValueError, AttributeError):
        return period
    names_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    names_pt = ["jan", "fev", "mar", "abr", "mai", "jun",
                "jul", "ago", "set", "out", "nov", "dez"]
    names = names_pt if locale.startswith("pt") else names_en
    return f"{names[date.month - 1]} {date.year}"


def month_sequence(start_period: str, end_period: str) -> list[str]:
    """Inclusive list of ``YYYY-MM`` keys between two periods."""
    start, end = _period_to_index(start_period), _period_to_index(end_period)
    if start is None or end is None or end < start:
        return []
    return [_index_to_period(i) for i in range(start, end + 1)]


def last_n_months(today: _dt.date, count: int) -> list[str]:
    """The last ``count`` months ending at ``today``, oldest first."""
    if count <= 0:
        return []
    index = today.year * 12 + (today.month - 1)
    return [_index_to_period(index - offset) for offset in range(count - 1, -1, -1)]


def _period_to_index(period: str) -> Optional[int]:
    try:
        year, month = period.split("-")
        return int(year) * 12 + (int(month) - 1)
    except (ValueError, AttributeError):
        return None


def _index_to_period(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def months_between(start: str, end: str) -> Optional[float]:
    """Calendar months between two ISO dates (fractional, month = 30.44 days)."""
    a, b = parse_date(start), parse_date(end)
    if a is None or b is None:
        return None
    return (b - a).days / 30.44


# --------------------------------------------------------------------------
# recurring expenses
# --------------------------------------------------------------------------
def as_flag(value) -> bool:
    """Truthiness for SQLite-ish flags ('0', 'False' and '' are false)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() not in ("", "0", "false", "False", "no")
    return bool(value)


def recurrence_step(frequency: str) -> int:
    """Months between charges for a frequency; unknown values act monthly."""
    return RECURRENCE_STEPS.get(str(frequency or "").strip().lower(), 1)


def recurring_due(template: Mapping, period: str) -> bool:
    """Should this recurring template produce an expense row for ``period``?

    A template fires when it is active, ``period`` is inside its
    ``start_month``..``end_month`` window, and the number of months since the
    start is an exact multiple of its frequency step. That makes the check
    deterministic: generating the same month twice can never double-charge.
    """
    if not as_flag(template.get("is_active", 1)):
        return False
    period_index = _period_to_index(period)
    if period_index is None:
        return False
    start_index = _period_to_index(str(template.get("start_month") or ""))
    if start_index is None:
        # No anchor month: treat the template as running for all time, which
        # keeps a simple monthly cost usable without extra setup.
        start_index = period_index
    if period_index < start_index:
        return False
    end_month = str(template.get("end_month") or "")
    if end_month:
        end_index = _period_to_index(end_month)
        if end_index is None or period_index > end_index:
            return False
    return (period_index - start_index) % recurrence_step(template.get("frequency")) == 0


def recurring_due_date(template: Mapping, period: str) -> str:
    """ISO due date for a template in a period, clamping to the month's length."""
    import calendar as _calendar

    try:
        year, month = (int(x) for x in str(period).split("-"))
    except (ValueError, AttributeError):
        return ""
    last_day = _calendar.monthrange(year, month)[1]
    day = int(to_float(template.get("day_of_month")) or 1)
    day = min(max(day, 1), last_day)
    return f"{period}-{day:02d}"


def recurring_monthly_equivalent(amount, frequency: str) -> Optional[float]:
    """Normalise any frequency to a per-month figure for a true cost total.

    Returns ``None`` when the amount is unusable, so the UI can show ``—``
    rather than a fake zero.
    """
    if amount is None or amount == "":
        return None
    value = to_float(amount)
    step = recurrence_step(frequency)
    if step <= 0:
        return None
    return value / step


def recurring_frequency_months(frequency: str) -> int:
    return recurrence_step(frequency)


def expense_total(rows: Iterable[Mapping]) -> float:
    return sum(to_float(r.get("amount")) for r in rows)


# --------------------------------------------------------------------------
# rent
# --------------------------------------------------------------------------
def compute_rent_status(
    due_amount: float,
    paid_amount: float,
    due_date=None,
    paid_date=None,
    today: Optional[_dt.date] = None,
) -> str:
    """Derive the rent status for one period.

    Rules (documented because they drive the dashboard donut chart):
    * fully paid -> PAID, whatever the date
    * partially paid, past due -> LATE
    * partially paid, not yet due -> PARTIAL
    * nothing paid, past due -> LATE
    * nothing paid, not yet due -> UNPAID
    """
    today = today or _dt.date.today()
    due_amount = to_float(due_amount)
    paid_amount = to_float(paid_amount)

    if due_amount > EPSILON and paid_amount + EPSILON >= due_amount:
        return RentStatus.PAID.value
    if due_amount <= EPSILON and paid_amount > EPSILON:
        return RentStatus.PAID.value

    overdue = False
    due = parse_date(due_date)
    if due is not None:
        overdue = today > due
    elif paid_date is None and due_amount > EPSILON:
        overdue = False

    if paid_amount > EPSILON:
        return RentStatus.LATE.value if overdue else RentStatus.PARTIAL.value
    return RentStatus.LATE.value if overdue else RentStatus.UNPAID.value


def rent_balance(due_amount: float, paid_amount: float) -> float:
    return round(to_float(due_amount) - to_float(paid_amount), 2)


def rent_collection_rate(collected: float, expected: float) -> Optional[float]:
    """Fraction 0..1+ of expected rent actually collected."""
    return safe_div(to_float(collected), to_float(expected))


def arrears(rows: Iterable[Mapping]) -> float:
    """Total unpaid balance across rent rows."""
    total = 0.0
    for row in rows:
        if row.get("status") in (RentStatus.PAID.value,):
            continue
        total += max(0.0, rent_balance(row.get("due_amount", 0), row.get("paid_amount", 0)))
    return round(total, 2)


# --------------------------------------------------------------------------
# property performance
# --------------------------------------------------------------------------
def net_cashflow(rent_collected: float, expenses: float) -> float:
    return round(to_float(rent_collected) - to_float(expenses), 2)


def gross_yield(annual_rent: float, property_value: float) -> Optional[float]:
    """Gross rental yield as a fraction (0.05 == 5%)."""
    return safe_div(to_float(annual_rent), to_float(property_value))


def net_yield(annual_rent: float, annual_costs: float, property_value: float) -> Optional[float]:
    return safe_div(to_float(annual_rent) - to_float(annual_costs), to_float(property_value))


def cash_on_cash(annual_net_income: float, cash_invested: float) -> Optional[float]:
    return safe_div(to_float(annual_net_income), to_float(cash_invested))


def total_return_percent(purchase_price: float, current_value: float) -> Optional[float]:
    """Simple capital appreciation on the purchase price."""
    base = to_float(purchase_price)
    if base <= EPSILON:
        return None
    return (to_float(current_value) - base) / base


def occupied_share(occupied: int, total: int) -> Optional[float]:
    return safe_div(occupied, total)


# --------------------------------------------------------------------------
# renovations / payback
# --------------------------------------------------------------------------
def renovation_payback_months(cost: float, expected_monthly_rent_increase: float) -> Optional[float]:
    """Months until a renovation pays for itself through higher rent.

    Returns ``None`` when there is no rent uplift — we never fabricate a
    payback number (Rodrigo's rule: no wishful math).
    """
    return safe_div(to_float(cost), to_float(expected_monthly_rent_increase))


def renovation_payback_years(cost: float, expected_monthly_rent_increase: float) -> Optional[float]:
    months = renovation_payback_months(cost, expected_monthly_rent_increase)
    return None if months is None else months / 12


def value_uplift_roi(cost: float, expected_value_increase: float) -> Optional[float]:
    """Return on a renovation measured against value created instead of rent."""
    return safe_div(to_float(expected_value_increase) - to_float(cost), to_float(cost))


def renovation_variance(budget: float, actual: float) -> float:
    """Positive == over budget."""
    return round(to_float(actual) - to_float(budget), 2)


def renovation_variance_percent(budget: float, actual: float) -> Optional[float]:
    return safe_div(to_float(actual) - to_float(budget), to_float(budget))


def renovation_actual_cost(linked_expenses: Iterable[float]) -> float:
    """Actual spend = the sum of expenses tagged to this renovation.

    Starts at €0 and only ever reflects money that was really spent. It must not
    fall back to the budget: a job with nothing logged yet has cost nothing, and
    substituting the estimate invents a payment that never happened. Callers that
    want a comparison should render "no spending logged yet" instead of a number.
    """
    return round(sum(to_float(v) for v in linked_expenses), 2)


# --------------------------------------------------------------------------
# aggregation helpers
# --------------------------------------------------------------------------
def group_sum(rows: Iterable[Mapping], key: str, value: str) -> dict[str, float]:
    """Sum ``value`` grouped by ``key`` (missing/blank key -> 'other')."""
    out: dict[str, float] = {}
    for row in rows:
        bucket = row.get(key) or "other"
        out[bucket] = out.get(bucket, 0.0) + to_float(row.get(value))
    return {k: round(v, 2) for k, v in out.items()}


def percentage_share(part: float, whole: float) -> Optional[float]:
    return safe_div(to_float(part), to_float(whole))


def annualise_monthly(monthly: float) -> float:
    return round(to_float(monthly) * 12, 2)


def trailing_average(values: Iterable[float]) -> Optional[float]:
    data = [to_float(v) for v in values]
    if not data:
        return None
    return round(sum(data) / len(data), 2)


def rent_roll_total(leases: Iterable[Mapping]) -> float:
    return round(sum(to_float(l.get("monthly_rent")) for l in leases if l.get("status") != "ended"), 2)
