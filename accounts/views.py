from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.utils.text import slugify
from .forms import RegisterForm

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
