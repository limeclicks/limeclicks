# admin_custom/admin.py
from django.contrib import admin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin, GroupAdmin as DjangoGroupAdmin
from unfold.admin import ModelAdmin

# Make sure we’re not using the default registrations
admin.site.unregister(User)
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
    list_display = ("username", "email", "is_staff", "is_active", "last_login", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "first_name", "last_name")

    # If you want all fields on the *add* page (instead of Django’s 2-step):
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
    )

@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, ModelAdmin):
    autocomplete_fields = ("permissions",)
    search_fields = ("name",)
