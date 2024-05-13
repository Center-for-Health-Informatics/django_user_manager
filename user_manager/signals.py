from django.dispatch import receiver
from django.db import models
from django.contrib.auth import get_user_model
from . import custom_settings as settings

import requests


@receiver(models.signals.post_save, sender=get_user_model())
def save_status_history_after_task_save(sender, instance, created, **kwargs):
    """Upload new or modified local user to CHI Auth
    (CHI Auth will create a new user if username and email are unique. Otherwise, it will
    ignore the request. )
    """

    # !important, this script should never be run if not on the UC network; will cause timeout
    if not settings.CHI_AUTH_AUTOCREATE_CHI_AUTH_USER:
        return

    headers = {"x-access-token": settings.CHI_AUTH_API_ACCESS_TOKEN}
    data = {
        "username": instance.username,
        "email": instance.email,
        "first_name": instance.first_name,
        "last_name": instance.last_name,
    }
    r = requests.post(
        settings.CHI_AUTH_URL + "api/create_user", headers=headers, data=data
    )
    print(r.text)
