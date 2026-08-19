"""Settings used by ``user_manager``, and their default values.

Don’t edit this directly, each setting can be overridden using the Django settings or
process environment (the Django setting wins).
This file makes a useful reference for all chi_auth settings and their default values.

Values are resolved on each access rather than at import time, so changing a setting
(including with ``@override_settings``) takes effect immediately.
"""

from os import getenv

from django.conf import settings

_UNSET = object()


def _to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in ("TRUE", "1", "YES", "ON")


def _to_list(value):
    """Accept a real sequence, or a comma separated string as it arrives from the environment."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [item.strip() for item in str(value).split(",") if item.strip()]


DEFAULTS = {
    "LOGIN_URL_FOR_LINK": "/user_manager/login",
    "LOGOUT_URL_FOR_LINK": "/user_manager/logout",
    # If using CHI Auth, what is the root URL for the system.
    #
    # Relative on purpose. Every vhost proxies /auth/ for itself, and CHI Auth redirects
    # to a bare path which the browser resolves against *CHI Auth's* host — so an
    # absolute value here sends the user to that host to sign in, sets the session cookie
    # there, and lands them back on that host rather than this app's. Single sign-on does
    # not span domains: the cookie and the SSO-* headers are per-domain. See checks.py
    # W007, which warns when this names a host.
    "CHI_AUTH_URL": "/auth/",
    # you need to provide an access token if using CHI_Auth
    "CHI_AUTH_API_ACCESS_TOKEN": "",
    # seconds to wait on any call out to CHI Auth before giving up
    "CHI_AUTH_TIMEOUT": 5,
    # if false, a user can only login to the system if they already have a local user account
    # if true, a local account will be auto-created for any user who successfully authenticates
    "CHI_AUTH_AUTOCREATE_LOCAL_USER": False,
    # what credentials should be accepted from CHI Auth? (comma separated string)
    # local: user account in CHI Auth
    # ucad: user account in UC Active Directory (only works if server is on UC network)
    "CHI_AUTH_CHECK_SYSTEMS": "local, ucad",
    # if true, locally created users will automatically get accounts in chi-auth
    "CHI_AUTH_AUTOCREATE_CHI_AUTH_USER": False,
    # is header SSO in use — an upstream nginx authenticating against CHI Auth and passing
    # identity as SSO-* headers for ChiAuthLoginMiddleware to read? The project is what
    # installs the middleware; this is how the rest of the package knows it did. login_view
    # reads it to decide whether to collect a password itself or hand off to CHI Auth.
    "CHI_AUTH_USE_MIDDLEWARE": False,
    # addresses (IPs or CIDR ranges) of the nginx servers allowed to set the SSO-* headers that
    # ChiAuthLoginMiddleware reads. Empty means “trust every client”, which is only safe if the
    # app server cannot be reached except through that nginx — see checks.py.
    "CHI_AUTH_TRUSTED_PROXIES": [],
    # dotted path to the abstract user model that user_manager.models.User is built from
    "USER_MANAGER_ABSTRACT_USER_MODEL": "project.abstract_user_model.AbstractCustomUser",
    "SITE_TITLE": "Center for Health Informatics",
    "CONTACT_EMAIL": "combmichi@uc.edu",
    "UC_PASSWORD_MANAGER_URL": "https://www.uc.edu/sspr",
    # Base URL of the shared CHI asset library, trailing slash included; the sign-in
    # template links its stylesheet and favicon from here. Absolute by default so an
    # existing consumer that says nothing keeps the styling it has, but overridable —
    # a project served under several hostnames (or one that wants same-origin assets
    # for a CSP) sets it to "/assets/". Templates concatenate directly onto it.
    "ASSETS_URL": "https://chi.uc.edu/assets/",
}

# settings that need converting when they arrive as a string from the process environment
CASTS = {
    "CHI_AUTH_TIMEOUT": float,
    "CHI_AUTH_AUTOCREATE_LOCAL_USER": _to_bool,
    "CHI_AUTH_AUTOCREATE_CHI_AUTH_USER": _to_bool,
    "CHI_AUTH_USE_MIDDLEWARE": _to_bool,
    "CHI_AUTH_TRUSTED_PROXIES": _to_list,
}


def get_setting(setting_name, alt=_UNSET):
    """Read a setting from the Django settings, then the environment, then the default."""
    if alt is _UNSET:
        try:
            alt = DEFAULTS[setting_name]
        except KeyError:
            raise AttributeError(f"{setting_name} is not a user_manager setting") from None

    if hasattr(settings, setting_name):
        value = getattr(settings, setting_name)
    else:
        value = getenv(setting_name, _UNSET)
        if value is _UNSET:
            value = alt

    cast = CASTS.get(setting_name)
    return cast(value) if cast else value


def __getattr__(name):
    """Expose every setting as a module attribute, resolved lazily on access."""
    if name in DEFAULTS:
        return get_setting(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
