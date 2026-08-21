import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from user_manager import custom_settings
from user_manager.checks import (
    check_chi_auth_middleware,
    check_migration_modules,
    check_username_case_collisions,
)
from user_manager.context_processors import settings_context_processor

User = get_user_model()

SSO_MIDDLEWARE = [
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "user_manager.middleware.ChiAuthLoginMiddleware",
]


class GetSettingTests(SimpleTestCase):
    def test_default_is_used_when_nothing_is_configured(self):
        # "ucad, local" since 4.0.0 — the order all four deployed consumers set, and it
        # decides which directory authenticates a password, not just which is asked first
        self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "ucad, local")

    @override_settings(CHI_AUTH_CHECK_SYSTEMS="local")
    def test_django_setting_wins(self):
        self.assertEqual(custom_settings.CHI_AUTH_CHECK_SYSTEMS, "local")

    def test_the_environment_is_not_a_configuration_surface(self):
        """settings.py is the only place a setting comes from, as of 4.0.0 (issue #17).

        The env fallback let a variable take effect in a deployment while appearing in no
        settings.py and no example.settings.env — CHI_AUTH_TIMEOUT governed sign-in
        latency for three services through a surface no repository documented.
        """
        for name, raw in [
            ("CHI_AUTH_CHECK_SYSTEMS", "ucad"),
            ("CHI_AUTH_TIMEOUT", "30"),
            ("USER_MANAGER_ABSTRACT_USER_MODEL", "somewhere.else.Model"),
        ]:
            with self.subTest(name=name):
                # compared against the resolved value rather than DEFAULTS, since the test
                # project sets USER_MANAGER_ABSTRACT_USER_MODEL in its own settings
                before = getattr(custom_settings, name)
                with mock.patch.dict(os.environ, {name: raw}):
                    self.assertEqual(getattr(custom_settings, name), before)

    def test_booleans_from_a_string_setting_are_parsed_strictly(self):
        """Matching the env_bool helper in every consumer's settings.py: only 'true'.

        '1' reading as False would be worse than '1' being rejected, because the first
        kind is only noticed in production — and these booleans decide whether accounts
        get provisioned.
        """
        for raw in ["TRUE", "true", " True "]:
            with self.subTest(raw=raw):
                with override_settings(CHI_AUTH_USE_MIDDLEWARE=raw):
                    self.assertIs(custom_settings.CHI_AUTH_USE_MIDDLEWARE, True)
        for raw in ["1", "yes", "on", "no", ""]:
            with self.subTest(raw=raw):
                with override_settings(CHI_AUTH_USE_MIDDLEWARE=raw):
                    self.assertIs(custom_settings.CHI_AUTH_USE_MIDDLEWARE, False)

    @override_settings(CHI_AUTH_AUTOCREATE_LOCAL_USER=False)
    def test_real_booleans_pass_through(self):
        self.assertIs(custom_settings.CHI_AUTH_AUTOCREATE_LOCAL_USER, False)

    def test_autocreate_defaults_on(self):
        """4.0.0 flipped it False -> True, because the middleware provisioned
        unconditionally before and header SSO is how everyone arrives. A False default
        would have turned that into 'provisions no one', silently, on the pin bump.
        """
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
        # relative, because CHI_AUTH_URL is: the link has to stay on the host the user
        # is already signed in to
        self.assertEqual(context["ACCOUNT_LOOKUP_URL"], "/auth/account_lookup")

    @override_settings(CHI_AUTH_URL="https://chi.uc.edu/auth/")
    def test_account_lookup_url_still_honours_an_absolute_setting(self):
        context = settings_context_processor(None)
        self.assertEqual(context["ACCOUNT_LOOKUP_URL"], "https://chi.uc.edu/auth/account_lookup")

    def test_assets_url_is_exposed_to_the_sign_in_template(self):
        self.assertEqual(
            settings_context_processor(None)["ASSETS_URL"], "https://chi.uc.edu/assets/"
        )

    @override_settings(ASSETS_URL="/assets/")
    def test_assets_url_can_be_overridden(self):
        self.assertEqual(settings_context_processor(None)["ASSETS_URL"], "/assets/")

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
        ids = self.ids(MIDDLEWARE=SSO_MIDDLEWARE, CHI_AUTH_TRUSTED_PROXIES=["127.0.0.1/32"])
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

    def test_warns_when_use_middleware_is_on_but_the_middleware_is_missing(self):
        self.assertIn("user_manager.W004", self.ids(MIDDLEWARE=[], CHI_AUTH_USE_MIDDLEWARE=True))

    def test_warns_when_the_middleware_is_installed_but_use_middleware_is_off(self):
        self.assertIn("user_manager.W005", self.ids(MIDDLEWARE=SSO_MIDDLEWARE))

    def test_no_disagreement_warning_when_both_agree(self):
        ids = self.ids(MIDDLEWARE=SSO_MIDDLEWARE, CHI_AUTH_USE_MIDDLEWARE=True)
        self.assertFalse({"user_manager.W004", "user_manager.W005"} & ids)

    def test_warns_when_logout_redirect_url_still_names_chi_auth(self):
        ids = self.ids(
            MIDDLEWARE=SSO_MIDDLEWARE,
            CHI_AUTH_USE_MIDDLEWARE=True,
            CHI_AUTH_URL="https://chi-tools.uc.edu/auth/",
            LOGOUT_REDIRECT_URL="/auth/logout?uri=/my_app/",
        )
        self.assertIn("user_manager.W006", ids)

    def test_no_logout_redirect_warning_for_a_local_destination(self):
        ids = self.ids(
            MIDDLEWARE=SSO_MIDDLEWARE,
            CHI_AUTH_USE_MIDDLEWARE=True,
            CHI_AUTH_URL="https://chi-tools.uc.edu/auth/",
            LOGOUT_REDIRECT_URL="/my_app/",
        )
        self.assertNotIn("user_manager.W006", ids)

    def test_warns_when_chi_auth_url_names_a_host(self):
        self.assertIn("user_manager.W007", self.ids(CHI_AUTH_URL="https://chi.uc.edu/auth/"))

    def test_no_warning_for_a_relative_chi_auth_url(self):
        self.assertNotIn("user_manager.W007", self.ids(CHI_AUTH_URL="/auth/"))

    def test_no_warning_for_the_default_chi_auth_url(self):
        self.assertNotIn("user_manager.W007", self.ids())

    def test_warns_about_the_header_inspection_log_outside_debug(self):
        ids = self.ids(
            MIDDLEWARE=["user_manager.middleware.InspectHeadersMiddleware"],
            SPECIAL_LOG_FOLDER="/var/log/example/",
            DEBUG=False,
        )
        self.assertIn("user_manager.W002", ids)


class UsernameCaseCollisionCheckTests(TestCase):
    """W008. Needs the database, so it is a TestCase rather than a SimpleTestCase."""

    def test_silent_when_every_username_is_distinct(self):
        User.objects.create_user(username="ada")
        User.objects.create_user(username="grace")
        self.assertEqual(check_username_case_collisions(None), [])

    def test_reports_a_pair_differing_only_in_case(self):
        User.objects.create_user(username="ada")
        User.objects.create_user(username="Ada")
        messages = check_username_case_collisions(None)
        self.assertEqual([m.id for m in messages], ["user_manager.W008"])
        self.assertIn("'ada'", messages[0].msg)

    def test_the_listing_is_capped(self):
        for n in range(12):
            User.objects.create_user(username=f"user{n}")
            User.objects.create_user(username=f"USER{n}")
        message = check_username_case_collisions(None)[0]
        self.assertIn("12 username(s)", message.msg)
        self.assertIn("and 2 more", message.msg)
