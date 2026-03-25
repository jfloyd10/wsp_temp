"""Management command to seed the profit_and_loss_statement table in DuckDB."""

import random
from datetime import datetime

import duckdb
from django.conf import settings
from django.core.management.base import BaseCommand


# P&L structure: category -> type -> subtype -> [line_items]
PNL_STRUCTURE = {
    "Revenue": {
        "Operating Revenue": {
            "Energy Sales": [
                "Wholesale Energy Sales",
                "Bilateral Contract Revenue",
                "PPA Revenue",
                "Capacity Sales",
            ],
            "Interchange Revenue": [
                "Associated Interchange",
                "Non-Associated Interchange",
                "Emergency Energy Sales",
            ],
            "Ancillary Services": [
                "Regulation Service Revenue",
                "Spinning Reserve Revenue",
                "Non-Spinning Reserve Revenue",
            ],
        },
        "Non-Operating Revenue": {
            "Other Revenue": [
                "Interest Income",
                "Miscellaneous Revenue",
                "Gain on Asset Sales",
            ],
        },
    },
    "Cost of Revenue": {
        "Fuel Expense": {
            "Gas": [
                "Natural Gas - Combined Cycle",
                "Natural Gas - Peaking",
                "Gas Transportation & Storage",
            ],
            "Coal": [
                "Coal Purchases",
                "Coal Transportation",
                "Coal Handling & Storage",
            ],
            "Nuclear": [
                "Nuclear Fuel Amortization",
                "Nuclear Fuel Disposal Fee",
            ],
        },
        "Purchased Power": {
            "Wholesale Purchases": [
                "Bilateral Contract Purchases",
                "Spot Market Purchases",
                "Emergency Energy Purchases",
            ],
            "PPA Expense": [
                "Solar PPA Payments",
                "Wind PPA Payments",
                "QF Contract Payments",
            ],
        },
    },
    "Operating Expenses": {
        "O&M Expense": {
            "Generation O&M": [
                "Plant Operations Labor",
                "Plant Maintenance",
                "Environmental Compliance",
                "Water & Chemical Treatment",
            ],
            "Transmission O&M": [
                "Transmission Operations",
                "Transmission Maintenance",
                "OATT Administration",
            ],
        },
        "Administrative & General": {
            "Corporate Overhead": [
                "Salaries & Benefits - Admin",
                "Professional Services",
                "Insurance Expense",
                "IT & Technology",
            ],
            "Regulatory": [
                "FERC Filing Fees",
                "Regulatory Compliance",
                "Rate Case Expense",
            ],
        },
        "Depreciation & Amortization": {
            "Depreciation": [
                "Generation Plant Depreciation",
                "Transmission Plant Depreciation",
                "General Plant Depreciation",
            ],
            "Amortization": [
                "Intangible Asset Amortization",
                "Regulatory Asset Amortization",
            ],
        },
    },
    "Other Income / (Expense)": {
        "Interest Expense": {
            "Long-term Debt": [
                "Senior Notes Interest",
                "Term Loan Interest",
            ],
            "Short-term Debt": [
                "Commercial Paper Interest",
                "Credit Facility Fees",
            ],
        },
        "Other": {
            "Non-Operating": [
                "Allowance for Funds (AFUDC)",
                "Mark-to-Market Adjustments",
                "Realized Hedging Gains/(Losses)",
            ],
        },
    },
}

ENTITIES = [
    ("Georgia Power", "Retail OpCo"),
    ("Alabama Power", "Retail OpCo"),
    ("Mississippi Power", "Retail OpCo"),
    ("Southern Power", "Wholesale OpCo"),
    ("Southern Company Gas", "Gas Utility"),
]

SOURCES = ["POOL_BILL", "WHOLESALE_SETTLEMENT", "GAS_ACCOUNTING", "GENERAL_LEDGER"]

ALLOCATION_NAMES = [
    "Direct Assignment",
    "Energy Allocation",
    "Demand Allocation",
    "Production Cost Allocation",
    "Composite Allocation",
]

TAGS = ["Actual", "Budget", "Forecast"]
LEDGERS = ["Operating", "Capital", "Regulatory"]
COVERED_UNCOVERED = ["Covered", "Uncovered"]


def _base_amount(category: str, line_item: str) -> float:
    """Return a realistic monthly base amount for a line item."""
    if category == "Revenue":
        if "Wholesale Energy" in line_item:
            return random.uniform(45_000_000, 85_000_000)
        if "Bilateral Contract Revenue" in line_item:
            return random.uniform(25_000_000, 55_000_000)
        if "PPA Revenue" in line_item:
            return random.uniform(15_000_000, 35_000_000)
        if "Capacity" in line_item:
            return random.uniform(8_000_000, 18_000_000)
        if "Interchange" in line_item:
            return random.uniform(5_000_000, 15_000_000)
        if "Ancillary" in line_item or "Reserve" in line_item or "Regulation" in line_item:
            return random.uniform(1_000_000, 5_000_000)
        if "Interest Income" in line_item:
            return random.uniform(500_000, 2_000_000)
        return random.uniform(200_000, 3_000_000)
    elif category == "Cost of Revenue":
        if "Natural Gas - Combined" in line_item:
            return -random.uniform(30_000_000, 60_000_000)
        if "Natural Gas - Peaking" in line_item:
            return -random.uniform(5_000_000, 20_000_000)
        if "Gas Transportation" in line_item:
            return -random.uniform(3_000_000, 8_000_000)
        if "Coal Purchases" in line_item:
            return -random.uniform(15_000_000, 35_000_000)
        if "Coal Transportation" in line_item:
            return -random.uniform(4_000_000, 10_000_000)
        if "Nuclear" in line_item:
            return -random.uniform(5_000_000, 12_000_000)
        if "Bilateral Contract Purchases" in line_item:
            return -random.uniform(10_000_000, 25_000_000)
        if "Spot Market" in line_item:
            return -random.uniform(5_000_000, 18_000_000)
        if "PPA" in line_item or "QF" in line_item:
            return -random.uniform(3_000_000, 10_000_000)
        return -random.uniform(1_000_000, 8_000_000)
    elif category == "Operating Expenses":
        if "Depreciation" in line_item and "Generation" in line_item:
            return -random.uniform(8_000_000, 15_000_000)
        if "Depreciation" in line_item:
            return -random.uniform(2_000_000, 6_000_000)
        if "Amortization" in line_item:
            return -random.uniform(1_000_000, 4_000_000)
        if "Labor" in line_item or "Salaries" in line_item:
            return -random.uniform(3_000_000, 8_000_000)
        if "Maintenance" in line_item:
            return -random.uniform(2_000_000, 6_000_000)
        return -random.uniform(500_000, 3_000_000)
    else:  # Other Income / (Expense)
        if "Senior Notes" in line_item:
            return -random.uniform(4_000_000, 10_000_000)
        if "AFUDC" in line_item:
            return random.uniform(1_000_000, 4_000_000)
        if "Mark-to-Market" in line_item:
            return random.uniform(-3_000_000, 3_000_000)
        if "Hedging" in line_item:
            return random.uniform(-2_000_000, 2_000_000)
        return -random.uniform(500_000, 3_000_000)


def _seasonal_factor(month: int) -> float:
    """Seasonal multiplier — summer/winter peak, spring/fall trough."""
    factors = {
        1: 1.15, 2: 1.05, 3: 0.90, 4: 0.85, 5: 0.90, 6: 1.10,
        7: 1.25, 8: 1.30, 9: 1.10, 10: 0.88, 11: 0.92, 12: 1.08,
    }
    return factors.get(month, 1.0)


def _entity_scale(entity_name: str) -> float:
    """Scale factor by entity size."""
    scales = {
        "Georgia Power": 1.0,
        "Alabama Power": 0.65,
        "Mississippi Power": 0.30,
        "Southern Power": 0.80,
        "Southern Company Gas": 0.45,
    }
    return scales.get(entity_name, 0.5)


def _yoy_growth(year: int) -> float:
    """Year-over-year growth factor."""
    return {2022: 1.0, 2023: 1.035, 2024: 1.06, 2025: 1.08}.get(year, 1.0)


class Command(BaseCommand):
    help = "Seed the profit_and_loss_statement table in DuckDB with demo data."

    def handle(self, *args, **options):
        random.seed(42)
        db_path = str(settings.DUCKDB_PATH)
        conn = duckdb.connect(db_path, read_only=False)

        # Create table
        conn.execute("DROP TABLE IF EXISTS profit_and_loss_statement")
        conn.execute("""
            CREATE TABLE profit_and_loss_statement (
                short_desc VARCHAR,
                source VARCHAR,
                year INTEGER,
                month INTEGER,
                dt TIMESTAMP,
                entity_class VARCHAR,
                entity_name VARCHAR,
                covered_or_uncovered VARCHAR,
                allocation_name VARCHAR,
                category VARCHAR,
                type VARCHAR,
                subtype VARCHAR,
                line_item VARCHAR,
                legacy_subtype VARCHAR,
                tag VARCHAR,
                ledger VARCHAR,
                amount DECIMAL(18, 2)
            )
        """)

        rows = []
        years = [2022, 2023, 2024, 2025]
        max_month = {2022: 12, 2023: 12, 2024: 12, 2025: 12}

        for year in years:
            for month in range(1, max_month[year] + 1):
                dt = datetime(year, month, 1)
                for entity_name, entity_class in ENTITIES:
                    for category, types in PNL_STRUCTURE.items():
                        for type_name, subtypes in types.items():
                            for subtype_name, line_items in subtypes.items():
                                for line_item in line_items:
                                    base = _base_amount(category, line_item)
                                    amount = (
                                        base
                                        * _seasonal_factor(month)
                                        * _entity_scale(entity_name)
                                        * _yoy_growth(year)
                                        * random.uniform(0.92, 1.08)
                                    )
                                    amount = round(amount, 2)

                                    source = random.choice(SOURCES)
                                    allocation = random.choice(ALLOCATION_NAMES)
                                    tag = "Actual"
                                    covered = random.choice(COVERED_UNCOVERED)
                                    ledger = random.choice(LEDGERS)
                                    short_desc = f"{entity_name[:3].upper()} {line_item[:30]}"
                                    legacy_subtype = subtype_name.upper().replace(" ", "_")

                                    rows.append((
                                        short_desc, source, year, month, dt,
                                        entity_class, entity_name,
                                        covered, allocation,
                                        category, type_name, subtype_name,
                                        line_item, legacy_subtype, tag, ledger,
                                        amount,
                                    ))

        conn.executemany(
            "INSERT INTO profit_and_loss_statement VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        count = conn.execute("SELECT COUNT(*) FROM profit_and_loss_statement").fetchone()[0]
        conn.close()

        self.stdout.write(self.style.SUCCESS(f"Seeded {count:,} P&L rows into {db_path}"))
