from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.utils import timezone


class User(AbstractUser):
    email_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True)
    verification_token_created = models.DateTimeField(auto_now_add=True)
    
    # Password reset tokens
    password_reset_token = models.UUIDField(null=True, blank=True)
    password_reset_token_created = models.DateTimeField(null=True, blank=True)
    
    def is_verification_token_expired(self):
        """Check if verification token is older than 24 hours"""
        if not self.verification_token_created:
            return True
        return timezone.now() - self.verification_token_created > timezone.timedelta(hours=24)
    
    def regenerate_verification_token(self):
        """Generate a new verification token"""
        self.verification_token = uuid.uuid4()
        self.verification_token_created = timezone.now()
        self.save()
    
    def is_password_reset_token_expired(self):
        """Check if password reset token is older than 1 hour"""
        if not self.password_reset_token_created:
            return True
        return timezone.now() - self.password_reset_token_created > timezone.timedelta(hours=1)
    
    def generate_password_reset_token(self):
        """Generate a new password reset token"""
        self.password_reset_token = uuid.uuid4()
        self.password_reset_token_created = timezone.now()
        self.save()
        return self.password_reset_token
    
    def clear_password_reset_token(self):
        """Clear the password reset token after use"""
        self.password_reset_token = None
        self.password_reset_token_created = None
        self.save()
    
    def __str__(self):
        """Display email instead of username in admin dropdowns"""
        if self.email:
            return f"{self.email} - {self.get_full_name() or self.username}"
        return self.username
