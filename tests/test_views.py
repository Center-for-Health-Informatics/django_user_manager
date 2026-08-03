from django.contrib.auth import get_user_model
from django.test import TestCase

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
