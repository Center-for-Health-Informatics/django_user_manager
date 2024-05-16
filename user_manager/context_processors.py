from . import custom_settings
from django.conf import settings


def settings_context_processor(request):
    # determine if CHI Auth is being used
    if (
        "user_manager.authentication_backends.ChiAuthBackend"
        in settings.AUTHENTICATION_BACKENDS
    ):
        allow_chi_auth_login = True
    else:
        allow_chi_auth_login = False

    my_dict = {
        "LOGIN_URL_FOR_LINK": custom_settings.LOGIN_URL_FOR_LINK,
        "LOGOUT_URL_FOR_LINK": custom_settings.LOGOUT_URL_FOR_LINK,
        "UC_PASSWORD_MANAGER_LINK": custom_settings.UC_PASSWORD_MANAGER_LINK,
        "ACCOUNT_LOOKUP_URL": "{}account_lookup".format(custom_settings.CHI_AUTH_URL),
        "CONTACT_EMAIL_ADDRESS": custom_settings.CONTACT_EMAIL_ADDRESS,
        "SITE_TITLE": custom_settings.SITE_TITLE,
        "allow_chi_auth_login": allow_chi_auth_login,
    }

    return my_dict
