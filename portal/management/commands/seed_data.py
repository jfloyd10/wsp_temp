"""Management command to generate realistic sample data in DuckDB."""

import random
import datetime
import duckdb
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed the DuckDB database with realistic wholesale settlement demo data'

    def handle(self, *args, **options):
        db_path = str(settings.DUCKDB_PATH)
        settings.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(db_path)
        self._create_tables(conn)
        self._seed_invoice_data(conn)
        self._seed_fcs_metrics(conn)
        self._seed_capacity_factors(conn)
        conn.close()

        self.stdout.write(self.style.SUCCESS('Successfully seeded DuckDB database.'))

    def _create_tables(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_header (
                source_system VARCHAR,
                source_type VARCHAR,
                operating_company VARCHAR,
                invoice_no VARCHAR PRIMARY KEY,
                invoice_name VARCHAR,
                invoice_date TIMESTAMP,
                invoice_status VARCHAR,
                counterparty_id VARCHAR,
                counterparty_name VARCHAR,
                invoice_total DECIMAL(12,2)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_detail (
                source_system VARCHAR,
                source_type VARCHAR,
                invoice_no VARCHAR,
                line_id VARCHAR,
                line_name VARCHAR,
                uom VARCHAR,
                quantity DECIMAL,
                rate DECIMAL,
                amount DECIMAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_file_attachments (
                source_system VARCHAR,
                source_type VARCHAR,
                invoice_no VARCHAR,
                file_name VARCHAR,
                file_ext VARCHAR,
                file_size INTEGER,
                file_contents BLOB
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fcs_metrics (
                source_system VARCHAR,
                year INTEGER,
                month INTEGER,
                adjustments DECIMAL,
                total_settled DECIMAL,
                adjustment_percent DECIMAL,
                cumulative_adjustment DECIMAL,
                cumulative_total DECIMAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS capacity_factors (
                year INTEGER,
                month INTEGER,
                operating_company VARCHAR,
                resource_id VARCHAR,
                resource_name VARCHAR,
                resource_type VARCHAR,
                ownership_share DECIMAL,
                total_net_generation DECIMAL,
                net_generation DECIMAL,
                budget_generation DECIMAL,
                hours_in_month INTEGER,
                total_rating_mw DECIMAL,
                rating_mw_share DECIMAL,
                total_mwh_possible DECIMAL,
                ac_capacity_factor DECIMAL,
                bu_capacity_factor DECIMAL,
                capacity_factor_variance DECIMAL
            )
        """)
        # Clear existing data
        for table in ['invoice_header', 'invoice_detail', 'invoice_file_attachments',
                       'fcs_metrics', 'capacity_factors']:
            conn.execute(f"DELETE FROM {table}")

    def _seed_invoice_data(self, conn):
        random.seed(42)

        operating_companies = ['Georgia Power', 'Alabama Power', 'Mississippi Power']
        source_configs = [
            ('POOL_BILL', 'WHOLESALE'),
            ('WHOLESALE_SETTLEMENT', 'SHORT_TERM'),
            ('WHOLESALE_SETTLEMENT', 'PPA'),
            ('GAS_ACCOUNTING', 'GAS_TRANSPORT'),
            ('COAL_ACCOUNTING', 'COAL_SUPPLY'),
        ]
        counterparties = [
            ('CP001', 'Duke Energy Carolinas'),
            ('CP002', 'Tennessee Valley Authority'),
            ('CP003', 'Florida Power & Light'),
            ('CP004', 'Entergy Mississippi'),
            ('CP005', 'South Carolina Electric & Gas'),
            ('CP006', 'Oglethorpe Power'),
            ('CP007', 'Municipal Electric Authority of GA'),
            ('CP008', 'Dalton Utilities'),
            ('CP009', 'PowerSouth Energy Cooperative'),
            ('CP010', 'Seminole Electric Cooperative'),
        ]
        statuses = ['FINAL', 'FINAL', 'FINAL', 'FINAL', 'DRAFT', 'ADJUSTED']
        line_item_templates = {
            'WHOLESALE': [
                ('Energy Charge - On Peak', 'MWH'),
                ('Energy Charge - Off Peak', 'MWH'),
                ('Demand Charge', 'MW'),
                ('Transmission Service', 'MW'),
                ('Ancillary Services', '$'),
                ('Scheduling & Dispatch', '$'),
            ],
            'SHORT_TERM': [
                ('Spot Energy Purchase', 'MWH'),
                ('Spot Energy Sale', 'MWH'),
                ('Imbalance Charge', 'MWH'),
                ('Congestion Cost', '$'),
            ],
            'PPA': [
                ('Capacity Payment', 'MW'),
                ('Energy Payment', 'MWH'),
                ('Fixed O&M', '$'),
                ('Variable O&M', 'MWH'),
                ('Fuel Adder', 'MMBTU'),
            ],
            'GAS_TRANSPORT': [
                ('Firm Transport - Reservation', 'MMBTU'),
                ('Firm Transport - Usage', 'MMBTU'),
                ('Interruptible Transport', 'MMBTU'),
                ('Fuel Retainage', 'MMBTU'),
                ('Balancing Charge', '$'),
            ],
            'COAL_SUPPLY': [
                ('Base Coal Delivery', 'TONS'),
                ('Quality Adjustment', '$'),
                ('Transportation Surcharge', '$'),
                ('Ash Disposal Credit', '$'),
            ],
        }

        invoice_count = 0
        for year in [2024, 2025]:
            end_month = 12 if year == 2024 else 3
            for month in range(1, end_month + 1):
                inv_date = datetime.datetime(year, month, 15)
                for oc in operating_companies:
                    num_invoices = random.randint(2, 5)
                    for _ in range(num_invoices):
                        invoice_count += 1
                        source_system, source_type = random.choice(source_configs)
                        cp_id, cp_name = random.choice(counterparties)
                        status = random.choice(statuses)
                        invoice_no = f"INV-{year}{month:02d}-{invoice_count:04d}"
                        invoice_name = f"{source_type.replace('_', ' ').title()} Settlement - {oc} - {inv_date.strftime('%b %Y')}"

                        # Generate line items
                        lines = line_item_templates.get(source_type, line_item_templates['WHOLESALE'])
                        total = 0
                        line_rows = []
                        for idx, (line_name, uom) in enumerate(lines, 1):
                            if uom == 'MWH':
                                qty = round(random.uniform(5000, 150000), 2)
                                rate = round(random.uniform(25, 85), 4)
                            elif uom == 'MW':
                                qty = round(random.uniform(100, 2000), 2)
                                rate = round(random.uniform(5000, 25000), 4)
                            elif uom == 'MMBTU':
                                qty = round(random.uniform(10000, 500000), 2)
                                rate = round(random.uniform(2, 8), 4)
                            elif uom == 'TONS':
                                qty = round(random.uniform(5000, 50000), 2)
                                rate = round(random.uniform(40, 90), 4)
                            else:
                                qty = 1
                                rate = round(random.uniform(10000, 500000), 2)
                            amount = round(qty * rate, 2)
                            if 'Credit' in line_name or 'Sale' in line_name:
                                amount = -abs(amount)
                            total += amount
                            line_rows.append((
                                source_system, source_type, invoice_no,
                                f"{invoice_no}-L{idx:02d}", line_name,
                                uom, qty, rate, amount
                            ))

                        total = round(total, 2)

                        conn.execute("""
                            INSERT INTO invoice_header VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [source_system, source_type, oc, invoice_no, invoice_name,
                              inv_date, status, cp_id, cp_name, total])

                        conn.executemany("""
                            INSERT INTO invoice_detail VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, line_rows)

                        # Add attachments for some invoices
                        if random.random() < 0.6:
                            pdf_content = f"PDF invoice content for {invoice_no}".encode('utf-8')
                            conn.execute("""
                                INSERT INTO invoice_file_attachments VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, [source_system, source_type, invoice_no,
                                  f"{invoice_no}_settlement.pdf", '.pdf',
                                  len(pdf_content), pdf_content])

                        if random.random() < 0.3:
                            xlsx_content = f"Excel backup data for {invoice_no}".encode('utf-8')
                            conn.execute("""
                                INSERT INTO invoice_file_attachments VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, [source_system, source_type, invoice_no,
                                  f"{invoice_no}_detail.xlsx", '.xlsx',
                                  len(xlsx_content), xlsx_content])

        self.stdout.write(f"  Created {invoice_count} invoices with line items and attachments.")

    def _seed_fcs_metrics(self, conn):
        random.seed(99)
        for source_system in ['WHOLESALE_SETTLEMENT', 'POOL_BILL']:
            for year in [2024, 2025]:
                cum_adj = 0
                cum_total = 0
                end_month = 12 if year == 2024 else 3
                for month in range(1, end_month + 1):
                    total_settled = round(random.uniform(50_000_000, 200_000_000), 2)
                    adjustments = round(random.uniform(-2_000_000, 5_000_000), 2)
                    adj_pct = round(adjustments / total_settled * 100, 4) if total_settled else 0
                    cum_adj += adjustments
                    cum_total += total_settled
                    conn.execute("""
                        INSERT INTO fcs_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, [source_system, year, month, adjustments, total_settled,
                          adj_pct, round(cum_adj, 2), round(cum_total, 2)])

        self.stdout.write("  Created FCS metrics data.")

    def _seed_capacity_factors(self, conn):
        random.seed(77)
        resources = {
            'Georgia Power': [
                ('RES-GP01', 'Plant Vogtle Unit 3', 'NUCLEAR'),
                ('RES-GP02', 'Plant Vogtle Unit 4', 'NUCLEAR'),
                ('RES-GP03', 'Plant Scherer Unit 1', 'COAL'),
                ('RES-GP04', 'Plant McDonough Unit 1', 'GAS'),
                ('RES-GP05', 'Plant McDonough Unit 2', 'GAS'),
                ('RES-GP06', 'Nells Solar Farm', 'SOLAR'),
                ('RES-GP07', 'Dalton Solar Farm', 'SOLAR'),
            ],
            'Alabama Power': [
                ('RES-AP01', 'Plant Farley Unit 1', 'NUCLEAR'),
                ('RES-AP02', 'Plant Farley Unit 2', 'NUCLEAR'),
                ('RES-AP03', 'Plant Miller Unit 1', 'COAL'),
                ('RES-AP04', 'Plant Barry Unit 5', 'GAS'),
                ('RES-AP05', 'Cherokee Solar Farm', 'SOLAR'),
            ],
            'Mississippi Power': [
                ('RES-MP01', 'Plant Daniel Unit 1', 'GAS'),
                ('RES-MP02', 'Plant Daniel Unit 2', 'GAS'),
                ('RES-MP03', 'Hattiesburg Solar Farm', 'SOLAR'),
            ],
        }
        hours_map = {1: 744, 2: 672, 3: 744, 4: 720, 5: 744, 6: 720,
                     7: 744, 8: 744, 9: 720, 10: 744, 11: 720, 12: 744}
        rating_map = {'NUCLEAR': (1100, 1200), 'COAL': (800, 900),
                      'GAS': (400, 700), 'SOLAR': (100, 300)}

        for year in [2024, 2025]:
            end_month = 12 if year == 2024 else 3
            for month in range(1, end_month + 1):
                hours = hours_map[month]
                for oc, res_list in resources.items():
                    for res_id, res_name, res_type in res_list:
                        ownership = round(random.uniform(0.5, 1.0), 4)
                        lo, hi = rating_map[res_type]
                        total_rating = round(random.uniform(lo, hi), 2)
                        rating_share = round(total_rating * ownership, 2)
                        total_possible = round(total_rating * hours, 2)

                        if res_type == 'NUCLEAR':
                            bu_cf = round(random.uniform(0.85, 0.95), 4)
                            ac_cf = round(bu_cf + random.uniform(-0.05, 0.05), 4)
                        elif res_type == 'COAL':
                            bu_cf = round(random.uniform(0.55, 0.75), 4)
                            ac_cf = round(bu_cf + random.uniform(-0.10, 0.10), 4)
                        elif res_type == 'GAS':
                            bu_cf = round(random.uniform(0.30, 0.60), 4)
                            ac_cf = round(bu_cf + random.uniform(-0.15, 0.15), 4)
                        else:  # SOLAR
                            bu_cf = round(random.uniform(0.15, 0.30), 4)
                            ac_cf = round(bu_cf + random.uniform(-0.05, 0.08), 4)

                        ac_cf = max(0, min(1, ac_cf))
                        total_gen = round(total_possible * ac_cf, 2)
                        net_gen = round(total_gen * ownership, 2)
                        budget_gen = round(total_possible * bu_cf * ownership, 2)
                        variance = round(ac_cf - bu_cf, 4)

                        conn.execute("""
                            INSERT INTO capacity_factors VALUES
                            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [year, month, oc, res_id, res_name, res_type,
                              ownership, total_gen, net_gen, budget_gen, hours,
                              total_rating, rating_share, total_possible,
                              ac_cf, bu_cf, variance])

        self.stdout.write("  Created capacity factors data.")
