# admin_custom/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin, GroupAdmin as DjangoGroupAdmin
from unfold.admin import ModelAdmin

User = get_user_model()

# Make sure we're not using the default registrations
admin.site.unregister(Group)

# Optional: register Permission so autocomplete has a backend
@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    search_fields = ("name", "codename", "content_type__app_label")
    list_display = ("name", "codename", "content_type")

@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    # Better UX for existing users: searchable autocompletes
    autocomplete_fields = ("groups", "user_permissions")
    list_display = ("email", "username", "email_verified", "is_staff", "is_active", "last_login", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "email_verified", "groups")
    search_fields = ("email", "username", "first_name", "last_name")
    readonly_fields = ("verification_token", "verification_token_created")
    
    def autocomplete_view(self, request):
        """
        Override autocomplete view to display emails instead of usernames
        """
        return super().autocomplete_view(request)
    
    def get_search_results(self, request, queryset, search_term):
        """
        Override to customize autocomplete display
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct

    # Add email verification fields to the fieldsets
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Email Verification", {"fields": ("email_verified", "verification_token", "verification_token_created")}),
    )

    # If you want all fields on the *add* page (instead of Django's 2-step):
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "email_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
    )

@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, ModelAdmin):
    autocomplete_fields = ("permissions",)
    search_fields = ("name",)
