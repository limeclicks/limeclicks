"""
Gravatar template tag for Django
Generates Gravatar URLs based on user email addresses
"""

import hashlib
from urllib.parse import urlencode
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def gravatar_url(user, size=80):
    """
    Return the Gravatar URL for a user's email address.
    
    Usage: {{ user|gravatar_url:200 }}
    
    Args:
        user: Django User object
        size: Size of the avatar in pixels (default: 80)
    
    Returns:
        Gravatar URL string
    """
    if not user or not hasattr(user, 'email'):
        return ''
    
    email = user.email.lower().strip()
    email_hash = hashlib.md5(email.encode('utf-8')).hexdigest()
    
    params = urlencode({
        's': str(size),  # Size
        'd': 'mp',  # Default image (mystery person)
        'r': 'g',  # Rating (g for general)
    })
    
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"


@register.simple_tag
def gravatar_img(user, size=80, css_class='', alt=''):
    """
    Return a complete img tag with Gravatar URL.
    
    Usage: {% gravatar_img user 200 "rounded-full" "User Avatar" %}
    
    Args:
        user: Django User object
        size: Size of the avatar in pixels (default: 80)
        css_class: CSS classes to apply to the img tag
        alt: Alt text for the image
    
    Returns:
        HTML img tag
    """
    if not user:
        return ''
    
    url = gravatar_url(user, size)
    if not alt:
        alt = f"{user.get_full_name() or user.username}'s avatar"
    
    html = f'<img src="{url}" width="{size}" height="{size}" class="{css_class}" alt="{alt}" />'
    return mark_safe(html)


@register.filter
def has_gravatar(user):
    """
    Check if a user has a Gravatar (this is a simplified check).
    Note: This doesn't actually verify if the user has uploaded a custom Gravatar,
    it just checks if they have an email address.
    
    For a real check, you'd need to make an API call to Gravatar,
    which is not recommended for template tags due to performance.
    
    Usage: {% if user|has_gravatar %}...{% endif %}
    """
    return bool(user and hasattr(user, 'email') and user.email)