from django.apps import AppConfig


class UserManagerConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "user_manager"

    def ready(self):
        # importing these registers the system checks and connects the post_save receiver
        from . import checks, signals  # noqa: F401
