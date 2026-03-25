# CLAUDE.md — Wholesale Settlement Portal (Demo/Pilot)

## Project Overview

This is a **working prototype** of a Wholesale Settlement Portal for **Southern Company**, built to demo to executives. It is **not production-ready** — the goal is to prove the concept of a unified customer-facing portal that consolidates settlement data from multiple legacy on-prem systems into a single view.

Southern Company is a large utility holding company in the Southeast US. Its retail operating subsidiaries include **Georgia Power**, **Mississippi Power**, and **Alabama Power**. The company pools all generation resources and dispatches them as one fleet; the monthly "Pool Bill" settles dollars across operating companies. Wholesale energy contracts, PPAs, and short-term deals are settled monthly by the Financial & Contract Services (FCS) team.

### Business Problem

- Dozens of siloed on-prem apps (settlement, gas accounting, coal accounting, pool bill, resource planning, budgeting, etc.)
- No enterprise data warehouse
- Customers currently have no self-service portal for viewing invoices or settlements
- The same "core" data layer should eventually feed both this portal **and** FERC/regulatory filings

### What This Demo Proves

1. Data from multiple source systems can be consolidated into one unified schema (already done — see DuckDB below).
2. An executive portal can surface invoices, line-item details, file attachments, and operational metrics from that unified layer — filterable by operating company, counterparty, and other dimensions.
3. The architecture is extensible toward a production "core data layer" strategy, including future customer-facing views with row-level security.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.11+ / Django 5.x | Standard Django (no DRF needed for demo unless API endpoints are requested) |
| **Database** | DuckDB (file-based) | All source data already consolidated here. Use `duckdb` Python package as the query engine. For Django ORM models, use SQLite as the Django metadata DB; read DuckDB directly for business data via raw queries or a thin service layer. |
| **Frontend** | Django Templates + Bootstrap 5 (or Tailwind) | Keep it simple — server-rendered HTML. Use Chart.js or Recharts for any dashboards. |
| **Auth** | Django built-in auth | Simple username/password. All users see all data (executive view). No row-level scoping. |
| **File Storage** | BLOBs in DuckDB `invoice_file_attachments` table | Serve via Django view that streams bytes with correct Content-Type. |

---

## Database Schema (DuckDB)

The DuckDB file contains **8 tables**. All data has already been consolidated from the various legacy source systems. The `source_system` and `source_type` columns identify where each record originated.

### `invoice_header`

The master invoice record. One row per invoice.

| Column | Type | Description |
|---|---|---|
| `source_system` | VARCHAR | Originating app (e.g., `'POOL_BILL'`, `'WHOLESALE_SETTLEMENT'`) |
| `source_type` | VARCHAR | Deal/contract type (e.g., `'SHORT_TERM'`, `'PPA'`, `'WHOLESALE'`) |
| `operating_company` | VARCHAR | Subsidiary (`'Georgia Power'`, `'Alabama Power'`, `'Mississippi Power'`) |
| `invoice_no` | VARCHAR | **Primary key** — unique invoice identifier |
| `invoice_name` | VARCHAR | Human-readable invoice description |
| `invoice_date` | TIMESTAMP | Invoice period date |
| `invoice_status` | VARCHAR | Status (e.g., `'FINAL'`, `'DRAFT'`, `'ADJUSTED'`) |
| `counterparty_id` | VARCHAR | Customer identifier — used as a **filter dimension** in views |
| `counterparty_name` | VARCHAR | Customer display name |
| `invoice_total` | DECIMAL(12,2) | Net invoice amount |

### `invoice_detail`

Line-item breakdown for each invoice. Many rows per `invoice_no`.

| Column | Type | Description |
|---|---|---|
| `source_system` | VARCHAR | Originating app |
| `source_type` | VARCHAR | Deal/contract type |
| `invoice_no` | VARCHAR | **FK → invoice_header.invoice_no** |
| `line_id` | VARCHAR | Unique line identifier within the invoice |
| `line_name` | VARCHAR | Description of the charge/credit |
| `uom` | VARCHAR | Unit of measure (`'MWH'`, `'MW'`, `'MMBTU'`, `'$'`, etc.) |
| `quantity` | DECIMAL | Volume/quantity |
| `rate` | DECIMAL | Unit rate/price |
| `amount` | DECIMAL | Line-item dollar amount (`quantity × rate`, or flat) |

### `invoice_file_attachments`

Supporting documents attached to invoices (PDFs, spreadsheets, etc.).

| Column | Type | Description |
|---|---|---|
| `source_system` | VARCHAR | Originating app |
| `source_type` | VARCHAR | Deal/contract type |
| `invoice_no` | VARCHAR | **FK → invoice_header.invoice_no** |
| `file_name` | VARCHAR | Original filename |
| `file_ext` | VARCHAR | Extension (e.g., `'.pdf'`, `'.xlsx'`) |
| `file_size` | INTEGER | Size in bytes |
| `file_contents` | BLOB | Raw file bytes |

### `fcs_metrics`

Monthly departmental KPIs for Financial & Contract Services. Used for internal dashboards (not customer-facing in v1, but useful for executive demo).

| Column | Type | Description |
|---|---|---|
| `source_system` | VARCHAR | Originating app |
| `year` | INTEGER | Calendar year |
| `month` | INTEGER | Calendar month (1–12) |
| `adjustments` | DECIMAL | Dollar adjustments for the month |
| `total_settled` | DECIMAL | Total dollars settled |
| `adjustment_percent` | DECIMAL | `adjustments / total_settled` |
| `cumulative_adjustment` | DECIMAL | Year-to-date adjustments |
| `cumulative_total` | DECIMAL | Year-to-date total settled |

### `capacity_factors`

Generation resource performance data by operating company. Useful for operational dashboards.

| Column | Type | Description |
|---|---|---|
| `year` | INTEGER | Calendar year |
| `month` | INTEGER | Calendar month |
| `operating_company` | VARCHAR | Subsidiary name |
| `resource_id` | VARCHAR | Unique resource identifier |
| `resource_name` | VARCHAR | Plant/unit name |
| `resource_type` | VARCHAR | Fuel type (e.g., `'GAS'`, `'COAL'`, `'NUCLEAR'`, `'SOLAR'`) |
| `ownership_share` | DECIMAL | Ownership percentage |
| `total_net_generation` | DECIMAL | Total MWh generated (100% basis) |
| `net_generation` | DECIMAL | MWh at ownership share |
| `budget_generation` | DECIMAL | Budgeted MWh |
| `hours_in_month` | INTEGER | Hours in the calendar month |
| `total_rating_mw` | DECIMAL | Nameplate capacity (MW) |
| `rating_mw_share` | DECIMAL | Capacity at ownership share |
| `total_mwh_possible` | DECIMAL | Max possible generation |
| `ac_capacity_factor` | DECIMAL | Actual capacity factor |
| `bu_capacity_factor` | DECIMAL | Budget capacity factor |
| `capacity_factor_variance` | DECIMAL | Actual − Budget variance |

### `avg_interchange_rate`

Average associated interchange rates by month. Used for tracking wholesale interchange pricing trends.

| Column | Type | Description |
|---|---|---|
| `year` | INTEGER | Calendar year |
| `month` | INTEGER | Calendar month (1–12) |
| `dt` | TIMESTAMP | Date timestamp for the record |
| `avg_associated_interchange_rate` | DECIMAL | Average interchange rate for the period |

### `weather`

Historical weather data including temperature and degree-day metrics. Useful for correlating energy demand with weather patterns.

| Column | Type | Description |
|---|---|---|
| `dt` | TIMESTAMP | Date timestamp |
| `year` | INTEGER | Calendar year |
| `qtr` | INTEGER | Calendar quarter (1–4) |
| `month` | INTEGER | Calendar month (1–12) |
| `day` | INTEGER | Day of month |
| `average_temp` | DECIMAL | Average temperature for the day |
| `cooling_degree_days` | DECIMAL | Cooling degree days |
| `heating_degree_days` | DECIMAL | Heating degree days |
| `cooling_degree_hours` | DECIMAL | Cooling degree hours |
| `heating_degree_hours` | DECIMAL | Heating degree hours |

### `profit_and_loss_statement`

Profit and loss statement data from various sources. Supports financial analysis across entities, categories, and allocation dimensions.

| Column | Type | Description |
|---|---|---|
| `short_desc` | VARCHAR | Short description of the P&L entry |
| `source` | VARCHAR | Data source identifier |
| `year` | INTEGER | Calendar year |
| `month` | INTEGER | Calendar month (1–12) |
| `dt` | TIMESTAMP | Date timestamp |
| `entity_class` | VARCHAR | Entity classification (e.g., operating company type) |
| `entity_name` | VARCHAR | Entity name |
| `covered_or_uncovered` | VARCHAR | Whether the item is covered or uncovered |
| `allocation_name` | VARCHAR | Name of the cost allocation |
| `category` | VARCHAR | P&L category |
| `type` | VARCHAR | Entry type |
| `subtype` | VARCHAR | Entry subtype |
| `line_item` | VARCHAR | Specific line item description |
| `legacy_subtype` | VARCHAR | Legacy system subtype mapping |
| `tag` | VARCHAR | Additional classification tag |
| `ledger` | VARCHAR | Ledger identifier |
| `amount` | DECIMAL | Dollar amount |

---

## Architecture Pattern

```
┌──────────────────────────────────────────────────────┐
│                   Django App                         │
│                                                      │
│  ┌────────────┐   ┌─────────────┐   ┌────────────┐  │
│  │  Templates  │   │    Views    │   │  Django ORM │  │
│  │ (Bootstrap) │◄──│ (Controllers│──►│  (SQLite -  │  │
│  └────────────┘   │  + Auth)    │   │  auth/users)│  │
│                    └──────┬──────┘   └────────────┘  │
│                           │                          │
│                    ┌──────▼──────┐                    │
│                    │  Data Layer │                    │
│                    │  (Services) │                    │
│                    └──────┬──────┘                    │
│                           │                          │
└───────────────────────────┼──────────────────────────┘
                            │
                     ┌──────▼──────┐
                     │   DuckDB    │
                     │  (file.db)  │
                     └─────────────┘
```

### Key Design Decisions

1. **Django ORM for auth only.** User accounts, sessions, and permissions live in SQLite via Django's standard ORM. Business data lives in DuckDB and is queried through a service layer.

2. **Service layer pattern.** Create a `services/duckdb_service.py` module that:
   - Opens a read-only DuckDB connection
   - Exposes methods like `get_invoices(filters)`, `get_invoice_detail(invoice_no)`, `get_attachment(invoice_no, file_name)`, etc.
   - All list/query methods accept optional filter kwargs: `operating_company`, `counterparty_id`, `source_system`, `source_type`, `date_from`, `date_to`, `status`
   - Returns Python dicts or dataclass instances (not Django model instances)

3. **Executive view — no row-level security.** All logged-in users see all data across all operating companies and counterparties. Every list view provides **filter dropdowns** for operating company, counterparty, source system, source type, date range, and status. Filters are passed as GET query parameters and applied dynamically in the service layer SQL via optional WHERE clauses.

4. **No REST API needed for demo.** Standard Django views returning HTML. If requested later, add DRF serializers on top of the same service layer.

---

## Project Structure

```
wholesale_portal/
├── CLAUDE.md                    # This file
├── manage.py
├── data/
│   └── wholesale.duckdb         # The consolidated DuckDB database
├── wholesale_portal/            # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── portal/                      # Main Django app
│   ├── models.py                # Minimal — no custom models needed for demo
│   ├── views.py                 # Page views
│   ├── urls.py                  # App URL routing
│   ├── services/
│   │   └── duckdb_service.py    # All DuckDB queries live here
│   ├── templatetags/
│   │   └── portal_filters.py    # Custom template filters (currency, dates)
│   ├── templates/
│   │   └── portal/
│   │       ├── base.html        # Base layout (nav, footer, branding)
│   │       ├── login.html
│   │       ├── dashboard.html   # Landing page after login
│   │       ├── invoices.html    # Invoice list with filters
│   │       ├── invoice_detail.html  # Single invoice + line items
│   │       ├── metrics.html     # FCS metrics dashboard (internal)
│   │       └── capacity.html    # Capacity factor dashboard
│   └── static/
│       └── portal/
│           ├── css/
│           └── js/
└── requirements.txt
```

---

## Key Pages & Features

### 1. Login (`/login/`)
- Standard Django auth login form
- Branded with Southern Company styling

### 2. Dashboard (`/dashboard/`)
- Executive overview of all wholesale settlement activity
- Summary cards: total invoices, total settled amount, recent invoices count, count by operating company
- Filters: operating company, counterparty (dropdowns populated from data)
- Quick links to invoice list, metrics, capacity factors

### 3. Invoice List (`/invoices/`)
- Filterable table of **all invoices** across all operating companies and counterparties
- Filters: operating company, counterparty, date range, source system, source type, status
- All filters are optional; default view shows everything
- Sortable columns
- Click row → invoice detail page
- Export to CSV button

### 4. Invoice Detail (`/invoices/<invoice_no>/`)
- Header info (counterparty, date, status, total, source system)
- Line-item detail table
- Attachments list with download links
- Print-friendly view

### 5. FCS Metrics Dashboard (`/metrics/`)
- Monthly adjustment trends (Chart.js line chart)
- Cumulative settlement totals
- Adjustment percentage tracking
- Filters: source system, year

### 6. Capacity Factors (`/capacity/`)
- Resource performance table with budget vs actual
- Filters: operating company, resource type, year/month
- Capacity factor variance highlighting (red/green)

---

## Development Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install django duckdb

# Initialize Django
python manage.py migrate          # Creates SQLite for auth
python manage.py createsuperuser  # Admin/demo account

# Run
python manage.py runserver
```

---

## Coding Conventions

- **Python**: Follow PEP 8. Use type hints in the service layer.
- **Templates**: Use Django template inheritance. `base.html` defines blocks: `title`, `content`, `extra_js`.
- **SQL**: Write all DuckDB queries in `duckdb_service.py` using parameterized queries (never string interpolation with user input).
- **Error handling**: Wrap DuckDB calls in try/except; return empty results on failure with logging.
- **Date formatting**: Display all dates as `MMM YYYY` (e.g., `Jan 2025`) unless day precision is needed.
- **Currency formatting**: Use locale-aware formatting or `${:,.2f}` pattern. All amounts are USD.
- **Naming**: snake_case for Python, kebab-case for CSS classes, camelCase for JS.

---

## Security Notes (Demo Scope)

- **No row-level security in this demo.** All logged-in users see all data. This is intentional — the demo is presented from an executive/admin perspective.
- Use Django's `@login_required` decorator on all views to prevent unauthenticated access.
- CSRF protection is enabled by default — keep it on.
- **Future production note:** Row-level scoping by `counterparty_id` should be added when this becomes a customer-facing portal. The service layer's filter-based architecture makes this straightforward — just make `counterparty_id` a required (non-optional) parameter for customer-role users.

---

## Future / Out of Scope for Demo

- REST API layer (DRF) for mobile or SPA frontends
- FERC/regulatory filing module (same core data, different views)
- Real authentication (SSO/SAML with corporate IdP)
- Migration from DuckDB to a proper data warehouse (Snowflake, Databricks, etc.)
- Role-based access control (executive vs. customer views with counterparty-scoped row-level security)
- Email notifications for new invoices
- Audit logging
- Data refresh pipeline from legacy source systems

---

## Sample Queries (DuckDB)

```sql
-- All invoices (executive view, no scoping — apply optional filters dynamically)
SELECT * FROM invoice_header
WHERE 1=1
  -- AND operating_company = ? (optional filter)
  -- AND counterparty_id = ?   (optional filter)
  -- AND source_system = ?     (optional filter)
  -- AND source_type = ?       (optional filter)
  -- AND invoice_status = ?    (optional filter)
  -- AND invoice_date BETWEEN ? AND ? (optional date range)
ORDER BY invoice_date DESC;

-- Line items for a specific invoice
SELECT * FROM invoice_detail
WHERE invoice_no = ?
ORDER BY line_id;

-- Attachments for an invoice
SELECT file_name, file_ext, file_size
FROM invoice_file_attachments
WHERE invoice_no = ?;

-- Download a specific attachment (returns BLOB)
SELECT file_contents, file_ext
FROM invoice_file_attachments
WHERE invoice_no = ? AND file_name = ?;

-- FCS metrics for a year
SELECT * FROM fcs_metrics
WHERE year = ?
ORDER BY month;

-- Capacity factors (with optional operating company filter)
SELECT * FROM capacity_factors
WHERE 1=1
  -- AND operating_company = ? (optional filter)
  -- AND resource_type = ?     (optional filter)
  AND year = ? AND month = ?
ORDER BY resource_name;

-- Populate filter dropdowns (call once on page load or cache)
SELECT DISTINCT operating_company FROM invoice_header ORDER BY operating_company;
SELECT DISTINCT counterparty_id, counterparty_name FROM invoice_header ORDER BY counterparty_name;
SELECT DISTINCT source_system FROM invoice_header ORDER BY source_system;
SELECT DISTINCT source_type FROM invoice_header ORDER BY source_type;
SELECT DISTINCT invoice_status FROM invoice_header ORDER BY invoice_status;

-- Dashboard summary (executive — all data, with optional filters)
SELECT
    COUNT(*) AS total_invoices,
    SUM(invoice_total) AS total_amount,
    COUNT(*) FILTER (WHERE invoice_date >= CURRENT_DATE - INTERVAL '30 days') AS recent_invoices
FROM invoice_header
WHERE 1=1;
  -- AND operating_company = ? (optional filter)
  -- AND counterparty_id = ?   (optional filter)

-- Average interchange rates for a year
SELECT * FROM avg_interchange_rate
WHERE year = ?
ORDER BY month;

-- Weather data for a date range
SELECT * FROM weather
WHERE year = ? AND month = ?
ORDER BY dt;

-- Weather degree-day summary by month
SELECT year, month,
       AVG(average_temp) AS avg_temp,
       SUM(cooling_degree_days) AS total_cdd,
       SUM(heating_degree_days) AS total_hdd
FROM weather
WHERE year = ?
GROUP BY year, month
ORDER BY year, month;

-- Profit & loss statement (with optional filters)
SELECT * FROM profit_and_loss_statement
WHERE 1=1
  -- AND entity_name = ?           (optional filter)
  -- AND category = ?              (optional filter)
  -- AND covered_or_uncovered = ?  (optional filter)
  AND year = ? AND month = ?
ORDER BY entity_name, category, type, subtype;

-- P&L summary by category
SELECT category, type, SUM(amount) AS total_amount
FROM profit_and_loss_statement
WHERE year = ? AND month = ?
GROUP BY category, type
ORDER BY category, type;
```

---

## LLM Assistant Notes

When generating code for this project:

1. **Always use the service layer** — never put raw DuckDB SQL in views or templates.
2. **All views show all data by default** — no row-level security. Filters (operating company, counterparty, source system, source type, date range, status) are optional and passed as GET query params.
3. **Build filters dynamically in SQL** — the service layer should construct WHERE clauses from a `filters: dict` parameter, only adding conditions for keys that are present. Use parameterized queries — never string-interpolate user input.
4. **Populate filter dropdowns from data** — query distinct values from DuckDB for each filter dimension. Cache these if performance matters, but for the demo, querying each page load is fine.
5. **The DuckDB file path** should be configurable via `settings.py` (e.g., `DUCKDB_PATH = BASE_DIR / 'data' / 'wholesale.duckdb'`).
6. **DuckDB connections are cheap** — open per-request in the service layer, don't try to pool them.
7. **For the demo, seed data matters** — if the DuckDB file doesn't exist or is empty, provide a management command to generate realistic sample data.
8. **Keep the UI professional but simple** — this is an executive demo for a utility company. Use a clean, corporate color scheme (Southern Company brand blue: `#00205B`, accent: `#6CACE4`). No flashy animations.
9. **Chart.js is preferred** for any data visualizations in templates.
