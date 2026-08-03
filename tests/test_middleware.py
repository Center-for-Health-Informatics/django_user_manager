import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from user_manager.middleware import ChiAuthLoginMiddleware, InspectHeadersMiddleware

User = get_user_model()

SSO_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "user_manager.middleware.ChiAuthLoginMiddleware",
]

LOGIN_URL = "/user_manager/login"


@override_settings(MIDDLEWARE=SSO_MIDDLEWARE)
class ChiAuthLoginMiddlewareTests(TestCase):
    """Driven through the test client so the whole middleware chain, and the session it
    writes, are exercised the way they are in production.
    """

    def test_header_creates_and_logs_in_a_new_user(self):
        response = self.client.get(
            LOGIN_URL,
            HTTP_SSO_USERNAME="ada",
            HTTP_SSO_EMAIL="ada@example.com",
            HTTP_SSO_FIRSTNAME="Ada",
            HTTP_SSO_LASTNAME="Lovelace",
        )
        user = User.objects.get(username="ada")
        self.assertEqual(user.email, "ada@example.com")
        self.assertEqual(user.first_name, "Ada")
        self.assertFalse(user.has_usable_password())
        # a real session login, not just an attribute on the request
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        self.assertEqual(response.status_code, 302)

    def test_existing_user_is_reused_and_not_duplicated(self):
        user = User.objects.create_user(username="ada", email="ada@example.com")
        self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada")
        self.assertEqual(User.objects.filter(username="ada").count(), 1)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_session_survives_a_later_request_without_the_header(self):
        self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada")
        user = User.objects.get(username="ada")
        self.client.get(LOGIN_URL)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_inactive_user_is_refused(self):
        User.objects.create_user(username="ada", is_active=False)
        with self.assertLogs("user_manager.middleware", "WARNING"):
            self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sentinel_values_are_ignored(self):
        for value in ["", "none", "None", "NULL", "  none  "]:
            with self.subTest(value=value):
                self.client.get(LOGIN_URL, HTTP_SSO_USERNAME=value)
                self.assertFalse(User.objects.exists())
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_no_header_leaves_an_existing_session_alone(self):
        """The old middleware overwrote request.user with AnonymousUser, so it could not
        coexist with ordinary session login."""
        user = User.objects.create_user(username="ada", password="hunter2")
        self.client.force_login(user)
        self.client.get(LOGIN_URL)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    @override_settings(CHI_AUTH_TRUSTED_PROXIES=["10.0.0.1"])
    def test_header_from_untrusted_address_is_ignored(self):
        with self.assertLogs("user_manager.middleware", "WARNING"):
            self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada", REMOTE_ADDR="203.0.113.9")
        self.assertFalse(User.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(CHI_AUTH_TRUSTED_PROXIES=["10.0.0.1"])
    def test_header_from_trusted_address_is_honoured(self):
        self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada", REMOTE_ADDR="10.0.0.1")
        self.assertTrue(User.objects.filter(username="ada").exists())

    @override_settings(CHI_AUTH_TRUSTED_PROXIES="10.0.0.0/24, 192.168.1.5")
    def test_trusted_proxies_accepts_cidr_ranges_and_comma_strings(self):
        self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada", REMOTE_ADDR="10.0.0.77")
        self.assertTrue(User.objects.filter(username="ada").exists())

    @override_settings(CHI_AUTH_TRUSTED_PROXIES=["not-an-address"])
    def test_invalid_trusted_proxy_entry_fails_closed(self):
        with self.assertLogs("user_manager.middleware", "WARNING"):
            self.client.get(LOGIN_URL, HTTP_SSO_USERNAME="ada", REMOTE_ADDR="10.0.0.1")
        self.assertFalse(User.objects.exists())

    def test_requires_authentication_middleware(self):
        request = RequestFactory().get("/")
        middleware = ChiAuthLoginMiddleware(lambda r: HttpResponse())
        with self.assertRaises(ImproperlyConfigured):
            middleware(request)


class InspectHeadersMiddlewareTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_file = Path(self.tmpdir.name) / "header_inspection.log"

    def run_middleware(self, **meta):
        request = RequestFactory().get("/", **meta)
        InspectHeadersMiddleware(lambda r: HttpResponse())(request)

    def test_does_nothing_without_the_setting(self):
        self.run_middleware(HTTP_SSO_USERNAME="ada")
        self.assertFalse(self.log_file.exists())

    def test_logs_headers_and_redacts_credentials(self):
        # no trailing slash: string concatenation used to put the file in the wrong place
        with override_settings(SPECIAL_LOG_FOLDER=self.tmpdir.name):
            self.run_middleware(
                HTTP_SSO_USERNAME="ada",
                HTTP_COOKIE="sessionid=super-secret",
                HTTP_X_PASSWORD="hunter2",
            )

        contents = self.log_file.read_text()
        self.assertIn("HTTP_SSO_USERNAME ada", contents)
        self.assertIn("HTTP_COOKIE [redacted]", contents)
        self.assertIn("HTTP_X_PASSWORD [redacted]", contents)
        self.assertNotIn("super-secret", contents)
        self.assertNotIn("hunter2", contents)
