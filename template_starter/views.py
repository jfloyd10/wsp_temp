"""
Example views for the template_starter app.

These render the three starter pages with placeholder data so the look-and-feel
works out of the box. Replace the dummy data with your real querysets / services.
"""

import json
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

# Common context applied to base.html (brand strings, notifications, etc.)
BRAND_CONTEXT = {
    "app_name": "Application Portal",
    "brand_name": "Your Brand",
    "brand_initials": "YB",
    "user_role": "Administrator",
    "login_footer": "Powered by your team",
    "notifications": [
        {"icon": "file-text", "color": "emerald", "title": "Welcome to your portal",
         "body": "This is a starter notification. Wire up real ones in the view.",
         "time": "Just now"},
        {"icon": "check-circle", "color": "blue", "title": "Setup complete",
         "body": "Your account is ready to go.",
         "time": "5 minutes ago"},
    ],
}


# ---------- Auth ----------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")
        error = "Invalid username or password."

    return render(request, "template_starter/login.html", {**BRAND_CONTEXT, "error": error})


def logout_view(request):
    auth_logout(request)
    return redirect("login")


# ---------- Dashboard ----------

@login_required
def dashboard(request):
    context = {
        **BRAND_CONTEXT,
        "page": "dashboard",
        "workspace": {
            "name": "Acme Corp",
            "id": "ACME-001",
            "plan": "Enterprise",
            "tagline": "Your dashboard provides a consolidated view of activity, performance, and account details.",
            "last_login": "Today, 9:42 AM",
            "contact_name": "Jamie Rivera",
            "contact_email": "jamie@example.com",
            "contact_phone": "+1 (555) 123-4567",
            "period_start": "Jan 2026",
            "period_end": "Dec 2026",
        },
        "summary_stats": [
            {"label": "Revenue YTD", "value": "$1,248,500", "icon": "dollar-sign", "color": "blue",
             "badge": "+8.2% YoY", "badge_color": "emerald", "progress": 72,
             "caption": "72% of annual target"},
            {"label": "Outstanding", "value": "$42,300", "icon": "clock", "color": "amber",
             "badge": "3 pending", "badge_color": "amber", "progress": 8,
             "caption": "Due within 30 days"},
            {"label": "On-Time Rate", "value": "98.6%", "icon": "check-square", "color": "emerald",
             "badge": "47 total", "badge_color": "blue", "progress": 98,
             "caption": "47 of 48 items"},
            {"label": "Accuracy", "value": "99.7%", "icon": "target", "color": "purple",
             "badge": "Excellent", "badge_color": "emerald", "progress": 99,
             "caption": "Quality score"},
        ],
        "trend": {
            "labels": json.dumps(["May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                  "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]),
            "actual": json.dumps([84000, 92000, 98000, 102000, 110000, 118000,
                                  125000, 132000, 128000, 138000, 145000, 152000]),
            "target": json.dumps([90000, 95000, 100000, 105000, 110000, 115000,
                                  120000, 125000, 130000, 135000, 140000, 145000]),
        },
        "breakdown": {
            "labels": json.dumps(["Type A", "Type B", "Type C", "Type D"]),
            "amounts": json.dumps([520000, 380000, 220000, 128500]),
            "colors": json.dumps(["#3b82f6", "#8b5cf6", "#f59e0b", "#10b981"]),
        },
        "status_chart": {
            "labels": json.dumps(["Final", "Pending", "Draft"]),
            "counts": json.dumps([42, 4, 2]),
            "colors": json.dumps(["#10b981", "#f59e0b", "#9ca3af"]),
        },
        "allocation": {
            "labels": ["Resource A", "Resource B", "Resource C", "Resource D"],
            "values": [42, 28, 18, 12],
            "colors": ["#3b82f6", "#8b5cf6", "#f59e0b", "#10b981"],
        },
        "recent_items": [
            {"id": "ITEM-2026-04-001", "name": "Sample item one", "type": "TYPE_A",
             "type_color": "blue", "date": "Apr 28, 2026", "amount": 12450.00,
             "status": "FINAL", "status_color": "emerald"},
            {"id": "ITEM-2026-04-002", "name": "Sample item two", "type": "TYPE_B",
             "type_color": "purple", "date": "Apr 24, 2026", "amount": 8730.50,
             "status": "PENDING", "status_color": "amber"},
            {"id": "ITEM-2026-04-003", "name": "Sample item three", "type": "TYPE_C",
             "type_color": "amber", "date": "Apr 21, 2026", "amount": 23110.75,
             "status": "FINAL", "status_color": "emerald"},
            {"id": "ITEM-2026-04-004", "name": "Sample item four", "type": "TYPE_A",
             "type_color": "blue", "date": "Apr 18, 2026", "amount": 5460.00,
             "status": "DRAFT", "status_color": "gray"},
        ],
        "activity_timeline": [
            {"icon": "file-text", "color": "emerald", "title": "New item created",
             "description": "ITEM-2026-04-001 was created and submitted for review.",
             "time": "2 hours ago"},
            {"icon": "check-circle", "color": "blue", "title": "Item approved",
             "description": "ITEM-2026-04-002 has been finalized.",
             "time": "Yesterday"},
            {"icon": "upload", "color": "purple", "title": "Documents uploaded",
             "description": "3 supporting attachments were uploaded.",
             "time": "2 days ago"},
            {"icon": "alert-circle", "color": "amber", "title": "Adjustment required",
             "description": "Variance detected — review recommended.",
             "time": "4 days ago"},
        ],
        "milestones": [
            {"date": "May 5", "title": "Statement close", "status": "upcoming"},
            {"date": "May 15", "title": "Review meeting", "status": "upcoming"},
            {"date": "Apr 30", "title": "Filing deadline", "status": "completed"},
        ],
        "quick_actions": [
            {"icon": "file-text", "color": "blue", "title": "View Items",
             "description": "Browse all records", "href": "#"},
            {"icon": "download", "color": "emerald", "title": "Export Data",
             "description": "Download CSV", "href": "#"},
            {"icon": "activity", "color": "purple", "title": "Reports",
             "description": "Performance dashboards", "href": "#"},
            {"icon": "bar-chart-2", "color": "amber", "title": "Metrics",
             "description": "Quality metrics", "href": "#"},
        ],
    }
    return render(request, "template_starter/dashboard.html", context)


# ---------- Detail ----------

@login_required
def detail(request, item_id):
    summary = {
        "id": item_id,
        "name": "Sample Resource",
        "subtitle": "Sample Subtitle",
        "category": "TYPE_A",
        "icon": "database",
        "icon_color": "blue",
        "stats": [
            {"label": "Avg Actual", "value": "82.4%", "icon": "zap", "color": "brand"},
            {"label": "Avg Target", "value": "78.0%", "icon": "target", "color": "blue"},
            {"label": "Avg Variance", "value": "+4.4%", "icon": "trending-up",
             "color": "emerald", "value_color": "emerald"},
            {"label": "Rating", "value": "1,250.00", "unit": "MW", "icon": "bar-chart-2", "color": "purple"},
            {"label": "Total Volume", "value": "8,420,500", "unit": "MWh",
             "icon": "battery-charging", "color": "cyan"},
        ],
        "fields": [
            {"label": "Resource ID", "value": item_id},
            {"label": "Owner", "value": "Acme Corp"},
            {"label": "Category", "value": "TYPE_A"},
            {"label": "Ownership", "value": "100.0%"},
            {"label": "Total Rating", "value": "1,250.00 MW"},
            {"label": "Data Range", "value": "2022 – 2026"},
            {"label": "Peak", "value": "94.2%", "value_color": "emerald"},
            {"label": "Min", "value": "61.5%", "value_color": "red"},
            {"label": "Records", "value": "48 months"},
        ],
    }

    history = [
        {"year": 2026, "month": m, "volume": 700000 + m * 5000,
         "target_volume": 680000 + m * 5000,
         "actual": 0.78 + (m - 6) * 0.01, "target": 0.78,
         "variance": (m - 6) * 0.01}
        for m in range(1, 5)
    ] + [
        {"year": 2025, "month": m, "volume": 650000 + m * 4000,
         "target_volume": 660000 + m * 4000,
         "actual": 0.74 + (m - 6) * 0.008, "target": 0.78,
         "variance": (m - 6) * 0.008 - 0.04}
        for m in range(1, 13)
    ]

    annual = [
        {"year": 2024, "avg_actual": 0.762, "avg_target": 0.780, "avg_variance": -0.018,
         "total_volume": 7950000, "total_target": 8100000},
        {"year": 2025, "avg_actual": 0.795, "avg_target": 0.780, "avg_variance": 0.015,
         "total_volume": 8200000, "total_target": 8100000},
        {"year": 2026, "avg_actual": 0.824, "avg_target": 0.780, "avg_variance": 0.044,
         "total_volume": 2900000, "total_target": 2700000},
    ]

    chart_data = {
        "labels": [f"{m}/2025" for m in range(1, 13)] + [f"{m}/2026" for m in range(1, 5)],
        "actual_values": [h["actual"] for h in history],
        "target_values": [h["target"] for h in history],
        "volume_values": [h["volume"] for h in history],
        "target_volume_values": [h["target_volume"] for h in history],
        "variance_values": [h["variance"] for h in history],
    }

    annual_chart = {
        "labels": [a["year"] for a in annual],
        "avg_actual": [a["avg_actual"] for a in annual],
        "avg_target": [a["avg_target"] for a in annual],
    }

    context = {
        **BRAND_CONTEXT,
        "page": "detail",
        "summary": summary,
        "history": history,
        "annual": annual,
        "chart_data": chart_data,
        "annual_chart": annual_chart,
    }
    return render(request, "template_starter/detail.html", context)
