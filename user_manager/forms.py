from django import forms
from django.contrib.auth.forms import UsernameField

from .models import User


class CustomUserCreationForm(forms.ModelForm):
    """A form that creates a user, with no privileges and no password, from the given
    username, email and name.

    Users added this way get an unusable password: they are expected to authenticate
    through CHI Auth, or to be given a password afterwards on the change form.
    """

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs.update({"autofocus": True})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user
