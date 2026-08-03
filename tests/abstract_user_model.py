"""Stands in for the abstract user model a host project supplies."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class AbstractCustomUser(AbstractUser):
    # a custom field, to prove the host project's additions really do land on the model
    department = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True
