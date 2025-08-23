from django.contrib import admin
from unfold.admin import ModelAdmin
from django import forms
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import path
from .models import Project

User = get_user_model()


class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = '__all__'
    
    def clean_domain(self):
        domain = self.cleaned_data.get('domain')
        if domain:
            # Remove http:// or https:// if present
            import re
            domain = domain.lower()
            domain = re.sub(r'^https?://', '', domain)
            
            # Remove trailing slash if present
            domain = domain.rstrip('/')
            
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            
            # Validate domain format - must have at least one dot for proper domain/subdomain
            # Reject localhost and single words
            if '.' not in domain:
                raise forms.ValidationError('Please enter a valid domain or subdomain name (must contain at least one dot).')
            
            # Check for invalid characters
            if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
                raise forms.ValidationError('Domain name contains invalid characters. Only letters, numbers, dots, and hyphens are allowed.')
            
            # Validate proper domain format
            domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
            if not re.match(domain_pattern, domain):
                raise forms.ValidationError('Please enter a valid domain or subdomain name.')
            
            # Additional validations
            if domain.startswith('.') or domain.endswith('.'):
                raise forms.ValidationError('Domain cannot start or end with a dot.')
            
            if '..' in domain:
                raise forms.ValidationError('Domain cannot contain consecutive dots.')
            
            if domain.startswith('-') or domain.endswith('-'):
                raise forms.ValidationError('Domain cannot start or end with a hyphen.')
            
            return domain
        return domain


class EmailFilter(admin.SimpleListFilter):
    title = 'User Email'
    parameter_name = 'user_email'

    def lookups(self, request, model_admin):
        emails = Project.objects.values_list('user__email', flat=True).distinct().order_by('user__email')
        return [(email, email) for email in emails if email]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__email=self.value())
        return queryset


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    form = ProjectAdminForm
    list_display = ('domain', 'title', 'user_email', 'active', 'favicon_url_display', 'created_at', 'updated_at')
    list_filter = ('active', EmailFilter, 'created_at', 'updated_at')
    search_fields = ('domain', 'title', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'favicon_url_display')
    list_per_page = 25
    ordering = ('-created_at',)
    autocomplete_fields = ('user',)
    
    fieldsets = (
        ('Project Information', {
            'fields': ('user', 'domain', 'title', 'active')
        }),
        ('Favicon', {
            'fields': ('favicon_url_display',),
            'classes': ('collapse',),
            'description': 'Favicons are now served via Google\'s favicon service'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def favicon_url_display(self, obj):
        google_url = obj.get_favicon_url()
        cached_url = obj.get_cached_favicon_url()
        return (f'<strong>Cached:</strong> <a href="{cached_url}" target="_blank">View</a><br>'
                f'<strong>Google:</strong> <a href="{google_url}" target="_blank">Direct</a>')
    favicon_url_display.short_description = 'Favicon URLs'
    favicon_url_display.allow_tags = True
