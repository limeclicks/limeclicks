from django import template
from site_audit.issue_fixes import get_fix_for_issue

register = template.Library()

@register.filter
def replace_underscore(value):
    """Replace underscores with spaces and title case"""
    if not value:
        return value
    return value.replace('_', ' ').title()

@register.filter
def get_fix_title(issue):
    """Get the fix title for an issue"""
    if not issue:
        return "Review Issue"
    fix_info = get_fix_for_issue(issue.issue_type)
    return fix_info.get('title', 'Review and Fix Issue')

@register.filter
def get_fix_description(issue):
    """Get the fix description for an issue"""
    if not issue:
        return ""
    fix_info = get_fix_for_issue(issue.issue_type)
    return fix_info.get('description', '')

@register.filter
def get_fix_steps(issue):
    """Get the fix steps for an issue"""
    if not issue:
        return []
    fix_info = get_fix_for_issue(issue.issue_type)
    return fix_info.get('fix_steps', [])

@register.filter
def get_fix_impact(issue):
    """Get the impact description for an issue"""
    if not issue:
        return ""
    fix_info = get_fix_for_issue(issue.issue_type)
    return fix_info.get('impact', 'This issue may affect SEO performance')