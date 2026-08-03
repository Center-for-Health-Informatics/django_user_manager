from django.conf import settings

from . import custom_settings


def settings_context_processor(request):
    # determine if CHI Auth is being used
    allow_chi_auth_login = "user_manager.authentication_backends.ChiAuthBackend" in getattr(
        settings, "AUTHENTICATION_BACKENDS", []
    )

    my_dict = {
        "LOGIN_URL_FOR_LINK": custom_settings.LOGIN_URL_FOR_LINK,
        "LOGOUT_URL_FOR_LINK": custom_settings.LOGOUT_URL_FOR_LINK,
        "UC_PASSWORD_MANAGER_URL": custom_settings.UC_PASSWORD_MANAGER_URL,
        "ACCOUNT_LOOKUP_URL": f"{custom_settings.CHI_AUTH_URL}account_lookup",
        "CONTACT_EMAIL": custom_settings.CONTACT_EMAIL,
        "SITE_TITLE": custom_settings.SITE_TITLE,
        "allow_chi_auth_login": allow_chi_auth_login,
    }

    return my_dict
