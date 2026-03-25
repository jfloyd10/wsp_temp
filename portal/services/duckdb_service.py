"""DuckDB service layer — all business data queries live here."""

import logging
from typing import Optional

import duckdb
from django.conf import settings

logger = logging.getLogger(__name__)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Open a read-only DuckDB connection using settings.DUCKDB_PATH."""
    return duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)


def _build_where(filters: dict, column_map: dict) -> tuple[str, list]:
    """Build a dynamic WHERE clause from filters using parameterized queries."""
    conditions = []
    params = []
    for key, column in column_map.items():
        if key in filters and filters[key]:
            conditions.append(f"{column} = ?")
            params.append(filters[key])
    if filters.get('date_from'):
        conditions.append("invoice_date >= ?")
        params.append(filters['date_from'])
    if filters.get('date_to'):
        conditions.append("invoice_date <= ?")
        params.append(filters['date_to'])
    if filters.get('search'):
        search_term = f"%{filters['search']}%"
        conditions.append("(invoice_no ILIKE ? OR counterparty_name ILIKE ?)")
        params.extend([search_term, search_term])
    where = " AND ".join(conditions)
    return (f"WHERE {where}" if where else ""), params


def get_filter_options() -> dict:
    """Return distinct values for all filter dimensions."""
    try:
        conn = get_connection()
        result = {}
        result['operating_companies'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT operating_company FROM invoice_header ORDER BY operating_company"
            ).fetchall()
        ]
        result['counterparties'] = [
            {'id': r[0], 'name': r[1]} for r in conn.execute(
                "SELECT DISTINCT counterparty_id, counterparty_name FROM invoice_header ORDER BY counterparty_name"
            ).fetchall()
        ]
        result['source_systems'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT source_system FROM invoice_header ORDER BY source_system"
            ).fetchall()
        ]
        result['source_types'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT source_type FROM invoice_header ORDER BY source_type"
            ).fetchall()
        ]
        result['statuses'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT invoice_status FROM invoice_header ORDER BY invoice_status"
            ).fetchall()
        ]
        result['years'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT year FROM fcs_metrics ORDER BY year DESC"
            ).fetchall()
        ]
        result['resource_types'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT resource_type FROM capacity_factors ORDER BY resource_type"
            ).fetchall()
        ]
        result['months'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT month FROM capacity_factors ORDER BY month"
            ).fetchall()
        ]
        conn.close()
        return result
    except Exception:
        logger.exception("Error fetching filter options")
        return {
            'operating_companies': [], 'counterparties': [], 'source_systems': [],
            'source_types': [], 'statuses': [], 'years': [], 'resource_types': [],
            'months': [],
        }


INVOICE_COLUMN_MAP = {
    'operating_company': 'operating_company',
    'counterparty_id': 'counterparty_id',
    'source_system': 'source_system',
    'source_type': 'source_type',
    'invoice_status': 'invoice_status',
}


def get_invoices(filters: dict) -> list[dict]:
    """Return invoice_header rows with optional filtering."""
    try:
        conn = get_connection()
        where, params = _build_where(filters, INVOICE_COLUMN_MAP)
        sql = f"""
            SELECT source_system, source_type, operating_company, invoice_no,
                   invoice_name, invoice_date, invoice_status, counterparty_id,
                   counterparty_name, invoice_total
            FROM invoice_header
            {where}
            ORDER BY invoice_date DESC, invoice_no
        """
        rows = conn.execute(sql, params).fetchall()
        columns = ['source_system', 'source_type', 'operating_company', 'invoice_no',
                    'invoice_name', 'invoice_date', 'invoice_status', 'counterparty_id',
                    'counterparty_name', 'invoice_total']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching invoices")
        return []


def get_invoices_paginated(filters: dict, page: int = 1, per_page: int = 50) -> dict:
    """Return paginated invoice_header rows with total count and summary amount."""
    try:
        conn = get_connection()
        where, params = _build_where(filters, INVOICE_COLUMN_MAP)

        # Get total count and sum in one query
        summary_row = conn.execute(f"""
            SELECT COUNT(*) AS total_count, COALESCE(SUM(invoice_total), 0) AS total_amount
            FROM invoice_header {where}
        """, params).fetchone()
        total_count = summary_row[0]
        total_amount = float(summary_row[1])

        # Fetch the page of results
        offset = (page - 1) * per_page
        sql = f"""
            SELECT source_system, source_type, operating_company, invoice_no,
                   invoice_name, invoice_date, invoice_status, counterparty_id,
                   counterparty_name, invoice_total
            FROM invoice_header
            {where}
            ORDER BY invoice_date DESC, invoice_no
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, params + [per_page, offset]).fetchall()
        columns = ['source_system', 'source_type', 'operating_company', 'invoice_no',
                    'invoice_name', 'invoice_date', 'invoice_status', 'counterparty_id',
                    'counterparty_name', 'invoice_total']
        conn.close()

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        return {
            'invoices': [dict(zip(columns, row)) for row in rows],
            'total_count': total_count,
            'total_amount': total_amount,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_previous': page > 1,
            'has_next': page < total_pages,
        }
    except Exception:
        logger.exception("Error fetching paginated invoices")
        return {
            'invoices': [], 'total_count': 0, 'total_amount': 0,
            'page': 1, 'per_page': per_page, 'total_pages': 1,
            'has_previous': False, 'has_next': False,
        }


def get_invoice_detail(invoice_no: str) -> dict:
    """Return invoice header + line items + attachment metadata for one invoice."""
    try:
        conn = get_connection()

        # Header
        header_row = conn.execute("""
            SELECT source_system, source_type, operating_company, invoice_no,
                   invoice_name, invoice_date, invoice_status, counterparty_id,
                   counterparty_name, invoice_total
            FROM invoice_header WHERE invoice_no = ?
        """, [invoice_no]).fetchone()

        if not header_row:
            conn.close()
            return {'header': None, 'lines': [], 'attachments': []}

        header_cols = ['source_system', 'source_type', 'operating_company', 'invoice_no',
                       'invoice_name', 'invoice_date', 'invoice_status', 'counterparty_id',
                       'counterparty_name', 'invoice_total']
        header = dict(zip(header_cols, header_row))

        # Line items
        line_rows = conn.execute("""
            SELECT line_id, line_name, uom, quantity, rate, amount
            FROM invoice_detail WHERE invoice_no = ? ORDER BY line_id
        """, [invoice_no]).fetchall()
        line_cols = ['line_id', 'line_name', 'uom', 'quantity', 'rate', 'amount']
        lines = [dict(zip(line_cols, row)) for row in line_rows]

        # Attachments (metadata only, not blob)
        att_rows = conn.execute("""
            SELECT file_name, file_ext, file_size
            FROM invoice_file_attachments WHERE invoice_no = ? ORDER BY file_name
        """, [invoice_no]).fetchall()
        att_cols = ['file_name', 'file_ext', 'file_size']
        attachments = [dict(zip(att_cols, row)) for row in att_rows]

        conn.close()
        return {'header': header, 'lines': lines, 'attachments': attachments}
    except Exception:
        logger.exception("Error fetching invoice detail")
        return {'header': None, 'lines': [], 'attachments': []}


def get_attachment(invoice_no: str, file_name: str) -> Optional[tuple[bytes, str]]:
    """Return (file_contents_bytes, file_extension) for download."""
    try:
        conn = get_connection()
        row = conn.execute("""
            SELECT file_contents, file_ext
            FROM invoice_file_attachments
            WHERE invoice_no = ? AND file_name = ?
        """, [invoice_no, file_name]).fetchone()
        conn.close()
        if row:
            return (bytes(row[0]), row[1])
        return None
    except Exception:
        logger.exception("Error fetching attachment")
        return None


def get_dashboard_summary(filters: dict) -> dict:
    """Return aggregate stats for the dashboard."""
    try:
        conn = get_connection()
        where, params = _build_where(filters, INVOICE_COLUMN_MAP)

        summary_row = conn.execute(f"""
            SELECT
                COUNT(*) AS total_invoices,
                COALESCE(SUM(invoice_total), 0) AS total_amount,
                COUNT(*) FILTER (WHERE invoice_date >= CURRENT_DATE - INTERVAL '30 days') AS recent_invoices
            FROM invoice_header
            {where}
        """, params).fetchone()

        breakdown_rows = conn.execute(f"""
            SELECT operating_company, COUNT(*) as cnt, COALESCE(SUM(invoice_total), 0) as total
            FROM invoice_header
            {where}
            GROUP BY operating_company
            ORDER BY operating_company
        """, params).fetchall()

        conn.close()
        return {
            'total_invoices': summary_row[0],
            'total_amount': summary_row[1],
            'recent_invoices': summary_row[2],
            'by_operating_company': [
                {'name': r[0], 'count': r[1], 'total': r[2]}
                for r in breakdown_rows
            ],
            'operating_company_count': len(breakdown_rows),
        }
    except Exception:
        logger.exception("Error fetching dashboard summary")
        return {
            'total_invoices': 0, 'total_amount': 0, 'recent_invoices': 0,
            'by_operating_company': [], 'operating_company_count': 0,
        }


def get_fcs_metrics(filters: dict) -> list[dict]:
    """Return fcs_metrics rows with optional filters."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('source_system'):
            conditions.append("source_system = ?")
            params.append(filters['source_system'])
        if filters.get('year'):
            conditions.append("year = ?")
            params.append(int(filters['year']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT source_system, year, month, adjustments, total_settled,
                   adjustment_percent, cumulative_adjustment, cumulative_total
            FROM fcs_metrics
            {where}
            ORDER BY year, month
        """, params).fetchall()
        columns = ['source_system', 'year', 'month', 'adjustments', 'total_settled',
                    'adjustment_percent', 'cumulative_adjustment', 'cumulative_total']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching FCS metrics")
        return []


def get_trading_analytics(filters: dict) -> list[dict]:
    """Return trading_analytics rows with optional filters."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT dt, deal_no, trading_group, employee_name,
                   issue_description, issue_category, issue_reason
            FROM trading_analytics
            {where}
            ORDER BY dt DESC, deal_no
        """, params).fetchall()

        columns = ['dt', 'deal_no', 'trading_group', 'employee_name',
                    'issue_description', 'issue_category', 'issue_reason']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching trading analytics")
        return []


def get_trading_analytics_filter_options() -> dict:
    """Return distinct values for trading analytics filter dimensions."""
    try:
        conn = get_connection()
        result = {}
        result['trading_groups'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT trading_group FROM trading_analytics ORDER BY trading_group"
            ).fetchall()
        ]
        result['employees'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT employee_name FROM trading_analytics ORDER BY employee_name"
            ).fetchall()
        ]
        result['issue_categories'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT issue_category FROM trading_analytics ORDER BY issue_category"
            ).fetchall()
        ]
        result['years'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT YEAR(dt) AS yr FROM trading_analytics ORDER BY yr DESC"
            ).fetchall()
        ]
        conn.close()
        return result
    except Exception:
        logger.exception("Error fetching trading analytics filter options")
        return {'trading_groups': [], 'employees': [], 'issue_categories': [], 'years': []}


def get_trading_analytics_summary_by_category(filters: dict) -> list[dict]:
    """Return issue counts grouped by issue_category."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT issue_category, COUNT(*) AS issue_count
            FROM trading_analytics
            {where}
            GROUP BY issue_category
            ORDER BY issue_count DESC
        """, params).fetchall()
        conn.close()
        return [dict(zip(['issue_category', 'issue_count'], r)) for r in rows]
    except Exception:
        logger.exception("Error fetching trading analytics summary by category")
        return []


def get_trading_analytics_summary_by_employee(filters: dict) -> list[dict]:
    """Return issue counts grouped by employee and trading group."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT employee_name, trading_group, COUNT(*) AS issue_count
            FROM trading_analytics
            {where}
            GROUP BY employee_name, trading_group
            ORDER BY issue_count DESC
        """, params).fetchall()
        conn.close()
        return [dict(zip(['employee_name', 'trading_group', 'issue_count'], r)) for r in rows]
    except Exception:
        logger.exception("Error fetching trading analytics summary by employee")
        return []


def get_trading_analytics_monthly_trend(filters: dict) -> list[dict]:
    """Return monthly issue counts for trend chart."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT YEAR(dt) AS year, MONTH(dt) AS month, COUNT(*) AS issue_count
            FROM trading_analytics
            {where}
            GROUP BY YEAR(dt), MONTH(dt)
            ORDER BY year, month
        """, params).fetchall()
        conn.close()
        return [dict(zip(['year', 'month', 'issue_count'], r)) for r in rows]
    except Exception:
        logger.exception("Error fetching trading analytics monthly trend")
        return []


def get_trading_analytics_by_group(filters: dict) -> list[dict]:
    """Return issue counts grouped by trading group."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT trading_group, COUNT(*) AS issue_count
            FROM trading_analytics
            {where}
            GROUP BY trading_group
            ORDER BY issue_count DESC
        """, params).fetchall()
        conn.close()
        return [dict(zip(['trading_group', 'issue_count'], r)) for r in rows]
    except Exception:
        logger.exception("Error fetching trading analytics by group")
        return []


def get_trading_analytics_category_by_month(filters: dict) -> list[dict]:
    """Return issue counts grouped by month and category for stacked chart."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('trading_group'):
            conditions.append("trading_group = ?")
            params.append(filters['trading_group'])
        if filters.get('employee_name'):
            conditions.append("employee_name = ?")
            params.append(filters['employee_name'])
        if filters.get('issue_category'):
            conditions.append("issue_category = ?")
            params.append(filters['issue_category'])
        if filters.get('year'):
            conditions.append("YEAR(dt) = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("MONTH(dt) = ?")
            params.append(int(filters['month']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT YEAR(dt) AS year, MONTH(dt) AS month, issue_category, COUNT(*) AS issue_count
            FROM trading_analytics
            {where}
            GROUP BY YEAR(dt), MONTH(dt), issue_category
            ORDER BY year, month, issue_category
        """, params).fetchall()
        conn.close()
        return [dict(zip(['year', 'month', 'issue_category', 'issue_count'], r)) for r in rows]
    except Exception:
        logger.exception("Error fetching trading analytics category by month")
        return []


def get_capacity_factors(filters: dict) -> list[dict]:
    """Return capacity_factors rows with optional filters."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        col_map = {
            'operating_company': 'operating_company',
            'resource_type': 'resource_type',
        }
        for key, col in col_map.items():
            if filters.get(key):
                conditions.append(f"{col} = ?")
                params.append(filters[key])
        if filters.get('year'):
            conditions.append("year = ?")
            params.append(int(filters['year']))
        if filters.get('month'):
            conditions.append("month = ?")
            params.append(int(filters['month']))

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT year, month, operating_company, resource_id, resource_name,
                   resource_type, ownership_share, total_net_generation,
                   net_generation, budget_generation, hours_in_month,
                   total_rating_mw, rating_mw_share, total_mwh_possible,
                   ac_capacity_factor, bu_capacity_factor, capacity_factor_variance
            FROM capacity_factors
            {where}
            ORDER BY operating_company, resource_name, year, month
        """, params).fetchall()

        columns = ['year', 'month', 'operating_company', 'resource_id', 'resource_name',
                    'resource_type', 'ownership_share', 'total_net_generation',
                    'net_generation', 'budget_generation', 'hours_in_month',
                    'total_rating_mw', 'rating_mw_share', 'total_mwh_possible',
                    'ac_capacity_factor', 'bu_capacity_factor', 'capacity_factor_variance']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching capacity factors")
        return []


def get_weather_monthly_summary(filters: dict) -> list[dict]:
    """Return monthly weather summary with avg temp and degree days."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('year'):
            conditions.append("year = ?")
            params.append(int(filters['year']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT year, month,
                   ROUND(AVG(average_temp), 1) AS avg_temp,
                   ROUND(SUM(cooling_degree_days), 1) AS total_cdd,
                   ROUND(SUM(heating_degree_days), 1) AS total_hdd
            FROM weather
            {where}
            GROUP BY year, month
            ORDER BY year, month
        """, params).fetchall()
        columns = ['year', 'month', 'avg_temp', 'total_cdd', 'total_hdd']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching weather monthly summary")
        return []


def get_weather_years() -> list[int]:
    """Return distinct years from weather data."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT DISTINCT year FROM weather ORDER BY year DESC"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        logger.exception("Error fetching weather years")
        return []


def get_avg_interchange_rates(filters: dict) -> list[dict]:
    """Return average interchange rate data with optional year filter."""
    try:
        conn = get_connection()
        conditions = []
        params = []
        if filters.get('year'):
            conditions.append("year = ?")
            params.append(int(filters['year']))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT year, month, dt, avg_associated_interchange_rate
            FROM avg_interchange_rate
            {where}
            ORDER BY year, month
        """, params).fetchall()
        columns = ['year', 'month', 'dt', 'avg_associated_interchange_rate']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching avg interchange rates")
        return []


def get_interchange_rate_years() -> list[int]:
    """Return distinct years from avg_interchange_rate data."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT DISTINCT year FROM avg_interchange_rate ORDER BY year DESC"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        logger.exception("Error fetching interchange rate years")
        return []


def get_platform_overview() -> dict:
    """Return summary counts/stats across all 9 data tables for the platform overview dashboard."""
    try:
        conn = get_connection()

        # Invoice stats
        inv_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(invoice_total), 0) AS total,
                   COUNT(DISTINCT operating_company) AS opcos,
                   COUNT(DISTINCT counterparty_id) AS counterparties,
                   COUNT(DISTINCT source_system) AS sources
            FROM invoice_header
        """).fetchone()

        # FCS metrics stats
        fcs_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(total_settled), 0) AS total_settled,
                   COALESCE(AVG(adjustment_percent), 0) AS avg_adj_pct
            FROM fcs_metrics
        """).fetchone()

        # Capacity factors stats
        cap_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COUNT(DISTINCT resource_name) AS resources,
                   COUNT(DISTINCT resource_type) AS fuel_types,
                   COALESCE(AVG(ac_capacity_factor), 0) AS avg_cf
            FROM capacity_factors
        """).fetchone()

        # Weather stats
        weather_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COALESCE(AVG(average_temp), 0) AS avg_temp,
                   MIN(year) AS min_year, MAX(year) AS max_year
            FROM weather
        """).fetchone()

        # Interchange rate stats
        ir_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COALESCE(AVG(avg_associated_interchange_rate), 0) AS avg_rate,
                   MIN(year) AS min_year, MAX(year) AS max_year
            FROM avg_interchange_rate
        """).fetchone()

        # P&L stats
        pnl_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COUNT(DISTINCT entity_name) AS entities,
                   COUNT(DISTINCT category) AS categories
            FROM profit_and_loss_statement
        """).fetchone()

        # Trading analytics stats
        ta_row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   COUNT(DISTINCT employee_name) AS traders,
                   COUNT(DISTINCT issue_category) AS categories
            FROM trading_analytics
        """).fetchone()

        # Capacity by resource type (for donut chart)
        cap_by_type = conn.execute("""
            SELECT resource_type, COUNT(DISTINCT resource_name) AS cnt
            FROM capacity_factors
            GROUP BY resource_type
            ORDER BY cnt DESC
        """).fetchall()

        # Invoices by operating company
        inv_by_opco = conn.execute("""
            SELECT operating_company, COUNT(*) AS cnt, COALESCE(SUM(invoice_total), 0) AS total
            FROM invoice_header
            GROUP BY operating_company
            ORDER BY total DESC
        """).fetchall()

        # Trading issues by category
        ta_by_cat = conn.execute("""
            SELECT issue_category, COUNT(*) AS cnt
            FROM trading_analytics
            GROUP BY issue_category
            ORDER BY cnt DESC
        """).fetchall()

        # Invoices by status
        inv_by_status = conn.execute("""
            SELECT invoice_status, COUNT(*) AS cnt
            FROM invoice_header
            GROUP BY invoice_status
            ORDER BY cnt DESC
        """).fetchall()

        conn.close()
        return {
            'invoices': {
                'count': inv_row[0], 'total': inv_row[1], 'opcos': inv_row[2],
                'counterparties': inv_row[3], 'sources': inv_row[4],
            },
            'fcs': {
                'count': fcs_row[0], 'total_settled': fcs_row[1], 'avg_adj_pct': fcs_row[2],
            },
            'capacity': {
                'count': cap_row[0], 'resources': cap_row[1],
                'fuel_types': cap_row[2], 'avg_cf': cap_row[3],
            },
            'weather': {
                'count': weather_row[0], 'avg_temp': weather_row[1],
                'min_year': weather_row[2], 'max_year': weather_row[3],
            },
            'interchange': {
                'count': ir_row[0], 'avg_rate': ir_row[1],
                'min_year': ir_row[2], 'max_year': ir_row[3],
            },
            'pnl': {
                'count': pnl_row[0], 'entities': pnl_row[1], 'categories': pnl_row[2],
            },
            'trading': {
                'count': ta_row[0], 'traders': ta_row[1], 'categories': ta_row[2],
            },
            'cap_by_type': [{'type': r[0], 'count': r[1]} for r in cap_by_type],
            'inv_by_opco': [{'name': r[0], 'count': r[1], 'total': r[2]} for r in inv_by_opco],
            'ta_by_category': [{'category': r[0], 'count': r[1]} for r in ta_by_cat],
            'inv_by_status': [{'status': r[0], 'count': r[1]} for r in inv_by_status],
        }
    except Exception:
        logger.exception("Error fetching platform overview")
        return {
            'invoices': {'count': 0, 'total': 0, 'opcos': 0, 'counterparties': 0, 'sources': 0},
            'fcs': {'count': 0, 'total_settled': 0, 'avg_adj_pct': 0},
            'capacity': {'count': 0, 'resources': 0, 'fuel_types': 0, 'avg_cf': 0},
            'weather': {'count': 0, 'avg_temp': 0, 'min_year': 0, 'max_year': 0},
            'interchange': {'count': 0, 'avg_rate': 0, 'min_year': 0, 'max_year': 0},
            'pnl': {'count': 0, 'entities': 0, 'categories': 0},
            'trading': {'count': 0, 'traders': 0, 'categories': 0},
            'cap_by_type': [], 'inv_by_opco': [], 'ta_by_category': [], 'inv_by_status': [],
        }


def get_pnl_filter_options() -> dict:
    """Return distinct values for P&L filter dimensions."""
    try:
        conn = get_connection()
        result = {}
        result['entities'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT entity_name FROM profit_and_loss_statement ORDER BY entity_name"
            ).fetchall()
        ]
        result['entity_classes'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT entity_class FROM profit_and_loss_statement ORDER BY entity_class"
            ).fetchall()
        ]
        result['years'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT year FROM profit_and_loss_statement ORDER BY year DESC"
            ).fetchall()
        ]
        result['months'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT month FROM profit_and_loss_statement ORDER BY month"
            ).fetchall()
        ]
        result['categories'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT category FROM profit_and_loss_statement ORDER BY category"
            ).fetchall()
        ]
        result['covered_uncovered'] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT covered_or_uncovered FROM profit_and_loss_statement ORDER BY covered_or_uncovered"
            ).fetchall()
        ]
        conn.close()
        return result
    except Exception:
        logger.exception("Error fetching P&L filter options")
        return {
            'entities': [], 'entity_classes': [], 'years': [],
            'months': [], 'categories': [], 'covered_uncovered': [],
        }


PNL_COLUMN_MAP = {
    'entity_name': 'entity_name',
    'entity_class': 'entity_class',
    'category': 'category',
    'covered_or_uncovered': 'covered_or_uncovered',
}


def _build_pnl_where(filters: dict) -> tuple[str, list]:
    """Build WHERE clause for P&L queries."""
    conditions = []
    params = []
    for key, col in PNL_COLUMN_MAP.items():
        if filters.get(key):
            conditions.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get('year'):
        conditions.append("year = ?")
        params.append(int(filters['year']))
    if filters.get('month'):
        conditions.append("month = ?")
        params.append(int(filters['month']))
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


def get_pnl_income_statement(filters: dict) -> list[dict]:
    """Return P&L data grouped by category, type, subtype, line_item."""
    try:
        conn = get_connection()
        where, params = _build_pnl_where(filters)
        rows = conn.execute(f"""
            SELECT category, type, subtype, line_item, SUM(amount) AS total_amount
            FROM profit_and_loss_statement
            {where}
            GROUP BY category, type, subtype, line_item
            ORDER BY category, type, subtype, line_item
        """, params).fetchall()
        columns = ['category', 'type', 'subtype', 'line_item', 'total_amount']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching P&L income statement")
        return []


def get_pnl_monthly_trend(filters: dict) -> list[dict]:
    """Return P&L monthly totals by category for trend charts."""
    try:
        conn = get_connection()
        where, params = _build_pnl_where(filters)
        rows = conn.execute(f"""
            SELECT year, month, category, SUM(amount) AS total_amount
            FROM profit_and_loss_statement
            {where}
            GROUP BY year, month, category
            ORDER BY year, month, category
        """, params).fetchall()
        columns = ['year', 'month', 'category', 'total_amount']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching P&L monthly trend")
        return []


def get_pnl_yoy_comparison(filters: dict) -> list[dict]:
    """Return P&L yearly totals by category for year-over-year comparison."""
    try:
        conn = get_connection()
        where, params = _build_pnl_where(filters)
        rows = conn.execute(f"""
            SELECT year, category, SUM(amount) AS total_amount
            FROM profit_and_loss_statement
            {where}
            GROUP BY year, category
            ORDER BY year, category
        """, params).fetchall()
        columns = ['year', 'category', 'total_amount']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching P&L YoY comparison")
        return []


def get_pnl_entity_comparison(filters: dict) -> list[dict]:
    """Return P&L totals by entity_name and category for entity comparison."""
    try:
        conn = get_connection()
        where, params = _build_pnl_where(filters)
        rows = conn.execute(f"""
            SELECT entity_name, category, SUM(amount) AS total_amount
            FROM profit_and_loss_statement
            {where}
            GROUP BY entity_name, category
            ORDER BY entity_name, category
        """, params).fetchall()
        columns = ['entity_name', 'category', 'total_amount']
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.exception("Error fetching P&L entity comparison")
        return []
