from django.contrib import admin
from django.urls import path, include
from accounts.views import root_view

urlpatterns = [
    path("", root_view, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("projects/", include("project.urls")),
    path("keywords/", include("keywords.urls")),
]
