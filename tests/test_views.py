from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()

LOGIN_URL = "/user_manager/login"
LOGOUT_URL = "/user_manager/logout"


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="hunter2")

    def test_get_renders_login_form(self):
        response = self.client.get(LOGIN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_manager/login.html")

    def test_successful_login_redirects_to_login_redirect_url(self):
        response = self.client.post(LOGIN_URL, {"username": "ada", "password": "hunter2"})
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_failed_login_rerenders_form_with_error(self):
        response = self.client.post(LOGIN_URL, {"username": "ada", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect username or password.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_post_fields_do_not_raise(self):
        """A bot posting an empty body used to raise MultiValueDictKeyError -> 500."""
        response = self.client.post(LOGIN_URL, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect username or password.")

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(LOGIN_URL, {"username": "ada", "password": "hunter2"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_already_authenticated_user_is_redirected(self):
        self.client.force_login(self.user)
        response = self.client.get(LOGIN_URL)
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_safe_next_is_honoured(self):
        response = self.client.post(
            LOGIN_URL + "?next=/reports/", {"username": "ada", "password": "hunter2"}
        )
        self.assertRedirects(response, "/reports/", fetch_redirect_response=False)

    def test_offsite_next_is_rejected_on_login(self):
        response = self.client.post(
            LOGIN_URL + "?next=https://evil.example/",
            {"username": "ada", "password": "hunter2"},
        )
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_offsite_next_is_rejected_when_already_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(LOGIN_URL + "?next=https://evil.example/")
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_scheme_relative_next_is_rejected(self):
        """//evil.example is a URL with no scheme, and browsers follow it off-site."""
        response = self.client.get(LOGIN_URL + "?next=//evil.example/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "//evil.example/")


@override_settings(CHI_AUTH_USE_MIDDLEWARE=True, CHI_AUTH_URL="https://chi-tools.uc.edu/auth/")
class LoginViewUnderHeaderSsoTests(TestCase):
    """With header SSO the view cannot sign anyone in itself, so it hands off to CHI Auth."""

    CHI_AUTH_LOGIN = "https://chi-tools.uc.edu/auth/login"

    def test_get_redirects_to_chi_auth_instead_of_rendering_the_form(self):
        response = self.client.get(LOGIN_URL)
        self.assertRedirects(
            response, f"{self.CHI_AUTH_LOGIN}?uri=%2Fdashboard%2F", fetch_redirect_response=False
        )

    def test_next_is_carried_through_as_uri(self):
        response = self.client.get(LOGIN_URL + "?next=/reports/2")
        self.assertRedirects(
            response, f"{self.CHI_AUTH_LOGIN}?uri=%2Freports%2F2", fetch_redirect_response=False
        )

    def test_uri_is_last_and_fully_quoted(self):
        """CHI Auth reads ‘uri’ from the raw query string to the end, so a destination
        with a query string of its own must not be able to read as more parameters."""
        response = self.client.get(LOGIN_URL + "?next=/logs%3Fpage%3D2%26uri%3D/evil")
        self.assertEqual(
            response["Location"],
            f"{self.CHI_AUTH_LOGIN}?uri=%2Flogs%3Fpage%3D2%26uri%3D%2Fevil",
        )

    def test_offsite_next_is_still_rejected(self):
        response = self.client.get(LOGIN_URL + "?next=https://evil.example/")
        self.assertRedirects(
            response, f"{self.CHI_AUTH_LOGIN}?uri=%2Fdashboard%2F", fetch_redirect_response=False
        )

    def test_no_password_is_accepted_here(self):
        """A POST is a handoff too — this view must never authenticate under header SSO."""
        User.objects.create_user(username="ada", password="hunter2")
        response = self.client.post(LOGIN_URL, {"username": "ada", "password": "hunter2"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.CHI_AUTH_LOGIN))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_authenticated_user_is_not_sent_out_to_chi_auth(self):
        """Otherwise every request from a signed-in user bounces off CHI Auth and back."""
        user = User.objects.create_user(username="ada", password="hunter2")
        self.client.force_login(user)
        response = self.client.get(LOGIN_URL)
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="hunter2")
        self.client.force_login(self.user)

    def test_post_logs_out_and_redirects(self):
        response = self.client.post(LOGOUT_URL)
        self.assertRedirects(response, "/goodbye/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_is_rejected(self):
        response = self.client.get(LOGOUT_URL)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_offsite_next_is_rejected_on_logout(self):
        response = self.client.post(LOGOUT_URL, {"next": "https://evil.example/"})
        self.assertRedirects(response, "/goodbye/", fetch_redirect_response=False)

    def test_anonymous_logout_is_a_no_op_redirect(self):
        self.client.logout()
        response = self.client.post(LOGOUT_URL)
        self.assertRedirects(response, "/goodbye/", fetch_redirect_response=False)


OFFSITE_NEXTS = [
    "https://evil.example/",
    "//evil.example/",
    "////evil.example",
    "https://testserver.evil.example/",  # our host as a prefix of theirs
    "http://evil.example\\@testserver/",  # backslash is not a userinfo separator
    "/\\evil.example",  # browsers read \ as / in the authority
    "\\\\evil.example",
    "http:/\\evil.example",
    "https:evil.example",  # scheme with no //, resolved as a host by some parsers
    "\t//evil.example",  # control characters are stripped before parsing
    "/\t/evil.example",
    "javascript:alert(1)",
    "data:text/html,<script>1</script>",
]


class OffsiteNextTests(TestCase):
    """No ``next`` may take the browser off this site. It is a URL an attacker chooses and
    a user follows from a page that just handled their credentials, so the whole value of
    the sign-in page as somewhere safe to type a password rests on this holding.

    Both views delegate to ``_safe_redirect_url``; these pin the outcome rather than the
    mechanism, so a refactor that stopped calling it would fail here.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="hunter2")

    def test_login_rejects_them_on_the_authenticated_path(self):
        for nxt in OFFSITE_NEXTS:
            with self.subTest(next=nxt):
                self.client.force_login(self.user)
                response = self.client.get(LOGIN_URL, {"next": nxt})
                self.assertEqual(response["Location"], "/dashboard/")

    def test_login_rejects_them_on_the_password_path(self):
        for nxt in OFFSITE_NEXTS:
            with self.subTest(next=nxt):
                self.client.logout()
                response = self.client.post(
                    f"{LOGIN_URL}?next={quote(nxt, safe='')}",
                    {"username": "ada", "password": "hunter2"},
                )
                self.assertEqual(response["Location"], "/dashboard/")

    def test_logout_rejects_them(self):
        for nxt in OFFSITE_NEXTS:
            with self.subTest(next=nxt):
                self.client.force_login(self.user)
                response = self.client.post(LOGOUT_URL, {"next": nxt})
                self.assertEqual(response["Location"], "/goodbye/")

    @override_settings(CHI_AUTH_USE_MIDDLEWARE=True, CHI_AUTH_URL="https://chi-tools.uc.edu/auth/")
    def test_none_of_them_reaches_chi_auth_as_a_uri(self):
        """The handoff must not become a way to launder a destination past the check."""
        for nxt in OFFSITE_NEXTS:
            with self.subTest(next=nxt):
                self.client.force_login(self.user)
                response = self.client.post(LOGOUT_URL, {"next": nxt})
                self.assertEqual(
                    response["Location"],
                    "https://chi-tools.uc.edu/auth/logout?uri=%2Fgoodbye%2F",
                )

    def test_a_same_site_path_that_merely_looks_hostile_is_still_honoured(self):
        """`evil.example` here is a path segment on our own host, not a destination.
        Over-rejecting would break ordinary links; the check is about scheme and host."""
        self.client.force_login(self.user)
        response = self.client.post(LOGOUT_URL, {"next": "/redirect?url=https://evil.example"})
        self.assertEqual(response["Location"], "/redirect?url=https://evil.example")


@override_settings(LOGIN_REDIRECT_URL=None, LOGOUT_REDIRECT_URL=None)
class UnconfiguredRedirectTests(TestCase):
    """Django's own default for LOGOUT_REDIRECT_URL is None. Falling back to "/" sends the
    user to the host root, which under a script prefix is another application entirely."""

    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="hunter2")

    @override_settings(FORCE_SCRIPT_NAME="/my_app/")
    def test_logout_falls_back_to_the_script_prefix(self):
        self.client.force_login(self.user)
        response = self.client.post(LOGOUT_URL)
        self.assertRedirects(response, "/my_app/", fetch_redirect_response=False)

    @override_settings(FORCE_SCRIPT_NAME="/my_app/")
    def test_login_falls_back_to_the_script_prefix(self):
        response = self.client.post(LOGIN_URL, {"username": "ada", "password": "hunter2"})
        self.assertRedirects(response, "/my_app/", fetch_redirect_response=False)

    @override_settings(FORCE_SCRIPT_NAME="/my_app/")
    def test_an_offsite_next_falls_back_there_too(self):
        """The fallback is also the rejection path, so it has to be right for both."""
        self.client.force_login(self.user)
        response = self.client.post(LOGOUT_URL, {"next": "https://evil.example/"})
        self.assertRedirects(response, "/my_app/", fetch_redirect_response=False)

    def test_the_root_is_still_the_root_without_a_prefix(self):
        self.client.force_login(self.user)
        response = self.client.post(LOGOUT_URL)
        self.assertRedirects(response, "/", fetch_redirect_response=False)


@override_settings(CHI_AUTH_USE_MIDDLEWARE=True, CHI_AUTH_URL="https://chi-tools.uc.edu/auth/")
class LogoutViewUnderHeaderSsoTests(TestCase):
    """Clearing the local session is only half of signing out: the SSO-* headers sign the
    user straight back in on their next request unless CHI Auth's session goes too."""

    CHI_AUTH_LOGOUT = "https://chi-tools.uc.edu/auth/logout"

    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="hunter2")
        self.client.force_login(self.user)

    def test_the_local_session_is_cleared_before_the_handoff(self):
        response = self.client.post(LOGOUT_URL)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response["Location"], f"{self.CHI_AUTH_LOGOUT}?uri=%2Fgoodbye%2F")

    def test_offsite_next_is_still_rejected(self):
        response = self.client.post(LOGOUT_URL, {"next": "https://evil.example/"})
        self.assertEqual(response["Location"], f"{self.CHI_AUTH_LOGOUT}?uri=%2Fgoodbye%2F")

    @override_settings(LOGOUT_REDIRECT_URL="/auth/logout?uri=/my_app/")
    def test_a_pre_3_1_setting_is_honoured_rather_than_wrapped(self):
        """Every project had to write this by hand before logout_view chained on its own.
        Wrapping it would send the browser to /auth/logout?uri=/auth/logout?uri=/my_app/."""
        response = self.client.post(LOGOUT_URL)
        self.assertEqual(response["Location"], "/auth/logout?uri=/my_app/")

    @override_settings(LOGOUT_REDIRECT_URL="https://chi-tools.uc.edu/auth/logout?uri=/my_app/")
    def test_the_absolute_form_of_that_setting_is_recognised_too(self):
        response = self.client.post(LOGOUT_URL)
        self.assertEqual(response["Location"], "https://chi-tools.uc.edu/auth/logout?uri=/my_app/")

    def test_a_crafted_next_cannot_reach_the_passthrough(self):
        """`next=/auth/logout?uri=…` is same-site, so it passes the safety check. It must
        still be wrapped like any other destination: taking the passthrough would let
        whoever wrote the link choose the ‘uri’ handed to CHI Auth, with only CHI Auth's
        own safe_path standing between that and an off-site redirect."""
        crafted = "/auth/logout?uri=https://evil.example/"
        response = self.client.post(LOGOUT_URL, {"next": crafted})
        self.assertEqual(
            response["Location"], f"{self.CHI_AUTH_LOGOUT}?uri={quote(crafted, safe='')}"
        )
        # and what CHI Auth reads as its own ‘uri’ is that whole path, quoted — not the
        # off-site URL sitting inside it
        self.assertNotIn("://", response["Location"].split("?uri=", 1)[1])

    @override_settings(LOGOUT_REDIRECT_URL="/auth/logout?uri=/my_app/")
    def test_a_crafted_next_cannot_borrow_the_legacy_setting_either(self):
        """Even where the legacy setting is in play, the passthrough is for that exact
        configured value — not for anything a request says looks like it."""
        response = self.client.post(LOGOUT_URL, {"next": "/auth/logout?uri=https://evil.example/"})
        self.assertTrue(response["Location"].startswith(self.CHI_AUTH_LOGOUT))
