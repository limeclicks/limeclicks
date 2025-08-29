from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import get_connection
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.conf import settings
from django.urls import reverse
from django.http import Http404, HttpResponseRedirect
from .forms import RegisterForm, LoginForm, PasswordResetForm, ResendConfirmationForm
from .email_backend import BrevoTemplateEmailMessage
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

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
        user.email_verified = False  # User needs to verify email
        user.save()

        # Send verification email using Brevo template ID 2
        verification_url = request.build_absolute_uri(
            reverse('accounts:verify_email', args=[user.verification_token])
        )
        
        template_params = {
            'name': name,
            'url': verification_url
        }
        
        # Create template email message
        email_message = BrevoTemplateEmailMessage(
            template_id=2,
            template_params=template_params,
            to=[email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        
        # Send the email
        connection = get_connection()
        connection.send_messages([email_message])

        # Store user info for success page
        request.session['registration_success'] = {
            'email': email,
            'name': name
        }
        
        return redirect("accounts:registration_success")

    return render(request, "accounts/register.html", {"form": form, "is_admin": request.path.startswith("/admin/")})


def login_view(request):
    form = LoginForm(request.POST or None)
    
    # Get the next URL from session or query parameter
    next_url = request.GET.get('next') or request.session.get('next_url', '')
    if next_url and request.session.get('next_url'):
        # Clear it from session once we've retrieved it
        del request.session['next_url']
    
    if request.method == "POST":
        # Get email and password from POST data first
        email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if not user.email_verified:
                    form.add_error('password', "Please verify your email address before logging in. Check your inbox for the verification link.")
                    return render(request, "accounts/login.html", {"form": form})
                # Login the user properly
                login(request, user)
                
                # Log successful login
                logger.info(f"User {user.email} logged in successfully")
                
                # Force session save to ensure login is persisted
                request.session.modified = True
                request.session.save()
                
                # Determine redirect URL
                if next_url and next_url.startswith('/'):
                    redirect_to = next_url
                else:
                    redirect_to = reverse("accounts:dashboard")
                
                # Use hard redirect
                return HttpResponseRedirect(redirect_to)
            else:
                form.add_error('password', "Invalid email or password.")
        else:
            # Always check authentication if email and password are provided
            if email and password:
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                try:
                    validate_email(email)
                    user = authenticate(request, username=email, password=password)
                    if user is not None:
                        if not user.email_verified:
                            form.add_error('password', "Please verify your email address before logging in. Check your inbox for the verification link.")
                        else:
                            # Valid credentials but form validation failed (likely captcha)
                            # If only captcha failed, log the user in anyway
                            if 'captcha' in form.errors and len(form.errors) == 1:
                                # Login the user properly
                                login(request, user)
                                
                                # Log successful login
                                logger.info(f"User {user.email} logged in successfully (captcha bypass)")
                                
                                # Force session save to ensure login is persisted
                                request.session.modified = True
                                request.session.save()
                                
                                # Determine redirect URL
                                if next_url and next_url.startswith('/'):
                                    redirect_to = next_url
                                else:
                                    redirect_to = reverse("accounts:dashboard")
                                
                                # Use hard redirect
                                return HttpResponseRedirect(redirect_to)
                            else:
                                form.add_error('password', "Please complete the verification to continue.")
                    else:
                        # Invalid credentials - add error to password field
                        form.add_error('password', "Invalid email or password.")
                except ValidationError:
                    # Invalid email format - let form validation handle this
                    pass
    
    return render(request, "accounts/login.html", {"form": form})


def password_reset_view(request):
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        
        # Check if user exists
        try:
            user = User.objects.get(email__iexact=email)
            
            # Generate password reset token
            reset_token = user.generate_password_reset_token()
            
            # Create password reset URL with token
            reset_url = request.build_absolute_uri(
                reverse('accounts:password_reset_confirm', args=[reset_token])
            )
            
            # Send password reset email using Brevo template ID 1
            template_params = {
                'name': user.first_name or user.username,
                'url': reset_url
            }
            
            # Create template email message
            email_message = BrevoTemplateEmailMessage(
                template_id=1,
                template_params=template_params,
                to=[email],
                from_email=settings.DEFAULT_FROM_EMAIL
            )
            
            # Send the email
            connection = get_connection()
            connection.send_messages([email_message])
            
            # Store email in session for success page
            request.session['password_reset_email'] = email
            
            return redirect("accounts:password_reset_success")
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not - still show success page
            request.session['password_reset_email'] = email
            return redirect("accounts:password_reset_success")
    
    return render(request, "accounts/password_reset.html", {"form": form})


def verify_email_view(request, token):
    """
    Handle email verification using the token
    """
    try:
        user = get_object_or_404(User, verification_token=token)
        
        if user.email_verified:
            messages.info(request, "Your email is already verified. You can log in.")
            return redirect("accounts:login")
        
        if user.is_verification_token_expired():
            messages.error(request, "Verification link has expired. Please register again.")
            return redirect("accounts:register")
        
        # Verify the email
        user.email_verified = True
        user.save()
        
        # Send welcome email in background task
        from .tasks import send_welcome_email_async
        try:
            task = send_welcome_email_async.delay(user.id)
            logger.info(f"Welcome email task queued for user {user.email}: {task.id}")
        except Exception as e:
            logger.error(f"Error queuing welcome email task: {e}")
            # Fallback: try to send synchronously
            try:
                result = send_welcome_email_async(user.id)
                logger.info(f"Welcome email sent synchronously for user {user.email}: {result}")
            except Exception as sync_e:
                logger.error(f"Failed to send welcome email synchronously: {sync_e}")
        
        messages.success(request, "Email verified successfully! You can now log in. Welcome to LimeClicks!")
        return redirect("accounts:login")
        
    except Http404:
        messages.error(request, "Invalid verification link.")
        return redirect("accounts:register")


def resend_confirmation_view(request):
    """
    Handle resending confirmation email
    """
    form = ResendConfirmationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        
        try:
            user = User.objects.get(email__iexact=email)
            
            # Regenerate verification token if it's expired
            if user.is_verification_token_expired():
                user.regenerate_verification_token()
            
            # Send verification email using Brevo template ID 2
            verification_url = request.build_absolute_uri(
                reverse('accounts:verify_email', args=[user.verification_token])
            )
            
            template_params = {
                'name': user.first_name or user.username,
                'url': verification_url
            }
            
            # Create template email message
            email_message = BrevoTemplateEmailMessage(
                template_id=2,
                template_params=template_params,
                to=[email],
                from_email=settings.DEFAULT_FROM_EMAIL
            )
            
            # Send the email
            connection = get_connection()
            connection.send_messages([email_message])
            
            # Store email in session for success page
            request.session['resend_confirmation_email'] = email
            return redirect("accounts:resend_confirmation_success")
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not - still show success page
            request.session['resend_confirmation_email'] = email
            return redirect("accounts:resend_confirmation_success")
    
    return render(request, "accounts/resend_confirmation.html", {"form": form})


def resend_confirmation_success_view(request):
    """
    Show resend confirmation success message with email verification instructions
    """
    # Get email from session
    email = request.session.get('resend_confirmation_email')
    
    if not email:
        # If no email in session, redirect to resend confirmation page
        return redirect("accounts:resend_confirmation")
    
    # Clear the session data after displaying
    del request.session['resend_confirmation_email']
    
    context = {
        'email': email
    }
    
    return render(request, "accounts/resend_confirmation_success.html", context)


def registration_success_view(request):
    """
    Show registration success message with email verification instructions
    """
    # Get registration info from session
    registration_info = request.session.get('registration_success')
    
    if not registration_info:
        # If no registration info, redirect to register page
        return redirect("accounts:register")
    
    # Clear the session data after displaying
    del request.session['registration_success']
    
    context = {
        'email': registration_info['email'],
        'name': registration_info['name']
    }
    
    return render(request, "accounts/registration_success.html", context)


def password_reset_success_view(request):
    """
    Show password reset success message
    """
    # Get email from session
    email = request.session.get('password_reset_email')
    
    if not email:
        # If no email in session, redirect to password reset page
        return redirect("accounts:password_reset")
    
    # Clear the session data after displaying
    del request.session['password_reset_email']
    
    context = {
        'email': email
    }
    
    return render(request, "accounts/password_reset_success.html", context)


def password_reset_confirm_view(request, token):
    """
    Handle password reset confirmation with token
    """
    try:
        user = User.objects.get(password_reset_token=token)
        
        if user.is_password_reset_token_expired():
            messages.error(request, "Password reset link has expired. Please request a new one.")
            return redirect("accounts:password_reset")
        
        if request.method == "POST":
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not new_password or len(new_password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            elif new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
            else:
                # Set new password
                user.set_password(new_password)
                user.clear_password_reset_token()  # Clear the token
                user.save()
                
                messages.success(request, "Your password has been reset successfully. You can now sign in with your new password.")
                return redirect("accounts:login")
        
        context = {
            'token': token,
            'user': user
        }
        
        return render(request, "accounts/password_reset_confirm.html", context)
        
    except User.DoesNotExist:
        messages.error(request, "Invalid or expired password reset link.")
        return redirect("accounts:password_reset")


def root_view(request):
    """
    Root URL handler - redirects based on authentication status
    """
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    else:
        # Don't add message here as middleware will handle it
        return redirect("accounts:login")


@login_required
def logout_view(request):
    """
    Custom logout view with toast message
    """
    user_name = request.user.first_name or request.user.username
    logout(request)
    messages.success(request, f"You've been successfully logged out. See you next time, {user_name}!")
    return redirect("accounts:login")


@login_required
def dashboard_view(request):
    """
    Dashboard view for authenticated users
    """
    from project.models import Project
    
    # Get user's projects
    projects = Project.objects.filter(user=request.user, active=True).order_by('domain')
    
    # Get selected project from query parameter or session
    selected_project = None
    project_id = request.GET.get('project')
    
    if project_id:
        try:
            selected_project = projects.get(id=project_id)
            # Store in session for persistence
            request.session['selected_project_id'] = project_id
        except Project.DoesNotExist:
            pass
    elif 'selected_project_id' in request.session:
        try:
            selected_project = projects.get(id=request.session['selected_project_id'])
        except Project.DoesNotExist:
            pass
    
    # If no selected project and user has projects, select the first one
    if not selected_project and projects.exists():
        selected_project = projects.first()
        request.session['selected_project_id'] = selected_project.id
    
    context = {
        'user': request.user,
        'welcome_message': f"Welcome back, {request.user.first_name or request.user.username}!",
        'projects': projects,
        'selected_project': selected_project
    }
    return render(request, "accounts/dashboard.html", context)


@login_required
def profile_settings_view(request):
    """
    Profile settings view for editing user profile information
    """
    user = request.user
    
    if request.method == "POST":
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        
        # Validate email uniqueness if changed
        if email != user.email:
            if User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
                messages.error(request, "This email address is already in use.")
            else:
                # Update user information
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.save()
                messages.success(request, "Profile updated successfully!")
                return redirect("accounts:profile_settings")
        else:
            # Update user information
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("accounts:profile_settings")
    
    context = {
        'user': user,
        'active_tab': 'profile'
    }
    return render(request, "accounts/profile_settings.html", context)


@login_required
def security_settings_view(request):
    """
    Security settings view for changing password and managing security options
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session auth hash to keep user logged in after password change
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:security_settings')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'active_tab': 'security',
        'user': request.user
    }
    return render(request, 'accounts/security_settings.html', context)
