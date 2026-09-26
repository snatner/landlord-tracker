"""Translation tests: both shipped languages must stay complete and identical."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from landlord_tracker import i18n

LOCALE_DIR = Path(i18n.__file__).resolve().parent / "resources" / "locale"


def load(code: str) -> dict:
    return json.loads((LOCALE_DIR / f"{code}.json").read_text(encoding="utf-8"))


def test_both_catalogs_exist():
    for code in ("en", "pt"):
        assert (LOCALE_DIR / f"{code}.json").exists()


def test_catalogs_have_identical_key_sets():
    en, pt = load("en"), load("pt")
    assert set(en) == set(pt), (
        f"only in en: {sorted(set(en) - set(pt))}\n"
        f"only in pt: {sorted(set(pt) - set(en))}"
    )


def test_no_empty_translations():
    for code in ("en", "pt"):
        empty = [k for k, v in load(code).items() if not str(v).strip()]
        assert not empty, f"{code} has empty values: {empty}"


def test_set_language_and_tr_round_trip():
    i18n.set_language("en")
    assert i18n.tr("nav_dashboard") == "Dashboard"
    i18n.set_language("pt")
    assert i18n.tr("nav_dashboard") == "Painel"
    i18n.set_language("en")


def test_unknown_language_falls_back_to_english():
    i18n.set_language("xx")
    assert i18n.current_language() == "en"
    assert i18n.tr("nav_rent") == "Rent"


def test_missing_key_returns_key_or_default():
    i18n.set_language("en")
    assert i18n.tr("definitely_not_a_key") == "definitely_not_a_key"
    assert i18n.tr("definitely_not_a_key", default="fallback") == "fallback"


def test_formatting_placeholders_resolve():
    i18n.set_language("en")
    assert i18n.tr("last_months", count=6) == "Last 6 months"
    i18n.set_language("pt")
    assert i18n.tr("last_months", count=6) == "Últimos 6 meses"
    i18n.set_language("en")


def test_all_keys_used_in_source_exist_in_english_catalog():
    """Guards against a tr("...") key that nobody translated."""
    import re

    src = Path(i18n.__file__).resolve().parent
    pattern = re.compile(r"""tr\(\s*["']([a-z0-9_]+)["']""")
    used: set[str] = set()
    for path in src.rglob("*.py"):
        used.update(pattern.findall(path.read_text(encoding="utf-8")))

    # dynamic f-string keys built at runtime
    dynamic = {"renovations", "properties", "tenants", "leases", "rent"}
    for prefix in ("renovation_id", "lease_status", "reno_cat", "reno_status",
                   "expense_cat", "rent_status", "document_link"):
        used = {k for k in used if not k.startswith(prefix)}
    for suffix in ("_subtitle",):
        used = {k for k in used if not k.endswith(suffix)}

    catalog = set(load("en"))
    missing = sorted(key for key in used if key not in catalog and key not in dynamic)
    assert not missing, f"untranslated keys used in code: {missing}"


def test_runtime_dynamic_keys_exist():
    catalog = set(load("en"))
    from landlord_tracker.models import (
        EXPENSE_CATEGORIES, RECURRENCE_FREQUENCIES, RENOVATION_CATEGORIES,
        RENOVATION_STATUSES, RentStatus,
    )
    from landlord_tracker.models import DocumentLink, LeaseStatus

    for value in EXPENSE_CATEGORIES:
        assert f"expense_cat_{value}" in catalog
    for value in RECURRENCE_FREQUENCIES:
        assert f"freq_{value}" in catalog
    for value in RENOVATION_CATEGORIES:
        assert f"reno_cat_{value}" in catalog
    for value in RENOVATION_STATUSES:
        assert f"reno_status_{value}" in catalog
    for value in (s.value for s in RentStatus):
        assert f"rent_status_{value}" in catalog
    for value in (s.value for s in LeaseStatus):
        assert f"lease_status_{value}" in catalog
    for value in (s.value for s in DocumentLink):
        assert f"document_link_{value}" in catalog
    for key in ("properties_subtitle", "tenants_subtitle", "leases_subtitle",
                "rent_subtitle", "expenses_subtitle", "recurring_subtitle",
                "renovations_subtitle", "documents_subtitle", "settings_subtitle"):
        assert key in catalog
