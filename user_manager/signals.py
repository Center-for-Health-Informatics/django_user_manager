import logging

import requests
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.dispatch import receiver

from . import custom_settings as settings

logger = logging.getLogger(__name__)


@receiver(models.signals.post_save, sender=get_user_model())
def create_chi_auth_user_on_local_user_create(sender, instance, created, **kwargs):
    """Upload a newly created local user to CHI Auth.

    (CHI Auth will create a new user if username and email are unique. Otherwise, it will
    ignore the request.)

    Only fires on creation — every login writes last_login, and we don’t want an outbound
    request on each one. The upload is deferred until the surrounding transaction commits,
    so a rolled back local user is never created remotely.
    """

    # !important, this script should never be run if not on the UC network; will cause timeout
    if not created or not settings.CHI_AUTH_AUTOCREATE_CHI_AUTH_USER:
        return

    data = {
        "username": instance.username,
        "email": instance.email,
        "first_name": instance.first_name,
        "last_name": instance.last_name,
    }
    transaction.on_commit(lambda: upload_user_to_chi_auth(data))


def upload_user_to_chi_auth(data):
    headers = {"x-access-token": settings.CHI_AUTH_API_ACCESS_TOKEN}
    try:
        requests.post(
            settings.CHI_AUTH_URL + "api/create_user",
            headers=headers,
            data=data,
            timeout=settings.CHI_AUTH_TIMEOUT,
        )
    except requests.RequestException:
        # the local user already exists; failing to mirror them shouldn’t break the request
        logger.exception("Failed to create user %r in CHI Auth", data["username"])
