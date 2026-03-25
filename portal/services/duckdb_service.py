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
