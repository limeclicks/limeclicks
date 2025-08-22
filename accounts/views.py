from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.utils.text import slugify
from django.conf import settings
from .forms import RegisterForm, LoginForm, PasswordResetForm

def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        email = form.cleaned_data["email"].lower()
        password = form.cleaned_data["password"]

        # unique username from email
        base_username = slugify(email.split("@")[0]) or "user"
        username = base_username
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base_username}-{i}"

        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = name
        user.save()

        messages.success(request, "Account created successfully. You can sign in once login is enabled.")
        return redirect("accounts:register")  # stay on same page with success alert

    return render(request, "accounts/register.html", {"form": form, "is_admin": request.path.startswith("/admin/")})


def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("accounts:register")  # or wherever you want to redirect
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, "accounts/login.html", {"form": form})


def password_reset_view(request):
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        
        # Check if user exists
        try:
            user = User.objects.get(email__iexact=email)
            
            # Send password reset email using Brevo
            subject = "Password Reset - LimeClicks"
            message = f"""
            Hi {user.first_name or user.username},
            
            You have requested a password reset for your LimeClicks account.
            
            If you did not request this, please ignore this email.
            
            Best regards,
            LimeClicks Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            messages.success(request, "Password reset instructions have been sent to your email.")
        except User.DoesNotExist:
            # Don't reveal if email exists or not
            messages.success(request, "Password reset instructions have been sent to your email.")
        
        return redirect("accounts:password_reset")
    
    return render(request, "accounts/password_reset.html", {"form": form})
