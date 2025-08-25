"""
Context processors for LimeClicks
"""
from django.conf import settings


def logos(request):
    """
    Add logo URLs to context for use in templates
    """
    return {
        'logo_light': '/static/img/logo-light-admin.png',
        'logo_dark': '/static/img/logo-dark-admin.png',
        'logo_light_large': '/static/img/logo-light.png',
        'logo_dark_large': '/static/img/logo-dark.png',
        'site_name': 'LimeClicks',
        'site_tagline': 'SEO & Digital Marketing Platform',
    }


def site_settings(request):
    """
    Add general site settings to context
    """
    return {
        'DEBUG': settings.DEBUG,
        'SITE_URL': getattr(settings, 'SITE_URL', 'https://limeclicks.com'),
        'SUPPORT_EMAIL': getattr(settings, 'SUPPORT_EMAIL', 'support@limeclicks.com'),
    }