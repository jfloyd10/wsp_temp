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
