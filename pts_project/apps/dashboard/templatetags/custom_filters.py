from django import template

register = template.Library()


@register.filter
def endswith(value, suffix):
    """Check if a string ends with a suffix."""
    if not isinstance(value, str):
        return False
    return str(value).endswith(str(suffix))


@register.filter
def abs(value):
    """Return absolute value of a number."""
    try:
        return value if value >= 0 else -value
    except Exception:
        return value
