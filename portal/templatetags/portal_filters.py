"""Custom template filters for the portal."""

from django import template

register = template.Library()


@register.filter
def currency(value):
    """Format a number as USD currency: $1,234,567.89"""
    try:
        value = float(value)
        if value < 0:
            return f"-${abs(value):,.2f}"
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


@register.filter
def percentage(value):
    """Format a decimal as a percentage: 45.2%"""
    try:
        value = float(value)
        return f"{value:.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


@register.filter
def capacity_pct(value):
    """Format a capacity factor (0-1 decimal) as percentage: 45.2%"""
    try:
        value = float(value) * 100
        return f"{value:.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


@register.filter
def format_number(value):
    """Format a number with commas: 1,234,567.89"""
    try:
        value = float(value)
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"


@register.filter
def format_filesize(value):
    """Format bytes as human-readable file size."""
    try:
        value = int(value)
        if value < 1024:
            return f"{value} B"
        elif value < 1024 * 1024:
            return f"{value / 1024:.1f} KB"
        else:
            return f"{value / (1024 * 1024):.1f} MB"
    except (ValueError, TypeError):
        return "0 B"


@register.filter
def format_date(value):
    """Format a date as MMM YYYY."""
    try:
        if hasattr(value, 'strftime'):
            return value.strftime('%b %Y')
        return str(value)
    except Exception:
        return str(value)


@register.filter
def month_name(value):
    """Convert month number to name."""
    names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return names[int(value)]
    except (ValueError, TypeError, IndexError):
        return str(value)


@register.filter
def dictget(d, key):
    """Look up a key in a dictionary. Usage: {{ mydict|dictget:key }}"""
    if isinstance(d, dict):
        return d.get(key, 0)
    return 0
