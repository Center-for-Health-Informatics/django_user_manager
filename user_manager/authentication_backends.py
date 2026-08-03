import logging

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from . import custom_settings as settings

logger = logging.getLogger(__name__)


class ChiAuthBackend(BaseBackend):
    """
    Authenticates against UC’s AD using the CHI Auth API.

    1. If user does not exist here already, they will not be created
       (unless CHI_AUTH_AUTOCREATE_LOCAL_USER is on).
    2. The api/authenticate call is just a proxy for UC’s LDAP system.
       It only cares if the username/PW matches in LDAP, not how that user is
       defined locally on the SSO site.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        UserModel = get_user_model()
        oUser = UserModel.objects.filter(username=username).first()

        # if no user and we’re not autocreating users, can quit here
        if oUser is None and not settings.CHI_AUTH_AUTOCREATE_LOCAL_USER:
            return None
        # a deactivated account stays locked out even when the remote credentials still work
        if oUser is not None and not self.user_can_authenticate(oUser):
            return None

        response = self._call_api(username, password)
        if not response or not response.get("authenticated"):
            return None

        # if user exists locally and they authenticated, we’re good
        if oUser:
            return oUser

        # if we’re autocreating and we authenticated a user that doesn’t exist, create them
        remote_user = response.get("user") or {}
        return UserModel.objects.create_user(
            username=remote_user.get("username", username),
            email=remote_user.get("email", ""),
            first_name=remote_user.get("first_name", ""),
            last_name=remote_user.get("last_name", ""),
        )

    def _call_api(self, username, password):
        """Ask CHI Auth whether these credentials are valid. Returns the decoded response,
        or None if CHI Auth could not be reached or answered with something unusable —
        either way the caller treats it as a failed login rather than raising.
        """
        payload = {
            "username": username,
            "systems": settings.CHI_AUTH_CHECK_SYSTEMS,
        }
        headers = {
            "x-password": password,
            "x-access-token": settings.CHI_AUTH_API_ACCESS_TOKEN,
        }
        try:
            r = requests.get(
                settings.CHI_AUTH_URL + "api/authenticate",
                params=payload,
                headers=headers,
                timeout=settings.CHI_AUTH_TIMEOUT,
            )
        except requests.RequestException:
            logger.warning("CHI Auth could not be reached", exc_info=True)
            return None

        try:
            return r.json()
        except ValueError:
            logger.warning("CHI Auth returned a non-JSON response (HTTP %s)", r.status_code)
            return None

    # this is just a copy of the default
    # get_user method from django.contrib.auth.backends.ModelBackend
    # (BaseBackend.get_user is only a stub that returns None)
    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None

    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don’t have
        that attribute are allowed.
        """
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None
