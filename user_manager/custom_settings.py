from django.conf import settings
from os import getenv


# Don’t edit this directly, each setting can be overridden using the Django settings or
# process environment.
# This file makes a useful reference for all chi_auth settings and their default values.


def get_setting(setting_name, alt):
    if hasattr(settings, setting_name):
        return getattr(settings, setting_name)

    if (
        setting_name == "CHI_AUTH_AUTOCREATE_LOCAL_USER"
        or setting_name == "CHI_AUTH_AUTOCREATE_CHI_AUTH_USER"
    ):
        return getenv(setting_name, str(alt)).upper() == "TRUE"

    return getenv(setting_name, alt)


LOGIN_URL_FOR_LINK = get_setting("LOGIN_URL_FOR_LINK", "/user_manager/login")
LOGOUT_URL_FOR_LINK = get_setting("LOGOUT_URL_FOR_LINK", "/user_manager/logout")

# if using CHI AUTH, what is the root URL for the system
CHI_AUTH_URL = get_setting("CHI_AUTH_URL", "https://chi.uc.edu/auth/")

# you need to provide an access token if using CHI_Auth
CHI_AUTH_API_ACCESS_TOKEN = get_setting("CHI_AUTH_API_ACCESS_TOKEN", "")

# if false, a user can only login to the system if they already have a local user account
# if true, a local account will be auto-created for any user who successfully authenticates
CHI_AUTH_AUTOCREATE_LOCAL_USER = get_setting("CHI_AUTH_AUTOCREATE_LOCAL_USER", False)

# what credentials should be accepted from CHI Auth? (comma separated string)
# local: user account in CHI Auth
# ucad: user account in UC Active Directory (only works if server is on UC network)
CHI_AUTH_CHECK_SYSTEMS = get_setting("CHI_AUTH_CHECK_SYSTEMS", "local, ucad")

# if true, locally created users will automatically get accounts in chi-auth
CHI_AUTH_AUTOCREATE_CHI_AUTH_USER = get_setting(
    "CHI_AUTH_AUTOCREATE_CHI_AUTH_USER", False
)

SITE_TITLE = get_setting("SITE_TITLE", "Center for Health Informatics")
CONTACT_EMAIL = get_setting("CONTACT_EMAIL", "combmichi@uc.edu")
UC_PASSWORD_MANAGER_URL = get_setting(
    "UC_PASSWORD_MANAGER_URL", "https://www.uc.edu/sspr"
)
