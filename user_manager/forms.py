import unicodedata

from django import forms
from django.contrib.auth import get_user_model


from django.contrib.auth.models import User

UserModel = get_user_model()


class UsernameField(forms.CharField):
    def to_python(self, value):
        return unicodedata.normalize("NFKC", super().to_python(value))


class CustomUserCreationForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password.
    """

    class Meta:
        model = User
        fields = ("username",)
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs.update({"autofocus": True})
