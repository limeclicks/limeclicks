from django.apps import AppConfig


class ProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'project'
    
    def ready(self):
        """Import signal handlers when the app is ready"""
        import project.signals  # Import signals to register them
