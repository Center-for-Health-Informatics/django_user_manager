import datetime
import ipaddress
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.exceptions import ImproperlyConfigured

from . import custom_settings

logger = logging.getLogger(__name__)

SSO_USERNAME_HEADER = "HTTP_SSO_USERNAME"

# CHI Auth sends these when it has no value to report
SSO_EMPTY_VALUES = frozenset(["", "none", "null"])

# headers that must never reach the header inspection log
SENSITIVE_HEADERS = frozenset(
    [
        "HTTP_AUTHORIZATION",
        "HTTP_COOKIE",
        "HTTP_PROXY_AUTHORIZATION",
        "HTTP_X_ACCESS_TOKEN",
        "HTTP_X_PASSWORD",
    ]
)

DEFAULT_SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"


class InspectHeadersMiddleware:
    """Append the inbound HTTP headers of every request to SPECIAL_LOG_FOLDER.

    This is a debug aid for setting up header based SSO behind nginx. **Don’t leave it
    enabled in production**: even with credentials redacted, the log records who is
    visiting what. It does nothing at all unless SPECIAL_LOG_FOLDER is set.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # code to be executed before view
        log_folder = getattr(settings, "SPECIAL_LOG_FOLDER", None)
        if not log_folder:
            return self.get_response(request)

        log_file = Path(log_folder) / "header_inspection.log"
        with log_file.open(mode="a") as file_object:
            print("", file=file_object)
            print(datetime.datetime.now(), file=file_object)
            for key in sorted(request.META):
                if key.startswith("HTTP"):
                    value = "[redacted]" if key in SENSITIVE_HEADERS else request.META[key]
                    print(key, value, file=file_object)

        return self.get_response(request)


class ChiAuthLoginMiddleware:
    """Log a user in from the SSO-* headers set by an upstream CHI Auth nginx.

    Must be listed *after* django.contrib.auth.middleware.AuthenticationMiddleware.

    Security: these headers are trusted, so nginx must strip any inbound SSO-* headers
    before setting its own, and the app server must not be reachable except through
    nginx — otherwise anyone can authenticate as anyone by sending SSO-Username.

    CHI_AUTH_TRUSTED_PROXIES has this middleware enforce the second requirement itself.
    That works only under the deployment topology the estate now uses: the sidecar shares
    the app container's network namespace and gunicorn binds 127.0.0.1, so a request
    arriving through nginx has REMOTE_ADDR 127.0.0.1 and nothing off-box can produce one.
    It is defence in depth behind the port binding, not a substitute for it — see
    chi-platform conventions.md, "A published port must name an address that cannot
    default". On a *bridge*-networked sidecar the check cannot distinguish anything,
    because REMOTE_ADDR is then the bridge gateway for proxied and direct requests alike.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hasattr(request, "user"):
            raise ImproperlyConfigured(
                "ChiAuthLoginMiddleware requires "
                "django.contrib.auth.middleware.AuthenticationMiddleware to be listed "
                "before it in MIDDLEWARE."
            )

        username = self.get_sso_username(request)
        # when there is no header we leave request.user alone, so this middleware can sit
        # alongside ordinary session login rather than replacing it
        if username and not self.already_logged_in(request, username):
            oUser = self.get_or_create_user(request, username)
            if oUser is not None:
                # a real session login, so request.user survives without the headers and
                # everything that reads the session (logout, session keyed data) works
                login(request, oUser, backend=self.session_backend())

        # continue to next entry in middleware chain
        return self.get_response(request)

    def get_sso_username(self, request):
        username = (request.META.get(SSO_USERNAME_HEADER) or "").strip()
        if username.lower() in SSO_EMPTY_VALUES:
            return None
        if not self.from_trusted_proxy(request):
            logger.warning(
                "Ignoring %s from untrusted address %s",
                SSO_USERNAME_HEADER,
                request.META.get("REMOTE_ADDR"),
            )
            return None
        return username

    @staticmethod
    def from_trusted_proxy(request):
        trusted = custom_settings.CHI_AUTH_TRUSTED_PROXIES
        if not trusted:
            # not configured; the user_manager.W001 system check warns about this
            return True

        try:
            remote_addr = ipaddress.ip_address(request.META.get("REMOTE_ADDR") or "")
        except ValueError:
            return False

        for entry in trusted:
            try:
                if remote_addr in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                logger.warning("Ignoring invalid CHI_AUTH_TRUSTED_PROXIES entry %r", entry)
        return False

    @staticmethod
    def already_logged_in(request, username):
        # casefold to match get_or_create_user's __iexact lookup. Comparing exactly would
        # miss when the session was established as "jsmith" and the header now says
        # "JSmith" — the same account, so login() would run again on every request,
        # cycling the session key each time.
        return (
            request.user.is_authenticated
            and request.user.get_username().casefold() == username.casefold()
        )

    @staticmethod
    def session_backend():
        """login() needs a backend path that is actually configured, since that is what
        gets stored in the session and used to reload the user on later requests.
        """
        backends = list(getattr(settings, "AUTHENTICATION_BACKENDS", []))
        if not backends or DEFAULT_SESSION_BACKEND in backends:
            return DEFAULT_SESSION_BACKEND
        return backends[0]

    @staticmethod
    def get_or_create_user(request, username):
        User = get_user_model()
        # __iexact, not an exact match: the header carries whatever casing the user typed
        # at CHI Auth, and the directory behind it is case-insensitive. Matching exactly
        # makes "JSmith" and "jsmith" two accounts with separate permissions and separate
        # rows pointing at them. See checks.py W008.
        oUser = User.objects.filter(username__iexact=username).first()
        if not oUser:
            if not custom_settings.CHI_AUTH_AUTOCREATE_LOCAL_USER:
                # the same answer ChiAuthBackend gives on the password path; before 4.0.0
                # this path provisioned regardless and the setting meant nothing here
                logger.warning(
                    "Refusing SSO login for unknown user %r: CHI_AUTH_AUTOCREATE_LOCAL_USER is off",
                    username,
                )
                return None
            oUser = User(
                # stored as the header gave it — folding to lower case here would
                # rewrite the display name of every account created from now on
                username=username,
                email=request.META.get("HTTP_SSO_EMAIL", ""),
                first_name=request.META.get("HTTP_SSO_FIRSTNAME", ""),
                last_name=request.META.get("HTTP_SSO_LASTNAME", ""),
            )
            # they authenticate through CHI Auth, never with a local password
            oUser.set_unusable_password()
            oUser.save()
        elif not oUser.is_active:
            # deactivating an account has to lock it out of the SSO path too
            logger.warning("Refusing SSO login for inactive user %r", username)
            return None
        return oUser
