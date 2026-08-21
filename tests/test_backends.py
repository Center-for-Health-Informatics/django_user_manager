from unittest import mock

import requests
from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase, override_settings

from user_manager.authentication_backends import ChiAuthBackend

User = get_user_model()

REMOTE_USER = {
    "username": "ada",
    "email": "ada@example.com",
    "first_name": "Ada",
    "last_name": "Lovelace",
}


def fake_response(payload=None, status_code=200, json_error=False):
    response = mock.Mock(status_code=status_code)
    if json_error:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = payload
    return response


def patch_get(**kwargs):
    return mock.patch("user_manager.authentication_backends.requests.get", **kwargs)


class ChiAuthBackendTests(TestCase):
    def setUp(self):
        self.backend = ChiAuthBackend()

    def test_no_credentials_makes_no_request(self):
        with patch_get() as get:
            self.assertIsNone(self.backend.authenticate(None, username="", password=""))
        get.assert_not_called()

    def test_existing_user_authenticates(self):
        user = User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response({"authenticated": True})):
            self.assertEqual(self.backend.authenticate(None, "ada", "pw"), user)

    def test_wrong_password_is_rejected(self):
        User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response({"authenticated": False})):
            self.assertIsNone(self.backend.authenticate(None, "ada", "pw"))

    def test_inactive_user_is_rejected_without_calling_chi_auth(self):
        """Deactivating an account must lock it out even while the UC credentials work."""
        User.objects.create_user(username="ada", is_active=False)
        with patch_get(return_value=fake_response({"authenticated": True})) as get:
            self.assertIsNone(self.backend.authenticate(None, "ada", "pw"))
        get.assert_not_called()

    @override_settings(CHI_AUTH_AUTOCREATE_LOCAL_USER=False)
    def test_unknown_user_is_rejected_when_autocreate_is_off(self):
        # explicit since 4.0.0, where the default flipped to True — see issue #8
        with patch_get() as get:
            self.assertIsNone(self.backend.authenticate(None, "ada", "pw"))
        get.assert_not_called()

    def test_the_username_is_matched_case_insensitively(self):
        """Issue #3: an exact match would authenticate "Ada" against a case-insensitive
        directory and then provision a second account beside the existing "ada".
        """
        user = User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response({"authenticated": True})):
            self.assertEqual(self.backend.authenticate(None, "Ada", "pw"), user)
        self.assertEqual(User.objects.count(), 1)

    @override_settings(CHI_AUTH_AUTOCREATE_LOCAL_USER=True)
    def test_unknown_user_is_created_when_autocreate_is_on(self):
        payload = {"authenticated": True, "user": REMOTE_USER}
        with patch_get(return_value=fake_response(payload)):
            user = self.backend.authenticate(None, "ada", "pw")

        self.assertIsNotNone(user)
        self.assertEqual(user.email, "ada@example.com")
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Lovelace")
        self.assertFalse(user.has_usable_password())

    @override_settings(CHI_AUTH_AUTOCREATE_LOCAL_USER=True)
    def test_autocreate_tolerates_a_response_with_no_user_details(self):
        with patch_get(return_value=fake_response({"authenticated": True})):
            user = self.backend.authenticate(None, "ada", "pw")
        self.assertEqual(user.username, "ada")

    def test_network_failure_is_a_failed_login_not_an_exception(self):
        User.objects.create_user(username="ada")
        with patch_get(side_effect=requests.Timeout("too slow")):
            with self.assertLogs("user_manager.authentication_backends", "WARNING"):
                self.assertIsNone(self.backend.authenticate(None, "ada", "pw"))

    def test_non_json_response_is_a_failed_login_not_an_exception(self):
        User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response(status_code=502, json_error=True)):
            with self.assertLogs("user_manager.authentication_backends", "WARNING"):
                self.assertIsNone(self.backend.authenticate(None, "ada", "pw"))

    @override_settings(CHI_AUTH_TIMEOUT=1.5, CHI_AUTH_URL="https://auth.test/")
    def test_request_uses_the_configured_timeout_and_url(self):
        User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response({"authenticated": True})) as get:
            self.backend.authenticate(None, "ada", "pw")

        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://auth.test/api/authenticate")
        self.assertEqual(kwargs["timeout"], 1.5)
        self.assertEqual(kwargs["headers"]["x-password"], "pw")

    def test_get_user_rejects_inactive_users(self):
        user = User.objects.create_user(username="ada")
        self.assertEqual(self.backend.get_user(user.pk), user)
        User.objects.filter(pk=user.pk).update(is_active=False)
        self.assertIsNone(self.backend.get_user(user.pk))
        self.assertIsNone(self.backend.get_user(user.pk + 1000))


class AuthenticateIntegrationTests(TestCase):
    """django.contrib.auth.authenticate() walks AUTHENTICATION_BACKENDS, and tags the
    returned user with the backend that succeeded — which is what login() then stores.
    """

    def test_backend_attribute_is_set_by_chi_auth(self):
        User.objects.create_user(username="ada")
        with patch_get(return_value=fake_response({"authenticated": True})):
            user = authenticate(None, username="ada", password="pw")
        self.assertEqual(user.backend, "user_manager.authentication_backends.ChiAuthBackend")

    def test_model_backend_still_wins_for_local_passwords(self):
        User.objects.create_user(username="ada", password="hunter2")
        with patch_get() as get:
            user = authenticate(None, username="ada", password="hunter2")
        self.assertEqual(user.backend, "django.contrib.auth.backends.ModelBackend")
        get.assert_not_called()
