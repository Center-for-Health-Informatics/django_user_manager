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
