from . import custom_settings


def settings_context_processor(request):
    my_dict = {
        "LOGIN_URL_FOR_LINK": custom_settings.LOGIN_URL_FOR_LINK,
        "LOGOUT_URL_FOR_LINK": custom_settings.LOGOUT_URL_FOR_LINK,
        "CONTACT_EMAIL": custom_settings.CONTACT_EMAIL,
        "SITE_TITLE": custom_settings.SITE_TITLE,
        "ASSETS_URL": custom_settings.ASSETS_URL,
    }

    return my_dict
