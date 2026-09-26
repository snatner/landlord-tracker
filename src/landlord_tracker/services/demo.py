"""Demo data loader.

Lets a new user explore the app before typing real tenant data. It is clearly
labelled in the UI and removable with one click, stored in a local flag so we
never touch real data by accident.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from ..db import Database, now_iso
from ..models import (
    Document,
    DocumentLink,
    Expense,
    Lease,
    Property,
    RecurringExpense,
    Renovation,
    RentPayment,
    Tenant,
)
from . import calculations as calc

DEMO_FLAG = "demo_data"


def _month_keys(count: int) -> list[str]:
    today = _dt.date.today()
    index = today.year * 12 + today.month - 1
    return [f"{(index - offset) // 12:04d}-{(index - offset) % 12 + 1:02d}"
            for offset in range(count - 1, -1, -1)]


def _date_in(period: str, day: int) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{year:04d}-{month:02d}-{day:02d}"


def load_demo(db: Database) -> None:
    """Populate the database with a realistic small Portuguese portfolio."""
    db.wipe(["rent_payments", "expenses", "recurring_expenses", "documents",
             "renovations", "leases", "tenants", "properties"])

    today = _dt.date.today()
    periods = _month_keys(12)

    # -- properties -----------------------------------------------------
    # The demo portfolio is DELIBERATELY set in Lisboa rather than the author's
    # own city. These records are rendered into screenshots that ship in the
    # README and the store listings, so demo data must not disclose where he
    # actually lives. Keep it geographically fictional, and keep the postcodes
    # consistent with the city (Lisboa postcodes start with 1).
    flat_two = db.add_property(Property(
        name="Rua das Flores 12, 2º Esq",
        address="Rua das Flores 12", city="Lisboa", postcode="1200-192",
        property_type="T2 apartment",
        purchase_price=118000, purchase_date="2019-04-12",
        current_value=168000, monthly_fixed_costs=62, size_m2=78,
        notes="Bought below market, refurbished kitchen in 2021.",
    ))
    ground = db.add_property(Property(
        name="Av. D. Afonso Henriques 45, R/C",
        address="Av. D. Afonso Henriques 45", city="Lisboa", postcode="1900-231",
        property_type="T1 apartment",
        purchase_price=92000, purchase_date="2021-09-01",
        current_value=139000, monthly_fixed_costs=48, size_m2=54,
        notes="Ground floor, small garden. Long-term tenant.",
    ))
    house = db.add_property(Property(
        name="Travessa do Forno 8",
        address="Travessa do Forno 8", city="Lisboa", postcode="1100-232",
        property_type="T3 house",
        purchase_price=76000, purchase_date="2023-02-20",
        current_value=124000, monthly_fixed_costs=35, size_m2=112,
        notes="Under renovation. Bathroom and floors done, painting pending.",
    ))

    # -- tenants + leases ----------------------------------------------
    ana = db.add_tenant(Tenant(
        full_name="Ana Ferreira", property_id=flat_two, phone="+351 912 000 111",
        email="ana.ferreira@example.pt", tax_number="245678901",
        emergency_contact="João Ferreira +351 913 000 222",
    ))
    bruno = db.add_tenant(Tenant(
        full_name="Bruno Matos", property_id=ground, phone="+351 934 555 666",
        email="bruno.matos@example.pt", tax_number="212345678",
    ))
    carla = db.add_tenant(Tenant(
        full_name="Carla Nunes", property_id=house, phone="+351 967 888 999",
        tax_number="234567812", is_active=0, notes="Previous tenant, left in 2024.",
    ))

    lease_ana = db.add_lease(Lease(
        property_id=flat_two, tenant_id=ana, start_date="2022-06-01",
        end_date=f"{today.year + 1}-05-31", monthly_rent=680, deposit_amount=680,
        due_day=5, last_increase_date="2025-06-01",
    ))
    lease_bruno = db.add_lease(Lease(
        property_id=ground, tenant_id=bruno, start_date="2023-01-15",
        end_date="", monthly_rent=595, deposit_amount=595, due_day=1,
        last_increase_date="2026-01-01",
    ))
    db.add_lease(Lease(
        property_id=house, tenant_id=carla, start_date="2023-04-01",
        end_date="2024-03-31", monthly_rent=0, deposit_amount=500,
        status="ended",
    ))

    # -- rent ledger ----------------------------------------------------
    for index, period in enumerate(periods):
        is_current = period == periods[-1]
        for lease, rent, base_status in ((lease_ana, 680, "paid"), (lease_bruno, 595, "paid")):
            due_date = _date_in(period, 5 if lease == lease_ana else 1)
            paid_amount, paid_date, status = rent, due_date, base_status
            # a small amount of realistic friction in the history
            if index == len(periods) - 4 and lease == lease_ana:
                paid_amount, status, paid_date = 400.0, "late", _date_in(period, 19)
            if is_current and lease == lease_bruno:
                paid_amount, paid_date, status = 0.0, "", "unpaid"
            db.add_rent(RentPayment(
                lease_id=lease, property_id=(flat_two if lease == lease_ana else ground),
                tenant_id=(ana if lease == lease_ana else bruno),
                period=period, due_amount=rent, due_date=due_date,
                paid_amount=paid_amount, paid_date=paid_date, status=status,
                method="Bank transfer" if paid_amount else "",
            ))

    # -- renovations ----------------------------------------------------
    bathroom = db.add_renovation(Renovation(
        property_id=house, title="Bathroom renovation", category="bathroom",
        status="done", start_date="2025-09-01", end_date="2025-10-10",
        budget=4200, expected_monthly_rent_increase=75, expected_value_increase=9000,
        contractor="Obras Lisboa Lda",
        notes="Walk-in shower, no glass cabin. Tenant-ready.",
    ))
    kitchen = db.add_renovation(Renovation(
        property_id=house, title="Kitchen replacement", category="kitchen",
        status="in_progress", start_date="2026-02-01",
        budget=6500, expected_monthly_rent_increase=90, expected_value_increase=14000,
        contractor="Cozinhas Lisboa",
    ))
    painting = db.add_renovation(Renovation(
        property_id=house, title="Exterior painting", category="painting",
        status="planned", start_date="",
        budget=1800, expected_monthly_rent_increase=0, expected_value_increase=4000,
        notes="Cosmetic. No rent uplift expected.",
    ))

    # -- expenses -------------------------------------------------------
    def expense(prop: int, date: str, category: str, amount: float,
                vendor: str, description: str, renovation_id: Optional[int] = None) -> None:
        db.add_expense(Expense(
            property_id=prop, date=date, category=category, amount=amount,
            vendor=vendor, description=description, renovation_id=renovation_id,
        ))

    # linked renovation costs (these drive the payback numbers)
    expense(house, "2025-09-08", "maintenance", 1850.0, "Obras Lisboa Lda",
            "Bathroom demolition and plumbing", bathroom)
    expense(house, "2025-09-26", "maintenance", 1420.0, "Casa Banho & Cia",
            "Walk-in shower base, tiles, fittings", bathroom)
    expense(house, "2025-10-04", "maintenance", 780.0, "Obras Lisboa Lda",
            "Electrical work and finishing", bathroom)
    expense(house, "2026-02-05", "maintenance", 2400.0, "Cozinhas Lisboa",
            "Kitchen units deposit", kitchen)

    # recurring costs across the last 12 months
    for index, period in enumerate(periods):
        expense(flat_two, _date_in(period, 3), "condo", 62.0, "Condomínio Flores",
                "Monthly condo fee")
        expense(ground, _date_in(period, 3), "condo", 48.0, "Condomínio Afonso",
                "Monthly condo fee")
        if index % 12 == 0:
            expense(flat_two, _date_in(period, 20), "insurance", 148.0, "Fidelidade",
                    "Annual building insurance")
            expense(ground, _date_in(period, 20), "insurance", 126.0, "Fidelidade",
                    "Annual building insurance")

    expense(flat_two, "2026-01-12", "repair", 320.0, "Pintores Lisboa",
            "Living room repaint after tenant damage")
    expense(ground, "2026-02-18", "repair", 185.0, "Hidráulica Rápida",
            "Kitchen tap and siphon replacement")
    expense(flat_two, "2026-03-02", "property_tax", 412.0, "Autoridade Tributária",
            "IMI annual")
    expense(ground, "2026-03-02", "property_tax", 356.0, "Autoridade Tributária",
            "IMI annual")

    # -- recurring cost templates ---------------------------------------
    # The rows above are history (what was actually paid). These templates are
    # the plan, so a new user can see how "generate expenses for month" works
    # without typing a single condo fee by hand.
    anchor = periods[0]
    db.add_recurring_expense(RecurringExpense(
        property_id=flat_two, category="condo", amount=62.0,
        vendor="Condomínio Flores", description="Monthly condo fee",
        frequency="monthly", day_of_month=3, start_month=anchor))
    db.add_recurring_expense(RecurringExpense(
        property_id=ground, category="condo", amount=48.0,
        vendor="Condomínio Afonso", description="Monthly condo fee",
        frequency="monthly", day_of_month=3, start_month=anchor))
    db.add_recurring_expense(RecurringExpense(
        property_id=flat_two, category="insurance", amount=148.0,
        vendor="Fidelidade", description="Annual building insurance",
        frequency="annual", day_of_month=20, start_month=anchor))
    db.add_recurring_expense(RecurringExpense(
        property_id=ground, category="insurance", amount=126.0,
        vendor="Fidelidade", description="Annual building insurance",
        frequency="annual", day_of_month=20, start_month=anchor))
    db.add_recurring_expense(RecurringExpense(
        property_id=house, category="property_tax", amount=310.0,
        vendor="Autoridade Tributária", description="IMI (annual property tax)",
        frequency="annual", day_of_month=31, start_month=anchor,
        notes="Due in the tax office's own month; day clamps to the month's last day."))

    _seed_documents(db, flat_two, ground, ana, bruno, kitchen)

    db.set_setting(DEMO_FLAG, "1")
    db.set_setting("demo_loaded_at", now_iso())


def _seed_documents(db: Database, flat_two: int, ground: int, ana: int, bruno: int,
                    kitchen: int) -> None:
    """Write a few placeholder files into the local vault and register them.

    Demonstrates that attachments are plain local files the landlord can open
    without any account or cloud service.
    """
    samples = [
        ("Lease — Ana Ferreira", DocumentLink.LEASE.value, ana,
         "lease-ana-ferreira.txt",
         "DEMO FILE\n\nLease agreement (sample).\n"
         "Tenant: Ana Ferreira\nRent: 680 EUR\nDue day: 5\n"),
        ("Lease — Bruno Matos", DocumentLink.LEASE.value, bruno,
         "lease-bruno-matos.txt",
         "DEMO FILE\n\nLease agreement (sample).\n"
         "Tenant: Bruno Matos\nRent: 595 EUR\nDue day: 1\n"),
        ("Energy certificate", DocumentLink.PROPERTY.value, flat_two,
         "certificado-energetico-flores.txt",
         "DEMO FILE\n\nEnergy performance certificate (sample).\nRating: B-\n"),
        ("Building insurance policy", DocumentLink.PROPERTY.value, ground,
         "seguro-afonso.txt",
         "DEMO FILE\n\nBuilding insurance policy (sample).\n"
         "Cover: fire, water damage, liability\n"),
        ("Kitchen invoice", DocumentLink.RENOVATION.value, kitchen,
         "fatura-cozinha.txt",
         "DEMO FILE\n\nContractor invoice (sample).\nKitchen units deposit: 2400 EUR\n"),
    ]
    for title, related_type, related_id, filename, content in samples:
        path = db.documents_dir / filename
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:  # pragma: no cover - read-only disk
            continue
        db.add_document(Document(
            title=title, related_type=related_type, related_id=related_id,
            file_path=str(path), notes="Sample document created with the demo data.",
        ))


def clear_demo(db: Database) -> None:
    db.wipe(["rent_payments", "expenses", "recurring_expenses", "documents",
             "renovations", "leases", "tenants", "properties"])
    db.set_setting(DEMO_FLAG, "0")


def is_demo(db: Database) -> bool:
    return db.get_setting(DEMO_FLAG, "0") == "1"


def demo_summary(db: Database) -> dict:
    """Sanity numbers used by tests and the screenshot harness."""
    renovation_rows = db.renovations()
    total_budget = sum(calc.to_float(r["budget"]) for r in renovation_rows)
    total_logged = sum(calc.to_float(r["logged_cost"]) for r in renovation_rows)
    return {
        "properties": db.count("properties"),
        "tenants": db.count("tenants"),
        "leases": db.count("leases"),
        "rent_rows": db.count("rent_payments"),
        "expenses": db.count("expenses"),
        "renovations": db.count("renovations"),
        "renovation_budget": round(total_budget, 2),
        "renovation_logged": round(total_logged, 2),
    }
