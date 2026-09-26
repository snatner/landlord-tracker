"""Dashboard aggregation.

Turns raw SQLite rows into the KPI numbers and chart series the dashboard
renders. Kept separate from the UI so the numbers can be unit tested without
a display server.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

from ..db import Database
from . import calculations as calc


@dataclass
class Kpi:
    key: str
    value: Optional[float]
    kind: str = "money"  # money | count | percent | months


@dataclass
class ChartSeries:
    key: str
    labels: list[str]
    values: list[float]
    series: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class RenovationRow:
    title: str
    property_name: str
    status: str
    budget: float
    actual: float
    variance: float
    monthly_uplift: float
    payback_months: Optional[float]
    value_uplift: float


@dataclass
class DashboardData:
    kpis: list[Kpi] = field(default_factory=list)
    charts: dict[str, ChartSeries] = field(default_factory=dict)
    renovations: list[RenovationRow] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    month: str = ""

    def kpi(self, key: str) -> Optional[float]:
        for item in self.kpis:
            if item.key == key:
                return item.value
        return None


def _month_bounds(period: str) -> tuple[str, str]:
    """First and last ISO date of a ``YYYY-MM`` month."""
    year, month = (int(x) for x in period.split("-"))
    first = _dt.date(year, month, 1)
    last = (_dt.date(year + (month == 12), (month % 12) + 1, 1) - _dt.timedelta(days=1))
    return first.isoformat(), last.isoformat()


def build_dashboard(
    db: Database,
    today: Optional[_dt.date] = None,
    months: int = 12,
    property_id: Optional[int] = None,
) -> DashboardData:
    """Compute the whole dashboard for the current month."""
    today = today or _dt.date.today()
    current_period = today.strftime("%Y-%m")
    data = DashboardData(month=current_period)

    properties = db.properties(include_inactive=False)
    if property_id:
        properties = [p for p in properties if p["id"] == property_id]
    prop_ids = {p["id"] for p in properties}

    leases = [l for l in db.active_leases() if not prop_ids or l["property_id"] in prop_ids]
    tenants = [t for t in db.tenants(include_inactive=False)
               if not prop_ids or t["property_id"] in prop_ids]

    period_start, period_end = _month_bounds(current_period)
    month_rent = [r for r in db.rent_payments(current_period)
                  if not prop_ids or r["property_id"] in prop_ids]
    month_expenses = [e for e in db.expenses(period_start, period_end)
                      if not prop_ids or e["property_id"] in prop_ids]

    rent_expected = round(sum(calc.to_float(r["due_amount"]) for r in month_rent), 2)
    rent_collected = round(sum(calc.to_float(r["paid_amount"]) for r in month_rent), 2)
    expense_total = round(sum(calc.to_float(e["amount"]) for e in month_expenses), 2)
    if rent_expected <= calc.EPSILON:
        # No ledger rows yet for this month: fall back to contracted rent roll.
        rent_expected = calc.rent_roll_total(leases)
    arrears_total = calc.arrears(month_rent)
    monthly_fixed = round(sum(calc.to_float(p["monthly_fixed_costs"]) for p in properties), 2)
    net_month = calc.net_cashflow(rent_collected or rent_expected, expense_total + monthly_fixed)

    portfolio_value = round(sum(calc.to_float(p["current_value"]) for p in properties), 2)
    purchase_total = round(sum(calc.to_float(p["purchase_price"]) for p in properties), 2)
    renovation_invested = round(
        sum(int(r["logged_cost"] or 0) for r in _filter_renovations(db, prop_ids)), 2
    )

    collection_rate = calc.rent_collection_rate(rent_collected, rent_expected)
    occupied = len(leases)
    total_units = len(properties)

    data.kpis = [
        Kpi("properties", float(total_units), "count"),
        Kpi("active_tenants", float(len(tenants)), "count"),
        Kpi("occupancy", calc.occupied_share(occupied, total_units), "percent"),
        Kpi("rent_expected", rent_expected, "money"),
        Kpi("rent_collected", rent_collected, "money"),
        Kpi("rent_collection_rate", collection_rate, "percent"),
        Kpi("arrears", arrears_total, "money"),
        Kpi("monthly_expenses", round(expense_total + monthly_fixed, 2), "money"),
        Kpi("net_cashflow", net_month, "money"),
        Kpi("portfolio_value", portfolio_value, "money"),
        Kpi("purchase_total", purchase_total, "money"),
        Kpi("capital_gain", round(portfolio_value - purchase_total, 2), "money"),
        Kpi("capital_gain_pct", calc.total_return_percent(purchase_total, portfolio_value), "percent"),
        Kpi("renovation_invested", renovation_invested, "money"),
        Kpi("annual_rent_roll", calc.annualise_monthly(calc.rent_roll_total(leases)), "money"),
        Kpi("gross_yield", calc.gross_yield(
            calc.annualise_monthly(calc.rent_roll_total(leases)), portfolio_value), "percent"),
    ]

    data.charts["portfolio_value"] = ChartSeries(
        key="portfolio_value",
        labels=[p["name"] for p in properties],
        values=[calc.to_float(p["current_value"]) for p in properties],
    )
    data.charts["purchase_vs_value"] = ChartSeries(
        key="purchase_vs_value",
        labels=[p["name"] for p in properties],
        values=[],
        series={
            "purchase": [calc.to_float(p["purchase_price"]) for p in properties],
            "current": [calc.to_float(p["current_value"]) for p in properties],
        },
    )
    data.charts["cashflow"] = _cashflow_series(db, today, months, prop_ids)
    data.charts["rent_status"] = _rent_status_series(month_rent)
    data.charts["expenses_by_category"] = _expense_category_series(month_expenses)
    data.charts["property_ranking"] = _ranking_series(db, properties, leases, today, months)

    data.renovations = _renovation_rows(db, prop_ids)
    data.alerts = _alerts(db, prop_ids, today, month_rent, properties)
    return data


def _filter_renovations(db: Database, prop_ids: set[int]) -> list[dict]:
    rows = db.renovations()
    if prop_ids:
        rows = [r for r in rows if r["property_id"] in prop_ids]
    return rows


def _cashflow_series(db: Database, today: _dt.date, months: int, prop_ids: set[int]) -> ChartSeries:
    """Rent collected vs expenses vs net for the last N months."""
    periods = calc.last_n_months(today, months)
    rent_all = [r for r in db.rent_payments() if not prop_ids or r["property_id"] in prop_ids]
    expenses_all = [e for e in db.expenses() if not prop_ids or e["property_id"] in prop_ids]

    rent_by_month: dict[str, float] = {}
    for row in rent_all:
        key = row["period"]
        rent_by_month[key] = rent_by_month.get(key, 0.0) + calc.to_float(
            row["paid_amount"] or row["due_amount"]
        )
    cost_by_month: dict[str, float] = {}
    for row in expenses_all:
        key = calc.month_key(row["date"])
        if not key:
            continue
        cost_by_month[key] = cost_by_month.get(key, 0.0) + calc.to_float(row["amount"])

    monthly_fixed = round(
        sum(calc.to_float(p["monthly_fixed_costs"]) for p in db.properties(include_inactive=False)), 2
    )

    rent_values, cost_values, net_values = [], [], []
    for period in periods:
        rent = round(rent_by_month.get(period, 0.0), 2)
        cost = round(cost_by_month.get(period, 0.0) + monthly_fixed, 2)
        rent_values.append(rent)
        cost_values.append(cost)
        net_values.append(round(rent - cost, 2))

    return ChartSeries(
        key="cashflow",
        labels=periods,
        values=net_values,
        series={"rent": rent_values, "expenses": cost_values, "net": net_values},
    )


def _rent_status_series(month_rent: list[dict]) -> ChartSeries:
    counts = {"paid": 0, "partial": 0, "unpaid": 0, "late": 0}
    amounts = {"paid": 0.0, "partial": 0.0, "unpaid": 0.0, "late": 0.0}
    for row in month_rent:
        status = (row.get("status") or "unpaid").lower()
        status = status if status in counts else "unpaid"
        counts[status] += 1
        amounts[status] += calc.to_float(row.get("due_amount"))
    return ChartSeries(
        key="rent_status",
        labels=list(counts.keys()),
        values=[round(v, 2) for v in amounts.values()],
        series={"counts": [float(v) for v in counts.values()]},
    )


def _expense_category_series(month_expenses: list[dict]) -> ChartSeries:
    grouped = calc.group_sum(month_expenses, "category", "amount")
    ordered = sorted(grouped.items(), key=lambda kv: kv[1], reverse=True)
    return ChartSeries(
        key="expenses_by_category",
        labels=[k for k, _ in ordered],
        values=[v for _, v in ordered],
    )


def _ranking_series(
    db: Database, properties: list[dict], leases: list[dict], today: _dt.date, months: int
) -> ChartSeries:
    """Net cashflow per property over the trailing window, best first."""
    periods = set(calc.last_n_months(today, months))
    rent_rows = db.rent_payments()
    expense_rows = db.expenses()

    rows: list[tuple[str, float]] = []
    for prop in properties:
        rent = sum(
            calc.to_float(r["paid_amount"] or r["due_amount"])
            for r in rent_rows
            if r["property_id"] == prop["id"] and r["period"] in periods
        )
        cost = sum(
            calc.to_float(e["amount"])
            for e in expense_rows
            if e["property_id"] == prop["id"] and calc.month_key(e["date"]) in periods
        ) + calc.to_float(prop["monthly_fixed_costs"]) * months
        rows.append((prop["name"], round(rent - cost, 2)))
    rows.sort(key=lambda kv: kv[1], reverse=True)
    return ChartSeries(
        key="property_ranking",
        labels=[name for name, _ in rows],
        values=[value for _, value in rows],
    )


def _renovation_rows(db: Database, prop_ids: set[int]) -> list[RenovationRow]:
    rows: list[RenovationRow] = []
    for reno in _filter_renovations(db, prop_ids):
        budget = calc.to_float(reno["budget"])
        # Real spend only: an unstarted job sits at €0, so its payback stays
        # unknown instead of being invented from the budget.
        actual = calc.renovation_actual_cost([reno["logged_cost"]])
        uplift = calc.to_float(reno["expected_monthly_rent_increase"])
        rows.append(
            RenovationRow(
                title=reno["title"],
                property_name=reno.get("property_name") or "",
                status=reno["status"],
                budget=budget,
                actual=actual,
                variance=calc.renovation_variance(budget, actual),
                monthly_uplift=uplift,
                payback_months=calc.renovation_payback_months(actual, uplift),
                value_uplift=calc.to_float(reno["expected_value_increase"]),
            )
        )
    rows.sort(key=lambda r: (r.payback_months is None, r.payback_months or 0))
    return rows


def _alerts(
    db: Database,
    prop_ids: set[int],
    today: _dt.date,
    month_rent: list[dict],
    properties: list[dict],
) -> list[str]:
    """Plain-language alerts — keys are translated in the UI layer."""
    codes: list[str] = []
    if any((r.get("status") or "") in ("late", "unpaid") for r in month_rent):
        codes.append("alert_rent_outstanding")
    vacant = _vacant_properties(db, prop_ids)
    if vacant:
        codes.append("alert_vacant")
    leases = [l for l in db.active_leases() if not prop_ids or l["property_id"] in prop_ids]
    for lease in leases:
        end = calc.parse_date(lease["end_date"])
        if end and 0 <= (end - today).days <= 60:
            codes.append("alert_lease_ending")
            break
    for prop in properties:
        if calc.to_float(prop["current_value"]) <= calc.EPSILON:
            codes.append("alert_missing_value")
            break
    return codes


def _vacant_properties(db: Database, prop_ids: set[int]) -> list[int]:
    leased = {l["property_id"] for l in db.active_leases()}
    return [
        p["id"]
        for p in db.properties(include_inactive=False)
        if (not prop_ids or p["id"] in prop_ids) and p["id"] not in leased
    ]


def rent_collection_for_period(db: Database, period: str) -> tuple[float, float]:
    rows = db.rent_payments(period)
    expected = round(sum(calc.to_float(r["due_amount"]) for r in rows), 2)
    collected = round(sum(calc.to_float(r["paid_amount"]) for r in rows), 2)
    return expected, collected
