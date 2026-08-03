from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()


def patch_post(**kwargs):
    return mock.patch("user_manager.signals.requests.post", **kwargs)


class ChiAuthUserUploadTests(TestCase):
    def test_nothing_is_uploaded_when_the_setting_is_off(self):
        with patch_post() as post:
            User.objects.create_user(username="ada")
        post.assert_not_called()

    @override_settings(CHI_AUTH_AUTOCREATE_CHI_AUTH_USER=True, CHI_AUTH_URL="https://auth.test/")
    def test_new_user_is_uploaded_once(self):
        with patch_post() as post:
            with self.captureOnCommitCallbacks(execute=True):
                User.objects.create_user(username="ada", email="ada@example.com", first_name="Ada")

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://auth.test/api/create_user")
        self.assertEqual(kwargs["data"]["username"], "ada")
        self.assertEqual(kwargs["data"]["email"], "ada@example.com")
        self.assertEqual(kwargs["timeout"], 5)

    @override_settings(CHI_AUTH_AUTOCREATE_CHI_AUTH_USER=True)
    def test_updates_are_not_uploaded(self):
        """Every login writes last_login; that must not trigger an outbound request."""
        user = User.objects.create_user(username="ada")
        with patch_post() as post:
            with self.captureOnCommitCallbacks(execute=True):
                user.first_name = "Ada"
                user.save()
        post.assert_not_called()

    @override_settings(CHI_AUTH_AUTOCREATE_CHI_AUTH_USER=True)
    def test_upload_is_deferred_until_commit(self):
        with patch_post() as post:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                User.objects.create_user(username="ada")
            post.assert_not_called()
        self.assertEqual(len(callbacks), 1)

    @override_settings(CHI_AUTH_AUTOCREATE_CHI_AUTH_USER=True)
    def test_chi_auth_being_down_does_not_break_user_creation(self):
        with patch_post(side_effect=requests.ConnectionError("no route")):
            with self.assertLogs("user_manager.signals", "ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    User.objects.create_user(username="ada")

        self.assertTrue(User.objects.filter(username="ada").exists())
