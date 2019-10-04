from django.conf import settings

def settings_context_processor(request):
    my_dict = {
        'LOGIN_URL_FOR_LINK': getattr(settings, 'LOGIN_URL_FOR_LINK', '#'),
        'LOGOUT_URL_FOR_LINK': getattr(settings, 'LOGOUT_URL_FOR_LINK', '#'),
    }

    return my_dict