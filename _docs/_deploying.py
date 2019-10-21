
# user_manager implements its own user table. Your life will be much easier if you put it in your project from
# the start, as moving the user table later without erasing the database is difficult.

# git clone user_manager, put it on your python path
# ex. you can have a sibling directory called external_apps, and include it in your project from settings

import sys
from test.test_decimal import file
sys.path.append("../external_apps")

# you need to define an abstract user model in project.abstract_user_model.AbstractCustomUser
# user_manager will use this as the base to create a concrete user model

#--- project/abstract_user_model.py ----------------------------------------

from django.contrib.auth.models import AbstractUser


class AbstractCustomUser(AbstractUser):
    # add any custom fields or methods you want
    
    class Meta:
        abstract = True
        
#--------------------------------------------------------------------------

# you need to add user_manager to your urls.py

path('user_manager/', include( ('user_manager.urls', 'user_manager'), namespace='user_manager') ),

### settings for development environment #####################################

INSTALLED_APPS = [
    # ...
    'user_manager',
    # ...
]

AUTH_USER_MODEL = "user_manager.User"

# select auth backends to use when authenticating inside the app for development
# the following will first try local authentication, then try CHI Auth authentication
# checking both CHI Accounts and UC AD Accounts. On successful CHI Auth authentication,
# the local user will be created if they don't exist yet.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'user_manager.authentication_backends.ChiAuthBackend',
]

CHI_AUTH_AUTOCREATE_LOCAL_USER = True
CHI_AUTH_CHECK_SYSTEMS = 'local, ucad'

# You need some more stuff to connect to CHI_AUTH:
CHI_AUTH_API_ACCESS_TOKEN = '...'
CHI_AUTH_URL = 'https://chi-dev.uc.edu/auth/'
CHI_AUTH_AUTOCREATE_CHI_AUTH_USER = False            # when local user is created, signal is used to create the user in CHI_AUTH as well

# set urls for login and logout
LOGIN_URL = '/user_manager/login'                   # this url gets called when @login_required view is accessed
LOGIN_URL_FOR_LINK = '/user_manager/login'          # use as a sign in link <a href="{{ LOGIN_URL_FOR_LINK }}">Sign In</a>
LOGOUT_URL_FOR_LINK = '/user_manager/logout'        # use as a sign out link <a href="{{ LOGOUT_URL_FOR_LINK }}">Sign Out</a>

### OVERRIDE SETTINGS FOR PRODUCTION ###################################

# login and logout need to point to CHI Auth instead of local
LOGIN_URL = '/auth/login?host=chi-test.uc.edu'
LOGIN_URL_FOR_LINK = '/auth/login?host=chi-test.uc.edu&uri=/research/'
LOGOUT_URL_FOR_LINK = '/auth/logout?host=chi-test.uc.edu&uri=/research/'

# authentication is done using HTTP headers instead of locally
MIDDLEWARE = [
     # ...
     # 'django.contrib.auth.middleware.AuthenticationMiddleware',
     'user_manager.middleware.ChiAuthLoginMiddleware',
     # ...
]


### SETTING UP LOGIN AND LOGOUT LINKS ################################

# you already defined these links in your settings file
# you can make these links available in your template by adding user manager context processor

TEMPLATES = [
    {
        #...
        'OPTIONS': {
            'context_processors': [
                #...
                'user_manager.context_processors.settings_context_processor',
            ],
        },
    },
]

# Then use the links like this:

<a class="nav-link" href="{{ LOGIN_URL_FOR_LINK }}">Sign in</a>
<a class="dropdown-item" href="{{ LOGOUT_URL_FOR_LINK }}">Logout</a>


















