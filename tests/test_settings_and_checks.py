import os
from unittest import mock

from django.test import SimpleTestCase, override_settings

from user_manager import custom_settings
from user_manager.checks import check_chi_auth_middleware, check_migration_modules
from user_manager.context_processors import settings_context_processor

SSO_MIDDLEWARE = [
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "user_manager.middleware.ChiAuthLoginMiddleware",
]


class GetSettingTests(SimpleTestCase):
    def test_default_is_used_when_nothing_is_configured(self):
        self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "local, ucad")

    @override_settings(CHI_AUTH_CHECK_SYSTEMS="local")
    def test_django_setting_wins(self):
        self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "local")

    def test_environment_is_used_when_there_is_no_django_setting(self):
        with mock.patch.dict(os.environ, {"CHI_AUTH_CHECK_SYSTEMS": "ucad"}):
            self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "ucad")

    @override_settings(CHI_AUTH_CHECK_SYSTEMS="local")
    def test_django_setting_beats_the_environment(self):
        with mock.patch.dict(os.environ, {"CHI_AUTH_CHECK_SYSTEMS": "ucad"}):
            self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "local")

    def test_booleans_from_the_environment(self):
        for raw, expected in [("TRUE", True), ("true", True), ("1", True), ("no", False)]:
            with self.subTest(raw=raw):
                with mock.patch.dict(os.environ, {"CHI_AUTH_AUTOCREATE_LOCAL_USER": raw}):
                    self.assertIs(custom_settings.CHI_AUTH_AUTOCREATE_LOCAL_USER, expected)

    @override_settings(CHI_AUTH_AUTOCREATE_LOCAL_USER=True)
    def test_real_booleans_pass_through(self):
        self.assertIs(custom_settings.CHI_AUTH_AUTOCREATE_LOCAL_USER, True)

    @override_settings(CHI_AUTH_TIMEOUT="2.5")
    def test_timeout_is_cast_to_a_number(self):
        self.assertEqual(custom_settings.CHI_AUTH_TIMEOUT, 2.5)

    @override_settings(CHI_AUTH_TRUSTED_PROXIES="10.0.0.1, 10.0.0.2")
    def test_trusted_proxies_are_split(self):
        self.assertEqual(custom_settings.CHI_AUTH_TRUSTED_PROXIES, ["10.0.0.1", "10.0.0.2"])

    def test_unknown_setting_raises(self):
        with self.assertRaises(AttributeError):
            _ = custom_settings.NOT_A_SETTING


class ContextProcessorTests(SimpleTestCase):
    def test_chi_auth_links_are_shown_when_the_backend_is_installed(self):
        context = settings_context_processor(None)
        self.assertTrue(context["allow_chi_auth_login"])
        self.assertEqual(context["ACCOUNT_LOOKUP_URL"], "https://chi.uc.edu/auth/account_lookup")

    @override_settings(AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend"])
    def test_chi_auth_links_are_hidden_otherwise(self):
        self.assertFalse(settings_context_processor(None)["allow_chi_auth_login"])


class ChecksTests(SimpleTestCase):
    def ids(self, **settings_kwargs):
        with override_settings(**settings_kwargs):
            return {message.id for message in check_chi_auth_middleware(None)}

    def test_no_messages_when_the_sso_middleware_is_not_used(self):
        self.assertEqual(self.ids(MIDDLEWARE=[]), set())

    def test_warns_when_trusted_proxies_is_empty(self):
        self.assertIn("user_manager.W001", self.ids(MIDDLEWARE=SSO_MIDDLEWARE))

    def test_no_warning_once_trusted_proxies_is_set(self):
        ids = self.ids(MIDDLEWARE=SSO_MIDDLEWARE, CHI_AUTH_TRUSTED_PROXIES=["10.0.0.1"])
        self.assertNotIn("user_manager.W001", ids)

    def test_errors_without_authentication_middleware(self):
        ids = self.ids(MIDDLEWARE=["user_manager.middleware.ChiAuthLoginMiddleware"])
        self.assertIn("user_manager.E001", ids)

    def test_errors_when_ordered_before_authentication_middleware(self):
        self.assertIn("user_manager.E002", self.ids(MIDDLEWARE=list(reversed(SSO_MIDDLEWARE))))

    def test_warns_when_migration_modules_has_no_entry(self):
        with override_settings(MIGRATION_MODULES={}):
            ids = {message.id for message in check_migration_modules(None)}
        self.assertIn("user_manager.W003", ids)

    def test_no_migration_warning_once_configured(self):
        for value in ["project.user_manager_migrations", None]:
            with self.subTest(value=value):
                with override_settings(MIGRATION_MODULES={"user_manager": value}):
                    self.assertEqual(check_migration_modules(None), [])

    def test_warns_about_the_header_inspection_log_outside_debug(self):
        ids = self.ids(
            MIDDLEWARE=["user_manager.middleware.InspectHeadersMiddleware"],
            SPECIAL_LOG_FOLDER="/var/log/example/",
            DEBUG=False,
        )
        self.assertIn("user_manager.W002", ids)
