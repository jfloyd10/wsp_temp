"""Portal views — all function-based, all @login_required except login/logout."""

import csv
import mimetypes
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from urllib.parse import urlencode

from portal.services import duckdb_service


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            error = 'Invalid username or password.'
    return render(request, 'portal/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


def _get_filters(request, keys):
    """Extract filter values from GET params."""
    filters = {}
    for key in keys:
        val = request.GET.get(key, '').strip()
        if val:
            filters[key] = val
    return filters


INVOICE_FILTER_KEYS = [
    'operating_company', 'counterparty_id', 'source_system',
    'source_type', 'invoice_status', 'date_from', 'date_to',
    'search',
]


@login_required
def dashboard_view(request):
    filters = _get_filters(request, ['operating_company', 'counterparty_id'])
    summary = duckdb_service.get_dashboard_summary(filters)
    filter_options = duckdb_service.get_filter_options()

    # Monthly settlement trend for chart
    trend_data = [
        r for r in duckdb_service.get_monthly_settlement_trend(filters)
        if r.get('month') is not None and r.get('year') is not None
    ]
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    trend_chart = {
        'labels': [f"{month_names[int(r['month'])]} {r['year']}" for r in trend_data],
        'amounts': [float(r['total_amount']) for r in trend_data],
        'counts': [int(r['invoice_count']) for r in trend_data],
    }

    # Build human-readable filter labels for active filter chips
    active_filter_labels = {}
    if filters.get('operating_company'):
        active_filter_labels['operating_company'] = filters['operating_company']
    if filters.get('counterparty_id'):
        # Look up counterparty name
        cp_name = filters['counterparty_id']
        for cp in filter_options.get('counterparties', []):
            if cp['id'] == filters['counterparty_id']:
                cp_name = cp['name']
                break
        active_filter_labels['counterparty_id'] = cp_name

    return render(request, 'portal/dashboard.html', {
        'summary': summary,
        'filter_options': filter_options,
        'active_filters': filters,
        'active_filter_labels': active_filter_labels,
        'trend_chart': trend_chart,
        'page': 'dashboard',
    })


@login_required
def invoices_view(request):
    filters = _get_filters(request, INVOICE_FILTER_KEYS)
    filter_options = duckdb_service.get_filter_options()

    # Pagination
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 50

    result = duckdb_service.get_invoices_paginated(filters, page=page, per_page=per_page)

    # Build page range for pagination controls (show at most 7 page links)
    total_pages = result['total_pages']
    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        if page <= 4:
            page_range = list(range(1, 6)) + ["...", total_pages]
        elif page >= total_pages - 3:
            page_range = [1, "..."] + list(range(total_pages - 4, total_pages + 1))
        else:
            page_range = [1, "..."] + list(range(page - 1, page + 2)) + ["...", total_pages]

    # Compute display range for "Showing X to Y of Z"
    start_index = (page - 1) * per_page + 1 if result['total_count'] > 0 else 0
    end_index = min(page * per_page, result['total_count'])

    # Build query string for pagination links (preserve filters)
    filter_query = urlencode(filters)

    # Human-readable labels for active filter chips
    filter_label_map = {
        'operating_company': 'Company',
        'counterparty_id': 'Counterparty',
        'source_system': 'System',
        'source_type': 'Type',
        'invoice_status': 'Status',
        'date_from': 'From',
        'date_to': 'To',
        'search': 'Search',
    }
    active_filter_chips = []
    for key, val in filters.items():
        display_val = val
        if key == 'counterparty_id':
            for cp in filter_options.get('counterparties', []):
                if cp['id'] == val:
                    display_val = cp['name']
                    break
        active_filter_chips.append({
            'key': key,
            'label': filter_label_map.get(key, key),
            'value': display_val,
        })

    return render(request, 'portal/invoices.html', {
        'invoices': result['invoices'],
        'filter_options': filter_options,
        'active_filters': filters,
        'active_filter_chips': active_filter_chips,
        'total_amount': result['total_amount'],
        'total_count': result['total_count'],
        'current_page': result['page'],
        'total_pages': total_pages,
        'has_previous': result['has_previous'],
        'has_next': result['has_next'],
        'page_range': page_range,
        'filter_query': filter_query,
        'per_page': per_page,
        'start_index': start_index,
        'end_index': end_index,
        'page': 'invoices',
    })


@login_required
def invoice_detail_view(request, invoice_no):
    data = duckdb_service.get_invoice_detail(invoice_no)
    if not data['header']:
        raise Http404("Invoice not found")
    return render(request, 'portal/invoice_detail.html', {
        'header': data['header'],
        'lines': data['lines'],
        'attachments': data['attachments'],
        'page': 'invoices',
    })


@login_required
def download_attachment_view(request, invoice_no, file_name):
    result = duckdb_service.get_attachment(invoice_no, file_name)
    if result is None:
        raise Http404("Attachment not found")
    file_bytes, file_ext = result
    content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
    response = HttpResponse(file_bytes, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


@login_required
def metrics_view(request):
    filters = _get_filters(request, ['source_system', 'year'])
    metrics = duckdb_service.get_fcs_metrics(filters)
    filter_options = duckdb_service.get_filter_options()

    # Prepare chart data
    months_labels = []
    adjustments_data = []
    total_settled_data = []
    adj_pct_data = []
    cumulative_total_data = []

    for m in metrics:
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        label = f"{month_names[m['month']]} {m['year']}"
        months_labels.append(label)
        adjustments_data.append(float(m['adjustments']))
        total_settled_data.append(float(m['total_settled']))
        adj_pct_data.append(float(m['adjustment_percent']))
        cumulative_total_data.append(float(m['cumulative_total']))

    chart_data = {
        'labels': months_labels,
        'adjustments': adjustments_data,
        'total_settled': total_settled_data,
        'adj_pct': adj_pct_data,
        'cumulative_total': cumulative_total_data,
    }

    # Summary stats
    ytd_total = sum(total_settled_data) if total_settled_data else 0
    ytd_adj = sum(adjustments_data) if adjustments_data else 0
    avg_adj_pct = (sum(adj_pct_data) / len(adj_pct_data)) if adj_pct_data else 0

    return render(request, 'portal/metrics.html', {
        'metrics': metrics,
        'chart_data': chart_data,
        'filter_options': filter_options,
        'active_filters': filters,
        'ytd_total': ytd_total,
        'ytd_adj': ytd_adj,
        'avg_adj_pct': avg_adj_pct,
        'page': 'metrics',
    })


@login_required
def capacity_view(request):
    filters = _get_filters(request, ['operating_company', 'resource_type', 'year', 'month'])
    data = duckdb_service.get_capacity_factors(filters)
    filter_options = duckdb_service.get_filter_options()

    # Weighted average capacity factor
    total_possible = sum(float(r.get('total_mwh_possible', 0) or 0) for r in data)
    if total_possible > 0:
        weighted_ac = sum(float(r['ac_capacity_factor']) * float(r['total_mwh_possible']) for r in data) / total_possible
        weighted_bu = sum(float(r['bu_capacity_factor']) * float(r['total_mwh_possible']) for r in data) / total_possible
    else:
        weighted_ac = 0
        weighted_bu = 0

    return render(request, 'portal/capacity.html', {
        'data': data,
        'filter_options': filter_options,
        'active_filters': filters,
        'weighted_ac': weighted_ac,
        'weighted_bu': weighted_bu,
        'weighted_variance': weighted_ac - weighted_bu,
        'page': 'capacity',
    })


@login_required
def resource_detail_view(request, resource_id):
    summary = duckdb_service.get_resource_summary(resource_id)
    if not summary:
        raise Http404("Resource not found")

    history = duckdb_service.get_resource_monthly_history(resource_id)
    annual = duckdb_service.get_resource_annual_summary(resource_id)

    # Build chart data for monthly CF trends
    chart_labels = []
    ac_values = []
    bu_values = []
    variance_values = []
    gen_values = []
    budget_gen_values = []

    for r in history:
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        label = f"{month_names[r['month']]} {r['year']}"
        chart_labels.append(label)
        ac_values.append(float(r['ac_capacity_factor'] or 0))
        bu_values.append(float(r['bu_capacity_factor'] or 0))
        variance_values.append(float(r['capacity_factor_variance'] or 0))
        gen_values.append(float(r['net_generation'] or 0))
        budget_gen_values.append(float(r['budget_generation'] or 0))

    chart_data = {
        'labels': chart_labels,
        'ac_values': ac_values,
        'bu_values': bu_values,
        'variance_values': variance_values,
        'gen_values': gen_values,
        'budget_gen_values': budget_gen_values,
    }

    # Annual chart data
    annual_chart = {
        'labels': [str(a['year']) for a in annual],
        'avg_ac': [float(a['avg_ac'] or 0) for a in annual],
        'avg_bu': [float(a['avg_bu'] or 0) for a in annual],
        'total_gen': [float(a['total_gen'] or 0) for a in annual],
        'total_budget_gen': [float(a['total_budget_gen'] or 0) for a in annual],
    }

    return render(request, 'portal/resource_detail.html', {
        'summary': summary,
        'history': history,
        'annual': annual,
        'chart_data': chart_data,
        'annual_chart': annual_chart,
        'page': 'capacity',
    })


PNL_FILTER_KEYS = [
    'entity_name', 'entity_class', 'year', 'month',
    'category', 'covered_or_uncovered',
]


@login_required
def profit_loss_view(request):
    filters = _get_filters(request, PNL_FILTER_KEYS)
    filter_options = duckdb_service.get_pnl_filter_options()

    # Income statement data
    income_statement = duckdb_service.get_pnl_income_statement(filters)

    # Build structured income statement (category -> type -> subtype -> line_items)
    statement_structure = {}
    category_totals = {}
    for row in income_statement:
        cat = row['category']
        typ = row['type']
        sub = row['subtype']
        amt = float(row['total_amount'])

        if cat not in statement_structure:
            statement_structure[cat] = {}
            category_totals[cat] = 0
        category_totals[cat] += amt

        if typ not in statement_structure[cat]:
            statement_structure[cat][typ] = {}
        if sub not in statement_structure[cat][typ]:
            statement_structure[cat][typ][sub] = []
        statement_structure[cat][typ][sub].append({
            'line_item': row['line_item'],
            'amount': amt,
        })

    # Compute type and subtype totals
    type_totals = {}
    subtype_totals = {}
    for cat, types in statement_structure.items():
        type_totals[cat] = {}
        subtype_totals[cat] = {}
        for typ, subs in types.items():
            type_totals[cat][typ] = 0
            subtype_totals[cat][typ] = {}
            for sub, items in subs.items():
                sub_total = sum(i['amount'] for i in items)
                subtype_totals[cat][typ][sub] = sub_total
                type_totals[cat][typ] += sub_total

    # Summary metrics — dynamically sum revenue vs non-revenue categories
    total_revenue = category_totals.get('Revenue', 0)
    total_expenses = sum(v for k, v in category_totals.items() if k != 'Revenue')
    net_income = total_revenue + total_expenses  # expenses are typically negative
    gross_margin = net_income
    gross_margin_pct = (gross_margin / total_revenue * 100) if total_revenue else 0
    operating_margin_pct = gross_margin_pct
    net_margin_pct = (net_income / total_revenue * 100) if total_revenue else 0

    # Monthly trend data (for charts)
    trend_filters = {k: v for k, v in filters.items() if k != 'month'}
    monthly_trend = duckdb_service.get_pnl_monthly_trend(trend_filters)

    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Build chart data: monthly revenue, costs, net income
    monthly_labels = []
    monthly_revenue = []
    monthly_costs = []
    monthly_net = []
    monthly_gross_margin = []

    # Group by year-month — dynamically handle whatever categories exist
    monthly_buckets = {}
    for row in monthly_trend:
        key = (row['year'], row['month'])
        if key not in monthly_buckets:
            monthly_buckets[key] = {}
        monthly_buckets[key][row['category']] = float(row['total_amount'])

    for (year, month) in sorted(monthly_buckets.keys()):
        bucket = monthly_buckets[(year, month)]
        label = f"{month_names[month]} {year}"
        monthly_labels.append(label)
        rev = bucket.get('Revenue', 0)
        expenses = sum(v for k, v in bucket.items() if k != 'Revenue')
        monthly_revenue.append(round(rev, 2))
        monthly_costs.append(round(abs(expenses), 2))
        monthly_net.append(round(rev + expenses, 2))
        monthly_gross_margin.append(round(rev + expenses, 2))

    chart_data = {
        'labels': monthly_labels,
        'revenue': monthly_revenue,
        'costs': monthly_costs,
        'net_income': monthly_net,
        'gross_margin': monthly_gross_margin,
    }

    # YoY comparison data
    yoy_filters = {k: v for k, v in filters.items() if k not in ('year', 'month')}
    yoy_data = duckdb_service.get_pnl_yoy_comparison(yoy_filters)

    yoy_years = sorted(set(r['year'] for r in yoy_data))
    yoy_chart = {
        'years': [str(y) for y in yoy_years],
        'revenue': [],
        'cost_of_revenue': [],
        'operating_expenses': [],
        'other': [],
        'net_income': [],
    }
    for year in yoy_years:
        year_data = {r['category']: float(r['total_amount']) for r in yoy_data if r['year'] == year}
        rev = year_data.get('Revenue', 0)
        expenses = sum(v for k, v in year_data.items() if k != 'Revenue')
        yoy_chart['revenue'].append(round(rev, 2))
        yoy_chart['cost_of_revenue'].append(round(abs(expenses), 2))
        yoy_chart['operating_expenses'].append(0)
        yoy_chart['other'].append(0)
        yoy_chart['net_income'].append(round(rev + expenses, 2))

    # Entity comparison data
    entity_filters = {k: v for k, v in filters.items() if k != 'entity_name'}
    entity_data = duckdb_service.get_pnl_entity_comparison(entity_filters)

    entities = sorted(set(r['entity_name'] for r in entity_data))
    entity_chart = {
        'entities': entities,
        'revenue': [],
        'net_income': [],
    }
    for entity in entities:
        ent_rows = {r['category']: float(r['total_amount']) for r in entity_data if r['entity_name'] == entity}
        rev = ent_rows.get('Revenue', 0)
        total = sum(ent_rows.values())
        entity_chart['revenue'].append(round(rev, 2))
        entity_chart['net_income'].append(round(total, 2))

    # Ordered categories for template rendering — Revenue first, then others alphabetically
    category_order = ['Revenue'] + sorted(k for k in statement_structure.keys() if k != 'Revenue')

    return render(request, 'portal/profit_loss.html', {
        'filter_options': filter_options,
        'active_filters': filters,
        'statement_structure': statement_structure,
        'category_totals': category_totals,
        'type_totals': type_totals,
        'subtype_totals': subtype_totals,
        'category_order': category_order,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'gross_margin': gross_margin,
        'net_income': net_income,
        'gross_margin_pct': gross_margin_pct,
        'operating_margin_pct': operating_margin_pct,
        'net_margin_pct': net_margin_pct,
        'chart_data': chart_data,
        'yoy_chart': yoy_chart,
        'entity_chart': entity_chart,
        'page': 'profit_loss',
    })


TRADING_ANALYTICS_FILTER_KEYS = [
    'trading_group', 'employee_name', 'issue_category', 'year', 'month',
]


@login_required
def customer_landing_view(request):
    """Customer landing page with sample data for demo purposes."""
    from decimal import Decimal

    # Sample customer profile
    customer = {
        'name': 'Georgia Power Company',
        'id': 'GAPWR-001',
        'account_manager': 'Sarah Mitchell',
        'manager_email': 'sarah.mitchell@southernco.com',
        'manager_phone': '(404) 506-2810',
        'contract_type': 'Power Purchase Agreement',
        'contract_start': 'Jan 2019',
        'contract_end': 'Dec 2029',
        'next_settlement': 'Apr 2026',
        'last_login': 'Mar 24, 2026 at 3:42 PM',
    }

    # Account summary cards
    account_summary = {
        'total_settled_ytd': 48726340.50,
        'outstanding_balance': 3841200.00,
        'invoices_ytd': 47,
        'pending_invoices': 3,
        'avg_monthly_settlement': 5414037.83,
        'on_time_payment_rate': 98.6,
        'active_contracts': 12,
        'settlement_accuracy': 99.7,
    }

    # Monthly settlement trend (last 12 months)
    settlement_trend = {
        'labels': ['Apr 2025', 'May 2025', 'Jun 2025', 'Jul 2025', 'Aug 2025',
                   'Sep 2025', 'Oct 2025', 'Nov 2025', 'Dec 2025',
                   'Jan 2026', 'Feb 2026', 'Mar 2026'],
        'settled': [4210500, 4587300, 5912800, 6845200, 7123400,
                    5634100, 4987600, 4523800, 4312700,
                    4856900, 5123400, 5684100],
        'budget': [4100000, 4500000, 5800000, 6700000, 7000000,
                   5500000, 4900000, 4400000, 4200000,
                   4700000, 5000000, 5500000],
    }

    # Invoice status breakdown
    invoice_status = {
        'labels': ['Final', 'Pending Review', 'Draft', 'Adjusted'],
        'counts': [38, 3, 4, 2],
        'colors': ['#10b981', '#f59e0b', '#6b7280', '#ef4444'],
    }

    # Recent invoices
    recent_invoices = [
        {
            'invoice_no': 'INV-2026-03-0512',
            'invoice_name': 'March 2026 Wholesale Settlement',
            'invoice_date': 'Mar 2026',
            'invoice_total': 5684100.00,
            'invoice_status': 'FINAL',
            'source_type': 'WHOLESALE',
        },
        {
            'invoice_no': 'INV-2026-03-0498',
            'invoice_name': 'March 2026 PPA - Solar Fleet',
            'invoice_date': 'Mar 2026',
            'invoice_total': 1245800.00,
            'invoice_status': 'PENDING',
            'source_type': 'PPA',
        },
        {
            'invoice_no': 'INV-2026-03-0487',
            'invoice_name': 'March 2026 Short-Term Bilateral',
            'invoice_date': 'Mar 2026',
            'invoice_total': 892350.00,
            'invoice_status': 'DRAFT',
            'source_type': 'SHORT_TERM',
        },
        {
            'invoice_no': 'INV-2026-02-0453',
            'invoice_name': 'February 2026 Wholesale Settlement',
            'invoice_date': 'Feb 2026',
            'invoice_total': 5123400.00,
            'invoice_status': 'FINAL',
            'source_type': 'WHOLESALE',
        },
        {
            'invoice_no': 'INV-2026-02-0441',
            'invoice_name': 'February 2026 Pool Bill Allocation',
            'invoice_date': 'Feb 2026',
            'invoice_total': 3876500.00,
            'invoice_status': 'FINAL',
            'source_type': 'WHOLESALE',
        },
    ]

    # Settlement by source type (pie chart)
    settlement_by_type = {
        'labels': ['Wholesale', 'PPA', 'Short-Term', 'Pool Bill'],
        'amounts': [28450200, 9876400, 4523100, 5876640],
        'colors': ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981'],
    }

    # Activity timeline
    activity_timeline = [
        {
            'icon': 'check-circle',
            'color': 'emerald',
            'title': 'Invoice #INV-2026-03-0512 finalized',
            'description': 'March wholesale settlement has been approved and marked as FINAL.',
            'time': '2 hours ago',
        },
        {
            'icon': 'file-text',
            'color': 'blue',
            'title': 'New invoice generated',
            'description': 'March 2026 PPA - Solar Fleet invoice for $1,245,800 is pending review.',
            'time': '5 hours ago',
        },
        {
            'icon': 'download',
            'color': 'purple',
            'title': 'Settlement report downloaded',
            'description': 'Q1 2026 settlement summary report was downloaded by your team.',
            'time': '1 day ago',
        },
        {
            'icon': 'credit-card',
            'color': 'amber',
            'title': 'Payment received',
            'description': 'Payment of $5,123,400.00 received for February wholesale settlement.',
            'time': '3 days ago',
        },
        {
            'icon': 'alert-circle',
            'color': 'red',
            'title': 'Adjustment posted',
            'description': '$38,200 adjustment applied to January Pool Bill allocation.',
            'time': '1 week ago',
        },
    ]

    # Upcoming milestones
    milestones = [
        {'date': 'Apr 1', 'title': 'Q1 Settlement Close', 'status': 'upcoming'},
        {'date': 'Apr 5', 'title': 'March Invoice Due', 'status': 'upcoming'},
        {'date': 'Apr 15', 'title': 'FERC Filing Deadline', 'status': 'upcoming'},
        {'date': 'May 1', 'title': 'April Settlement Preview', 'status': 'future'},
    ]

    # Energy mix data (donut chart)
    energy_mix = {
        'labels': ['Natural Gas', 'Nuclear', 'Coal', 'Solar', 'Hydro', 'Wind'],
        'values': [42, 24, 15, 10, 6, 3],
        'colors': ['#3b82f6', '#8b5cf6', '#6b7280', '#f59e0b', '#06b6d4', '#10b981'],
    }

    return render(request, 'portal/customer_landing.html', {
        'customer': customer,
        'account_summary': account_summary,
        'settlement_trend': settlement_trend,
        'invoice_status': invoice_status,
        'recent_invoices': recent_invoices,
        'settlement_by_type': settlement_by_type,
        'activity_timeline': activity_timeline,
        'milestones': milestones,
        'energy_mix': energy_mix,
        'page': 'customer_landing',
    })


@login_required
def blank_view(request):
    return render(request, 'portal/blank.html', {'page': 'blank'})


@login_required
def minipool_view(request):
    return render(request, 'portal/minipool.html', {'page': 'minipool'})


@login_required
def trading_analytics_view(request):
    filters = _get_filters(request, TRADING_ANALYTICS_FILTER_KEYS)
    filter_options = duckdb_service.get_trading_analytics_filter_options()

    # Raw issue list
    issues = duckdb_service.get_trading_analytics(filters)

    # Aggregations for BI charts
    by_category = duckdb_service.get_trading_analytics_summary_by_category(filters)
    by_employee = duckdb_service.get_trading_analytics_summary_by_employee(filters)
    by_group = duckdb_service.get_trading_analytics_by_group(filters)
    monthly_trend = duckdb_service.get_trading_analytics_monthly_trend(filters)
    category_by_month = duckdb_service.get_trading_analytics_category_by_month(filters)

    # Summary stats
    total_issues = len(issues)
    unique_traders = len(set(i['employee_name'] for i in issues)) if issues else 0
    unique_deals = len(set(i['deal_no'] for i in issues)) if issues else 0
    top_category = by_category[0]['issue_category'] if by_category else 'N/A'
    top_category_count = by_category[0]['issue_count'] if by_category else 0

    # Monthly trend chart data
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    trend_labels = []
    trend_counts = []
    for row in monthly_trend:
        trend_labels.append(f"{month_names[row['month']]} {row['year']}")
        trend_counts.append(row['issue_count'])

    # Category breakdown chart data
    cat_labels = [r['issue_category'] for r in by_category]
    cat_counts = [r['issue_count'] for r in by_category]

    # Trading group chart data
    group_labels = [r['trading_group'] for r in by_group]
    group_counts = [r['issue_count'] for r in by_group]

    # Stacked bar chart: categories by month
    all_categories = sorted(set(r['issue_category'] for r in category_by_month if r['issue_category'] is not None))
    stacked_labels = []
    stacked_datasets = {cat: [] for cat in all_categories}

    # Build ordered month keys
    month_keys = sorted(set((r['year'], r['month']) for r in category_by_month))
    for year, month in month_keys:
        stacked_labels.append(f"{month_names[month]} {year}")
        month_data = {r['issue_category']: r['issue_count']
                      for r in category_by_month if r['year'] == year and r['month'] == month}
        for cat in all_categories:
            stacked_datasets[cat].append(month_data.get(cat, 0))

    chart_data = {
        'trend_labels': trend_labels,
        'trend_counts': trend_counts,
        'cat_labels': cat_labels,
        'cat_counts': cat_counts,
        'group_labels': group_labels,
        'group_counts': group_counts,
        'stacked_labels': stacked_labels,
        'stacked_categories': all_categories,
        'stacked_datasets': stacked_datasets,
    }

    return render(request, 'portal/trading_analytics.html', {
        'issues': issues,
        'by_category': by_category,
        'by_employee': by_employee,
        'by_group': by_group,
        'filter_options': filter_options,
        'active_filters': filters,
        'total_issues': total_issues,
        'unique_traders': unique_traders,
        'unique_deals': unique_deals,
        'top_category': top_category,
        'top_category_count': top_category_count,
        'chart_data': chart_data,
        'page': 'trading_analytics',
    })


@login_required
def export_invoices_csv(request):
    filters = _get_filters(request, INVOICE_FILTER_KEYS)
    invoices = duckdb_service.get_invoices(filters)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Invoice No', 'Invoice Name', 'Operating Company', 'Counterparty',
        'Source System', 'Source Type', 'Date', 'Status', 'Total'
    ])
    for inv in invoices:
        date_val = inv.get('invoice_date', '')
        if hasattr(date_val, 'strftime'):
            date_val = date_val.strftime('%Y-%m-%d')
        writer.writerow([
            inv.get('invoice_no', ''),
            inv.get('invoice_name', ''),
            inv.get('operating_company', ''),
            inv.get('counterparty_name', ''),
            inv.get('source_system', ''),
            inv.get('source_type', ''),
            date_val,
            inv.get('invoice_status', ''),
            inv.get('invoice_total', ''),
        ])
    return response
