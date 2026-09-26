"""Calculation tests: the numbers a landlord sees must be right.

These are pure functions with no database and no Qt, so they run anywhere.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from landlord_tracker.services import calculations as calc


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def test_safe_div_returns_none_instead_of_dividing_by_zero():
    assert calc.safe_div(10, 0) is None
    assert calc.safe_div(10, None) is None
    assert calc.safe_div(10, 4) == 2.5


def test_to_float_tolerates_junk():
    assert calc.to_float(None) == 0.0
    assert calc.to_float("") == 0.0
    assert calc.to_float("abc") == 0.0
    assert calc.to_float("12.5") == 12.5


def test_parse_date_handles_empty_and_junk():
    assert calc.parse_date("") is None
    assert calc.parse_date(None) is None
    assert calc.parse_date("not-a-date") is None
    assert calc.parse_date("2026-03-04") == _dt.date(2026, 3, 4)
    assert calc.parse_date("2026-03-04 10:00:00") == _dt.date(2026, 3, 4)


def test_month_key_and_label():
    assert calc.month_key("2026-03-04") == "2026-03"
    assert calc.month_key("") == ""
    assert calc.month_label("2026-03", "en") == "Mar 2026"
    assert calc.month_label("2026-03", "pt") == "mar 2026"


def test_last_n_months_crosses_year_boundary():
    months = calc.last_n_months(_dt.date(2026, 2, 15), 4)
    assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_month_sequence_is_inclusive():
    assert calc.month_sequence("2025-11", "2026-02") == [
        "2025-11", "2025-12", "2026-01", "2026-02"
    ]
    assert calc.month_sequence("2026-02", "2025-11") == []


def test_months_between():
    value = calc.months_between("2026-01-01", "2026-07-01")
    assert value is not None and 5.8 < value < 6.1
    assert calc.months_between("", "2026-07-01") is None


# --------------------------------------------------------------------------
# rent status logic
# --------------------------------------------------------------------------
TODAY = _dt.date(2026, 3, 20)


def test_fully_paid_is_paid_even_after_due_date():
    assert calc.compute_rent_status(680, 680, "2026-03-05", "2026-03-25", TODAY) == "paid"
    assert calc.compute_rent_status(680, 700, "2026-03-05", "2026-03-25", TODAY) == "paid"


def test_partial_payment_past_due_is_late():
    assert calc.compute_rent_status(680, 400, "2026-03-05", "2026-03-06", TODAY) == "late"


def test_partial_payment_before_due_is_partial():
    assert calc.compute_rent_status(680, 400, "2026-03-25", "", TODAY) == "partial"


def test_nothing_paid_past_due_is_late():
    assert calc.compute_rent_status(680, 0, "2026-03-05", "", TODAY) == "late"


def test_nothing_paid_not_yet_due_is_unpaid():
    assert calc.compute_rent_status(680, 0, "2026-03-25", "", TODAY) == "unpaid"


def test_zero_due_with_payment_counts_as_paid():
    assert calc.compute_rent_status(0, 120, "", "2026-03-02", TODAY) == "paid"


def test_rent_balance_and_arrears():
    assert calc.rent_balance(680, 400) == 280.0
    rows = [
        {"due_amount": 680, "paid_amount": 680, "status": "paid"},
        {"due_amount": 680, "paid_amount": 400, "status": "late"},
        {"due_amount": 595, "paid_amount": 0, "status": "unpaid"},
    ]
    assert calc.arrears(rows) == 875.0


def test_rent_collection_rate():
    assert calc.rent_collection_rate(1275, 1500) == 0.85
    assert calc.rent_collection_rate(0, 0) is None


# --------------------------------------------------------------------------
# property performance
# --------------------------------------------------------------------------
def test_net_cashflow():
    assert calc.net_cashflow(1275, 410.5) == 864.5
    assert calc.net_cashflow(0, 410.5) == -410.5


def test_yields():
    assert calc.gross_yield(15000, 300000) == 0.05
    assert calc.net_yield(15000, 4000, 300000) == pytest.approx(0.036667, rel=1e-4)
    assert calc.gross_yield(15000, 0) is None


def test_capital_gain_percent():
    assert calc.total_return_percent(100000, 150000) == 0.5
    assert calc.total_return_percent(0, 150000) is None


def test_occupied_share():
    assert calc.occupied_share(3, 4) == 0.75
    assert calc.occupied_share(0, 0) is None


# --------------------------------------------------------------------------
# renovations / payback — the headline feature
# --------------------------------------------------------------------------
def test_renovation_payback_months():
    assert calc.renovation_payback_months(4200, 75) == pytest.approx(56.0)
    assert calc.renovation_payback_months(1800, 0) is None  # never invented
    assert calc.renovation_payback_years(4200, 75) == pytest.approx(56 / 12)


def test_renovation_actual_cost_is_real_spend_only():
    """Actual starts at €0 and never borrows the budget.

    Rodrigo's call (Sep 2026): a job with nothing logged has cost nothing, so the
    budget must not stand in for actual spend. This replaced the earlier
    fallback-to-estimate behaviour.
    """
    assert calc.renovation_actual_cost([]) == 0.0
    assert calc.renovation_actual_cost([0]) == 0.0
    assert calc.renovation_actual_cost([2400, 1500]) == 3900.0


def test_renovation_variance_sign_convention():
    # positive == over budget, which is what a landlord needs to see
    assert calc.renovation_variance(4200, 4600) == 400.0
    assert calc.renovation_variance(4200, 3800) == -400.0
    assert calc.renovation_variance_percent(4000, 5000) == 0.25


def test_value_uplift_roi():
    assert calc.value_uplift_roi(4200, 9000) == pytest.approx(1.142857, rel=1e-5)
    assert calc.value_uplift_roi(0, 9000) is None


# --------------------------------------------------------------------------
# aggregation
# --------------------------------------------------------------------------
def test_group_sum_buckets_missing_category_into_other():
    rows = [
        {"category": "repair", "amount": 100},
        {"category": "repair", "amount": 50},
        {"category": "", "amount": 25},
        {"amount": 10},
    ]
    assert calc.group_sum(rows, "category", "amount") == {
        "repair": 150.0, "other": 35.0
    }


def test_percentage_share_and_trailing_average():
    assert calc.percentage_share(25, 200) == 0.125
    assert calc.percentage_share(25, 0) is None
    assert calc.trailing_average([10, 20, 30]) == 20.0
    assert calc.trailing_average([]) is None


def test_annualise_and_rent_roll():
    assert calc.annualise_monthly(1000) == 12000.0
    assert calc.rent_roll_total([
        {"monthly_rent": 680, "status": "active"},
        {"monthly_rent": 595, "status": "active"},
        {"monthly_rent": 0, "status": "ended"},
    ]) == 1275.0
