from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("register/success/", views.registration_success_view, name="registration_success"),

    # Login / Logout
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    
    # Dashboard
    path("dashboard/", views.dashboard_view, name="dashboard"),

    # Email verification
    path("verify-email/<uuid:token>/", views.verify_email_view, name="verify_email"),
    path("resend-confirmation/", views.resend_confirmation_view, name="resend_confirmation"),
    path("resend-confirmation/success/", views.resend_confirmation_success_view, name="resend_confirmation_success"),

    # Password reset
    path("password-reset/", views.password_reset_view, name="password_reset"),
    path("password-reset/success/", views.password_reset_success_view, name="password_reset_success"),
    path("password-reset/confirm/<uuid:token>/", views.password_reset_confirm_view, name="password_reset_confirm"),
]
