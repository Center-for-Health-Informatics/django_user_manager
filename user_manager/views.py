from urllib.parse import quote, urlparse

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from . import custom_settings


def _safe_redirect_url(request, url, fallback_setting):
    """Return ``url`` only if it points back at this site, otherwise the configured fallback.

    Without this check, ``?next=https://evil.example/`` would bounce the user off-site
    straight from the page that just collected their password.
    """
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return getattr(settings, fallback_setting, None) or "/"


def chi_auth_url(view_name, destination):
    """Build a CHI Auth URL, carrying ``destination`` as the ‘uri’ parameter.

    ‘uri’, not ‘next’: CHI Auth reads it straight out of the raw query string, taking
    everything from ``uri=`` to the end as the value, because nginx sends
    ``/auth/login?uri=$request_uri`` and cannot percent-encode a variable. Two rules
    follow, and both are the caller's to keep — CHI Auth cannot check either:

    * nothing may come after ‘uri’ in the query string, so it is built last here and
      this function returns a finished URL rather than something to append to;
    * a value starting with "/" is taken verbatim, anything else is unquoted once.
      Quoting the separators too keeps the destination a single opaque parameter, so
      a query string of its own cannot read as more parameters of ours.

    CHI Auth re-checks the result against its own resource list either way.
    """
    return f"{custom_settings.CHI_AUTH_URL}{view_name}?uri={quote(destination, safe='')}"


def chi_auth_login_url(destination):
    return chi_auth_url("login", destination)


def chi_auth_logout_url(destination):
    return chi_auth_url("logout", destination)


def _already_chi_auth(url, view_name):
    """Is ``url`` already pointing at one of CHI Auth's own views?

    Only asked about LOGOUT_REDIRECT_URL, and only to keep upgrading from 3.0 from
    silently breaking sign-out: before 3.1 every project had to write CHI Auth's logout
    into that setting by hand, and wrapping such a value would send the browser to
    ``/auth/logout?uri=/auth/logout?uri=/the/app``. Matched on path so it works whether
    the configured value is absolute or rooted, as both forms are in use.
    """
    chi_auth_path = urlparse(custom_settings.CHI_AUTH_URL).path
    return urlparse(url).path == f"{chi_auth_path}{view_name}"


@never_cache
@csrf_protect
def login_view(request):
    next_url = _safe_redirect_url(request, request.GET.get("next"), "LOGIN_REDIRECT_URL")

    if request.user.is_authenticated:
        return redirect(next_url)

    # Under header SSO this view cannot sign anyone in. ChiAuthLoginMiddleware only ever
    # derives a local session from the SSO-* headers, and only CHI Auth can mint the
    # upstream session those headers describe — so the browser has to go there. Rendering
    # the form instead would collect an AD password this app has no reason to see and
    # hand back a local session with no upstream session behind it: single sign-on
    # defeated, and a sign-out that has nothing upstream to chain to.
    if custom_settings.CHI_AUTH_USE_MIDDLEWARE:
        return redirect(chi_auth_login_url(next_url))

    context = {
        "current_page": "login",
        "next": next_url,
    }
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        # authenticates against all settings.AUTHENTICATION_BACKENDS
        oUser = authenticate(request, username=username, password=password)

        if oUser is None:
            context["login_error"] = "Incorrect username or password."
            return render(request, "user_manager/login.html", context)

        # authenticate() records which backend succeeded on the user; login() reuses it,
        # so the session is tied to the backend that actually authenticated them.
        login(request, oUser)
        return redirect(next_url)

    return render(request, "user_manager/login.html", context)


@require_POST
def logout_view(request):
    """Log out and redirect. POST only — a GET logout is CSRF-able and gets triggered
    by link prefetchers, which is why Django dropped GET support from its own LogoutView
    in 5.0. Use a small form with {% csrf_token %} rather than a plain link.

    Under header SSO this runs in the opposite order from signing in: the local session
    has to go first, here, because CHI Auth's logout is GET-only and in another app — a
    cross-app POST would fail CSRF — and only then does the browser chain on to CHI Auth
    to drop the upstream session. Clearing just one of the two is not signing out. Losing
    the local session alone leaves the SSO-* headers to sign the user back in on their
    next request, which is the failure that looks like a broken logout button.
    """
    logout(request)

    next_url = _safe_redirect_url(request, request.POST.get("next"), "LOGOUT_REDIRECT_URL")

    if custom_settings.CHI_AUTH_USE_MIDDLEWARE and not _already_chi_auth(next_url, "logout"):
        return redirect(chi_auth_logout_url(next_url))
    return redirect(next_url)
