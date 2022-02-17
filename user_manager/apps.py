from django.apps import AppConfig


class UserManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'user_manager'
    
    def ready(self):
        import user_manager.signals
