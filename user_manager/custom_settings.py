"""Settings used by ``user_manager``, and their default values.

Don’t edit this directly — a consuming project overrides any of these in its own
``settings.py``. That is the *only* configuration surface: there is no process environment
fallback, so a variable set in a deployment does nothing unless the project's settings read
it. A project wanting a setting to be deployment configurable writes the ``getenv`` call
itself, as it already does for everything else it configures.

This file makes a useful reference for all chi_auth settings and their default values.

Values are resolved on each access rather than at import time, so changing a setting
(including with ``@override_settings``) takes effect immediately.
"""

from django.conf import settings

_UNSET = object()


def _to_list(value):
    """Accept a real sequence, or a comma separated string as a project's settings give it."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _to_bool(value):
    """Parse a boolean that a project's settings supplied as a string.

    Deliberately strict, matching the ``env_bool`` helper every consumer's ``settings.py``
    uses: ``'1'``, ``'yes'`` and ``'on'`` are all False. A setting that silently reads as
    False when someone wrote ``'1'`` is worse than one that never accepts ``'1'``, because
    the first kind is only noticed in production — and the booleans here decide whether
    header SSO is in use and whether accounts get provisioned.
    """
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() == "TRUE"


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
    # Provision a local account for a user CHI Auth authenticates but this app has never
    # seen? True on both login paths — the header SSO middleware and ChiAuthBackend.
    #
    # Defaults True because that is what every deployment already does: before 4.0.0 the
    # middleware provisioned unconditionally and never consulted this setting (issue #8),
    # and header SSO is how everyone arrives. A default of False would have turned that
    # into "provisions no one" on the pin bump, silently, for every consumer that had
    # never set it. A deployment that genuinely wants closed provisioning sets False and
    # gets it on both paths.
    "CHI_AUTH_AUTOCREATE_LOCAL_USER": True,
    # what credentials should be accepted from CHI Auth? (comma separated string)
    # local: user account in CHI Auth
    # ucad: user account in UC Active Directory (only works if server is on UC network)
    #
    # The order is not merely which directory is asked first — it decides which one
    # authenticates a password when an account exists in both. "ucad, local" is what all
    # four deployed consumers set, so it is the default rather than something each of
    # them restates.
    "CHI_AUTH_CHECK_SYSTEMS": "ucad, local",
    # is header SSO in use — an upstream nginx authenticating against CHI Auth and passing
    # identity as SSO-* headers for ChiAuthLoginMiddleware to read? The project is what
    # installs the middleware; this is how the rest of the package knows it did. login_view
    # reads it to decide whether to collect a password itself or hand off to CHI Auth.
    "CHI_AUTH_USE_MIDDLEWARE": False,
    # addresses (IPs or CIDR ranges) of the nginx servers allowed to set the SSO-* headers that
    # ChiAuthLoginMiddleware reads. Empty means “trust every client”, which is only safe if the
    # app server cannot be reached except through that nginx — see checks.py W001.
    #
    # This works because of the deployment topology, and only because of it: the sidecar
    # shares the app container's network namespace and gunicorn binds 127.0.0.1, so nginx
    # reaches it as 127.0.0.1 and nothing else can. Set it in compose.yaml, not
    # settings.env — it is a property of the container topology, and a deployment-local
    # override re-opens the bypass. A value broader than /32 readmits the bridge gateway.
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

# settings that need converting when a project supplies them as a string
CASTS = {
    "CHI_AUTH_TIMEOUT": float,
    "CHI_AUTH_AUTOCREATE_LOCAL_USER": _to_bool,
    "CHI_AUTH_USE_MIDDLEWARE": _to_bool,
    "CHI_AUTH_TRUSTED_PROXIES": _to_list,
}


def get_setting(setting_name, alt=_UNSET):
    """Read a setting from the Django settings, falling back to the default."""
    if alt is _UNSET:
        try:
            alt = DEFAULTS[setting_name]
        except KeyError:
            raise AttributeError(f"{setting_name} is not a user_manager setting") from None

    value = getattr(settings, setting_name, alt)

    cast = CASTS.get(setting_name)
    return cast(value) if cast else value


def __getattr__(name):
    """Expose every setting as a module attribute, resolved lazily on access."""
    if name in DEFAULTS:
        return get_setting(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
