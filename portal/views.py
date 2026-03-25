"""Portal views — all function-based, all @login_required except login/logout."""

import csv
import mimetypes
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect

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
]


@login_required
def dashboard_view(request):
    filters = _get_filters(request, ['operating_company', 'counterparty_id'])
    summary = duckdb_service.get_dashboard_summary(filters)
    filter_options = duckdb_service.get_filter_options()
    return render(request, 'portal/dashboard.html', {
        'summary': summary,
        'filter_options': filter_options,
        'active_filters': filters,
        'page': 'dashboard',
    })


@login_required
def invoices_view(request):
    filters = _get_filters(request, INVOICE_FILTER_KEYS)
    invoices = duckdb_service.get_invoices(filters)
    filter_options = duckdb_service.get_filter_options()
    total_amount = sum(float(inv.get('invoice_total', 0) or 0) for inv in invoices)
    return render(request, 'portal/invoices.html', {
        'invoices': invoices,
        'filter_options': filter_options,
        'active_filters': filters,
        'total_amount': total_amount,
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

    # Summary metrics
    total_revenue = category_totals.get('Revenue', 0)
    total_cost_of_revenue = category_totals.get('Cost of Revenue', 0)
    gross_margin = total_revenue + total_cost_of_revenue
    total_opex = category_totals.get('Operating Expenses', 0)
    operating_income = gross_margin + total_opex
    total_other = category_totals.get('Other Income / (Expense)', 0)
    net_income = operating_income + total_other
    gross_margin_pct = (gross_margin / total_revenue * 100) if total_revenue else 0
    operating_margin_pct = (operating_income / total_revenue * 100) if total_revenue else 0
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

    # Group by year-month
    monthly_buckets = {}
    for row in monthly_trend:
        key = (row['year'], row['month'])
        if key not in monthly_buckets:
            monthly_buckets[key] = {'Revenue': 0, 'Cost of Revenue': 0,
                                     'Operating Expenses': 0, 'Other Income / (Expense)': 0}
        monthly_buckets[key][row['category']] = float(row['total_amount'])

    for (year, month) in sorted(monthly_buckets.keys()):
        bucket = monthly_buckets[(year, month)]
        label = f"{month_names[month]} {year}"
        monthly_labels.append(label)
        rev = bucket['Revenue']
        cor = bucket['Cost of Revenue']
        opx = bucket['Operating Expenses']
        oth = bucket['Other Income / (Expense)']
        monthly_revenue.append(round(rev, 2))
        monthly_costs.append(round(abs(cor + opx), 2))
        monthly_net.append(round(rev + cor + opx + oth, 2))
        monthly_gross_margin.append(round(rev + cor, 2))

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
        cor = year_data.get('Cost of Revenue', 0)
        opx = year_data.get('Operating Expenses', 0)
        oth = year_data.get('Other Income / (Expense)', 0)
        yoy_chart['revenue'].append(round(rev, 2))
        yoy_chart['cost_of_revenue'].append(round(abs(cor), 2))
        yoy_chart['operating_expenses'].append(round(abs(opx), 2))
        yoy_chart['other'].append(round(oth, 2))
        yoy_chart['net_income'].append(round(rev + cor + opx + oth, 2))

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

    # Ordered categories for template rendering
    category_order = ['Revenue', 'Cost of Revenue', 'Operating Expenses', 'Other Income / (Expense)']

    return render(request, 'portal/profit_loss.html', {
        'filter_options': filter_options,
        'active_filters': filters,
        'statement_structure': statement_structure,
        'category_totals': category_totals,
        'type_totals': type_totals,
        'subtype_totals': subtype_totals,
        'category_order': category_order,
        'total_revenue': total_revenue,
        'total_cost_of_revenue': total_cost_of_revenue,
        'gross_margin': gross_margin,
        'total_opex': total_opex,
        'operating_income': operating_income,
        'total_other': total_other,
        'net_income': net_income,
        'gross_margin_pct': gross_margin_pct,
        'operating_margin_pct': operating_margin_pct,
        'net_margin_pct': net_margin_pct,
        'chart_data': chart_data,
        'yoy_chart': yoy_chart,
        'entity_chart': entity_chart,
        'page': 'profit_loss',
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
