from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from user_manager.forms import CustomUserCreationForm

User = get_user_model()


class CustomUserCreationFormTests(TestCase):
    def test_form_is_bound_to_the_swapped_user_model(self):
        """It used to be bound to django.contrib.auth.models.User — the model this app
        replaces — which has no table when AUTH_USER_MODEL is swapped."""
        self.assertIs(CustomUserCreationForm._meta.model, User)

    def test_saves_a_user_with_an_unusable_password(self):
        form = CustomUserCreationForm(
            {
                "username": "ada",
                "email": "ada@example.com",
                "first_name": "Ada",
                "last_name": "Lovelace",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.pk, User.objects.get(username="ada").pk)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.check_password(""))

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="ada")
        form = CustomUserCreationForm({"username": "ada"})
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_username_is_nfkc_normalised(self):
        # the fullwidth 'ａ' normalises to plain 'a'
        form = CustomUserCreationForm({"username": "ａda"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "ada")


class AdminAddUserTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="root", password="hunter2")
        self.client.force_login(self.admin)

    def test_add_user_page_renders(self):
        response = self.client.get(reverse("admin:user_manager_user_add"))
        self.assertEqual(response.status_code, 200)

    def test_add_user_creates_the_user(self):
        response = self.client.post(
            reverse("admin:user_manager_user_add"),
            {
                "username": "ada",
                "email": "ada@example.com",
                "first_name": "Ada",
                "last_name": "Lovelace",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="ada")
        self.assertEqual(user.email, "ada@example.com")
        self.assertFalse(user.has_usable_password())
