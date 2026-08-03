"""System checks, so misconfigurations that silently weaken authentication get surfaced
by ``manage.py check`` instead of going unnoticed.
"""

from django.conf import settings
from django.core.checks import Error, Warning, register

from . import custom_settings

AUTH_MIDDLEWARE = "django.contrib.auth.middleware.AuthenticationMiddleware"
CHI_AUTH_MIDDLEWARE = "user_manager.middleware.ChiAuthLoginMiddleware"
INSPECT_MIDDLEWARE = "user_manager.middleware.InspectHeadersMiddleware"


@register()
def check_migration_modules(app_configs, **kwargs):
    """user_manager ships no migrations, so without MIGRATION_MODULES it is an unmigrated
    app: skipped by makemigrations autodetection, and its tables only created by
    --run-syncdb. That failure is silent, so say something about it.
    """
    if "user_manager" in getattr(settings, "MIGRATION_MODULES", {}):
        return []

    return [
        Warning(
            "MIGRATION_MODULES has no entry for 'user_manager', so the app is unmigrated: "
            "makemigrations will ignore it and its tables will only be created by "
            "`migrate --run-syncdb`.",
            hint="Set MIGRATION_MODULES = {'user_manager': 'project.user_manager_migrations'} "
            "and makemigrations into that package, so the migrations live in your repo "
            "rather than in site-packages. Use None instead of a path to opt out.",
            id="user_manager.W003",
        )
    ]


@register("security")
def check_chi_auth_middleware(app_configs, **kwargs):
    errors = []
    middleware = list(getattr(settings, "MIDDLEWARE", []))

    if CHI_AUTH_MIDDLEWARE in middleware:
        if AUTH_MIDDLEWARE not in middleware:
            errors.append(
                Error(
                    f"{CHI_AUTH_MIDDLEWARE} requires {AUTH_MIDDLEWARE} in MIDDLEWARE.",
                    id="user_manager.E001",
                )
            )
        elif middleware.index(AUTH_MIDDLEWARE) > middleware.index(CHI_AUTH_MIDDLEWARE):
            errors.append(
                Error(
                    f"{CHI_AUTH_MIDDLEWARE} must be listed after {AUTH_MIDDLEWARE} in "
                    f"MIDDLEWARE, otherwise request.user is not available to it.",
                    id="user_manager.E002",
                )
            )

        if not custom_settings.CHI_AUTH_TRUSTED_PROXIES:
            errors.append(
                Warning(
                    f"{CHI_AUTH_MIDDLEWARE} trusts the SSO-* request headers from any "
                    f"client because CHI_AUTH_TRUSTED_PROXIES is empty. Anyone able to "
                    f"reach this server without going through nginx can authenticate as "
                    f"any user by sending an SSO-Username header.",
                    hint="Set CHI_AUTH_TRUSTED_PROXIES to the address(es) of your nginx "
                    "server, and make sure nginx strips inbound SSO-* headers.",
                    id="user_manager.W001",
                )
            )

    if INSPECT_MIDDLEWARE in middleware and getattr(settings, "SPECIAL_LOG_FOLDER", None):
        if not settings.DEBUG:
            errors.append(
                Warning(
                    f"{INSPECT_MIDDLEWARE} is active and will write the headers of every "
                    f"request to SPECIAL_LOG_FOLDER. It is a debugging aid only.",
                    hint="Remove it from MIDDLEWARE, or unset SPECIAL_LOG_FOLDER.",
                    id="user_manager.W002",
                )
            )

    return errors
