"""Custom template filters used by the starter templates."""

from django import template

register = template.Library()


@register.filter
def currency(value):
    try:
        value = float(value)
        if value < 0:
            return f"-${abs(value):,.2f}"
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


@register.filter
def percentage(value):
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


@register.filter
def capacity_pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


@register.filter
def format_number(value):
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return "0.00"


@register.filter
def month_name(value):
    names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return names[int(value)]
    except (ValueError, TypeError, IndexError):
        return str(value)


@register.filter
def floatsub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def listget(lst, index):
    try:
        return lst[int(index)]
    except (IndexError, ValueError, TypeError):
        return ''
