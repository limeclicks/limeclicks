import uuid
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class BaseAuditHistory(TimestampedModel):
    AUDIT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    TRIGGER_TYPE_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
        ('project_created', 'Project Created'),
        ('webhook', 'Webhook'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=20,
        choices=AUDIT_STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_TYPE_CHOICES,
        default='manual'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    task_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['trigger_type', '-created_at']),
        ]
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_running(self):
        return self.status == 'running'
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_failed(self):
        return self.status == 'failed'
    
    def mark_running(self):
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def mark_failed(self, error_message=None):
        self.status = 'failed'
        self.completed_at = timezone.now()
        if error_message:
            self.error_message = str(error_message)[:5000]  # Limit error message size
        self.save(update_fields=['status', 'completed_at', 'error_message'])


class BaseAuditModel(TimestampedModel):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
        ('disabled', 'Disabled'),
    ]
    
    audit_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='weekly'
    )
    last_audit_at = models.DateTimeField(null=True, blank=True)
    next_audit_at = models.DateTimeField(null=True, blank=True, db_index=True)
    audit_enabled = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['audit_enabled', 'next_audit_at']),
        ]
    
    def calculate_next_audit_time(self):
        if not self.audit_enabled or self.audit_frequency == 'disabled':
            return None
            
        from datetime import timedelta
        now = timezone.now()
        
        frequency_deltas = {
            'daily': timedelta(days=1),
            'weekly': timedelta(days=7),
            'biweekly': timedelta(days=14),
            'monthly': timedelta(days=30),
        }
        
        delta = frequency_deltas.get(self.audit_frequency)
        if delta:
            return now + delta
        return None
    
    def schedule_next_audit(self):
        self.next_audit_at = self.calculate_next_audit_time()
        self.save(update_fields=['next_audit_at'])
    
    def can_run_manual_audit(self, cooldown_minutes=30):
        if not self.last_audit_at:
            return True
        
        from datetime import timedelta
        cooldown = timedelta(minutes=cooldown_minutes)
        return timezone.now() >= self.last_audit_at + cooldown