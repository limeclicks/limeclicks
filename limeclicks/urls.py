from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import root_view

urlpatterns = [
    path("", root_view, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("projects/", include("project.urls")),
    path("keywords/", include("keywords.urls")),
    path("site-audit/", include("site_audit.urls")),
    path("competitors/", include("competitors.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Note: Django automatically serves static files from STATICFILES_DIRS in DEBUG mode
    # via django.contrib.staticfiles
