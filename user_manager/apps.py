from django.apps import AppConfig


class UserManagerConfig(AppConfig):
    # AutoField on purpose, and it is the one place the estate departs from
    # chi-platform conventions.md's "DEFAULT_AUTO_FIELD is BigAutoField".
    #
    # An AppConfig's default_auto_field beats the project's DEFAULT_AUTO_FIELD, so User —
    # the table every other table foreign-keys to — is the estate's only 32-bit key, and
    # the frozen migrations in daedalus, email_service and monitor all record
    # models.AutoField. Changing it is not one migration: it is an AlterField on the pk
    # plus every FK referencing it, in three consumers, one of them on MSSQL. These are
    # small apps and nothing is remotely near 2^31, so the cost buys nothing but tidiness.
    # Recorded as a justified exception in conventions.md rather than migrated.
    default_auto_field = "django.db.models.AutoField"
    name = "user_manager"

    def ready(self):
        # importing this registers the system checks
        from . import checks  # noqa: F401
