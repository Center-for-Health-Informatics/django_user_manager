"""System checks, so misconfigurations that silently weaken authentication get surfaced
by ``manage.py check`` instead of going unnoticed.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register

from . import custom_settings, views

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

    # CHI_AUTH_USE_MIDDLEWARE is what login_view reads to decide whether to collect a
    # password itself or hand off to CHI Auth; MIDDLEWARE is what actually installs the
    # middleware. A project sets both, and nothing ties them together — so say something
    # when they disagree, in either direction.
    if custom_settings.CHI_AUTH_USE_MIDDLEWARE and CHI_AUTH_MIDDLEWARE not in middleware:
        errors.append(
            Warning(
                f"CHI_AUTH_USE_MIDDLEWARE is on but {CHI_AUTH_MIDDLEWARE} is not in "
                f"MIDDLEWARE. The login view hands off to CHI Auth, but nothing reads the "
                f"SSO-* headers the browser comes back with, so nobody can sign in.",
                hint=f"Add {CHI_AUTH_MIDDLEWARE} to MIDDLEWARE after {AUTH_MIDDLEWARE}, or "
                "turn CHI_AUTH_USE_MIDDLEWARE off.",
                id="user_manager.W004",
            )
        )
    elif CHI_AUTH_MIDDLEWARE in middleware and not custom_settings.CHI_AUTH_USE_MIDDLEWARE:
        errors.append(
            Warning(
                f"{CHI_AUTH_MIDDLEWARE} is in MIDDLEWARE but CHI_AUTH_USE_MIDDLEWARE is "
                f"off, so the login view collects a password of its own instead of handing "
                f"off to CHI Auth. That login leaves no upstream session for logout to "
                f"chain to.",
                hint="Set CHI_AUTH_USE_MIDDLEWARE=True, unless the local login form is "
                "deliberately offered alongside header SSO.",
                id="user_manager.W005",
            )
        )

    # Before 3.1 every project wrote CHI Auth's logout into LOGOUT_REDIRECT_URL by hand,
    # because logout_view did not chain there itself. It does now, so such a value is
    # redundant — honoured rather than wrapped, so sign-out keeps working, but it means
    # the app lands the user on CHI Auth instead of back on itself.
    if custom_settings.CHI_AUTH_USE_MIDDLEWARE and views._already_chi_auth(
        getattr(settings, "LOGOUT_REDIRECT_URL", "") or "", "logout"
    ):
        errors.append(
            Warning(
                "LOGOUT_REDIRECT_URL points at CHI Auth's logout, which user_manager has "
                "chained on to by itself since 3.1.0. The user is left on CHI Auth after "
                "signing out rather than back on this site.",
                hint="Set LOGOUT_REDIRECT_URL to where the user should land on this site "
                "once signed out — the site root, or FORCE_SCRIPT_NAME under a sub-path.",
                id="user_manager.W006",
            )
        )

    # CHI Auth redirects to a bare path, which the browser resolves against whichever
    # host it was sent to — so naming a host here only works while that host is also the
    # one serving this app. It is a warning rather than an error because an absolute
    # value pointing at the app's own host does work, and an existing deployment should
    # not fail to start over it.
    chi_auth_url = urlparse(custom_settings.CHI_AUTH_URL)
    if chi_auth_url.scheme or chi_auth_url.netloc:
        errors.append(
            Warning(
                f"CHI_AUTH_URL names a host ({custom_settings.CHI_AUTH_URL!r}). Single "
                "sign-on is per-domain: the session cookie and the SSO-* headers belong "
                "to the host that signs the user in, and CHI Auth redirects back to a "
                "bare path resolved against that same host. If it is not the host serving "
                "this app, users sign in there and land there.",
                hint='Use a relative "/auth/" — every vhost proxies it for itself.',
                id="user_manager.W007",
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
