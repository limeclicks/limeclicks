from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

User = get_user_model()

class RegisterForm(forms.Form):
    name = forms.CharField(
        label="Name", 
        max_length=150,
        error_messages={
            'required': 'Please tell us your name',
            'max_length': 'That name is a bit too long. Please use 150 characters or less.'
        }
    )
    email = forms.EmailField(
        label="Email",
        error_messages={
            'required': 'We need your email to create your account',
            'invalid': 'That doesn\'t look like a valid email address. Please check and try again.'
        }
    )
    password = forms.CharField(
        label="Password", 
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please create a password for your account'
        }
    )
    password_confirm = forms.CharField(
        label="Confirm password", 
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please confirm your password'
        }
    )
    # Always include reCAPTCHA for registration
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox,
        error_messages={
            'required': 'Please complete the verification to prove you\'re human'
        }
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "It looks like you already have an account with this email. Try signing in instead!"
            )
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            # Simple length validation
            if len(password) < 8:
                raise ValidationError(
                    "Password must be at least 8 characters long."
                )
            
            # Check for common weak passwords
            common_passwords = ['password', '12345678', 'qwerty', 'abc123', 'password123']
            if password.lower() in common_passwords:
                raise ValidationError(
                    "That's a very common password that's easy to guess. Please choose something more unique to you."
                )
                
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", 
                "The passwords you entered don't match. Please try typing them again.")
        return cleaned


class LoginForm(forms.Form):
    username = forms.EmailField(
        label="Email",
        error_messages={
            'required': 'Please enter your email address',
            'invalid': 'That doesn\'t look like a valid email address'
        }
    )
    password = forms.CharField(
        label="Password", 
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please enter your password'
        }
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only add reCAPTCHA if not in debug mode (for easier testing)
        if not settings.DEBUG:
            self.fields['captcha'] = ReCaptchaField(
                widget=ReCaptchaV2Checkbox,
                error_messages={
                    'required': 'Please complete the verification'
                }
            )


class PasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        error_messages={
            'required': 'Please enter your email address',
            'invalid': 'That doesn\'t look like a valid email address'
        }
    )
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox,
        error_messages={
            'required': 'Please complete the verification'
        }
    )


class ResendConfirmationForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        error_messages={
            'required': 'Please enter your email address',
            'invalid': 'That doesn\'t look like a valid email address'
        }
    )
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox,
        error_messages={
            'required': 'Please complete the verification'
        }
    )
    
    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        try:
            user = User.objects.get(email__iexact=email)
            if user.email_verified:
                raise forms.ValidationError(
                    "Good news! This email is already verified. You can sign in now."
                )
            return email
        except User.DoesNotExist:
            raise forms.ValidationError(
                "We couldn't find an account with that email address. Maybe you used a different one?"
            )