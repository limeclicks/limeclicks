from django.apps import AppConfig


class PerformanceAuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance_audit'
    
    def ready(self):
        import performance_audit.signals
