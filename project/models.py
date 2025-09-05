from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets
import uuid


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_projects')
    domain = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='ProjectMember', related_name='shared_projects')

    @staticmethod
    def clean_domain_string(domain):
        """Clean a domain string - remove protocol, www, path, etc."""
        from core.utils import clean_domain_string
        return clean_domain_string(domain)
    
    def clean(self):
        """Clean and validate the domain"""
        from django.core.exceptions import ValidationError
        
        if self.domain:
            self.domain = self.clean_domain_string(self.domain)
            
            # Validate domain has at least one dot
            if '.' not in self.domain:
                raise ValidationError("Please enter a valid domain name (e.g., example.com)")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_favicon_url(self, size=64):
        """Get Google favicon URL for this domain"""
        return f"https://www.google.com/s2/favicons?domain={self.domain}&sz={size}"
    
    def get_cached_favicon_url(self, size=64):
        """Get cached favicon URL using our proxy (reduces Google API calls)"""
        from django.urls import reverse
        return reverse('project:favicon_proxy', kwargs={'domain': self.domain}) + f'?size={size}'

    def __str__(self):
        return f"{self.domain} - {self.title or 'Untitled'}"

    class Meta:
        ordering = ['-created_at']


class ProjectRole(models.TextChoices):
    OWNER = 'OWNER', 'Owner'
    MEMBER = 'MEMBER', 'Member'  # Can manage keywords and view site audit


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=10, choices=ProjectRole.choices, default=ProjectRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['project', 'user']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.project.domain} ({self.role})"


class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    REVOKED = 'REVOKED', 'Revoked'
    EXPIRED = 'EXPIRED', 'Expired'


class ProjectInvitation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=ProjectRole.choices, default=ProjectRole.MEMBER)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_invitations')
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=14)
        self.email = self.email.lower()
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        return self.status == InvitationStatus.PENDING and not self.is_expired()
    
    def accept(self, user):
        if not self.is_valid():
            raise ValueError("Invitation is not valid")
        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save()
        
        ProjectMember.objects.get_or_create(
            project=self.project,
            user=user,
            defaults={'role': self.role}
        )
    
    def revoke(self):
        self.status = InvitationStatus.REVOKED
        self.save()
    
    def regenerate_token(self):
        self.token = uuid.uuid4()
        self.expires_at = timezone.now() + timezone.timedelta(days=14)
        self.save()
        return self.token
    
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'email'],
                condition=models.Q(status=InvitationStatus.PENDING),
                name='unique_pending_invitation'
            )
        ]
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.project.domain} ({self.status})"
