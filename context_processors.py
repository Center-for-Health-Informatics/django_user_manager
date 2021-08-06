from . import custom_settings
from django.conf import settings

def settings_context_processor(request):
    # determine if CHI Auth is being used
    if 'user_manager.authentication_backends.ChiAuthBackend' in settings.AUTHENTICATION_BACKENDS:
        allow_chi_auth_login = True
    else:
        allow_chi_auth_login = False


    my_dict = {
        'LOGIN_URL_FOR_LINK': custom_settings.LOGIN_URL_FOR_LINK,
        'LOGOUT_URL_FOR_LINK': custom_settings.LOGOUT_URL_FOR_LINK,
        'allow_chi_auth_login': allow_chi_auth_login
    }

    return my_dict