from django.apps import AppConfig


class UserManagerConfig(AppConfig):
    name = 'user_manager'
    
    def ready(self):
        import user_manager.signals
