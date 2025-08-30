from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def score_to_percent(value):
    """Convert a 0-1 score to a percentage."""
    try:
        return int(float(value) * 100)
    except (ValueError, TypeError):
        return 0

@register.filter 
def get_item(dictionary, key):
    """Get an item from a dictionary."""
    if dictionary:
        return dictionary.get(key)
    return None