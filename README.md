# user_manager

## About

This is a Django app that integrates well with the [CHI_AUTH](https://github.com/Center-for-Health-Informatics/chi_auth) tool (though it doesn’t require the CHI_AUTH tool to use). There are a few possible configurations:

- normal Django local login
    - not much benefit over normal Django user system
- local login integration with CHI_AUTH
    - allows users to log in with their UC or CHI credentials
- CHI_AUTH login
    - all login is handled by CHI_AUTH and credentials are passed to this application through nginx as HTTP headers

## Using with django_startup

I already have a django_startup project template that’s already configured to integrate this. That is the easiest way to get started.

See the django_startup documentation, examples, as well as my obisidian “workflow_deploy_django_project” for how to configure everything.

## Using with a new django project from scratch

Download the code from GitHub using pip

```shell
pip install git+https://github.com/Center-for-Health-Informatics/django_user_manager.git@v1.2.0#egg=django_user_manager
```

or add to a `requirements.txt` file
```
git+https://github.com/Center-for-Health-Informatics/django_user_manager.git@v1.2.0#egg=django_user_manager
```

Add `user_manager` app to your installed apps

```python
INSTALLED_APPS = [
    ...
    'user_manager',
]
```

Set the user manager model as your User model
```python
AUTH_USER_MODEL = "user_manager.User"
```

Select the authentication backends you want to use
```python
# select auth backends to use when authenticating inside the app for development
# the following will first try local authentication, then try CHI Auth authentication
# checking both CHI Accounts and UC AD Accounts. On successful CHI Auth authentication,
# the local user will be created if they don’t exist yet.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "user_manager.authentication_backends.ChiAuthBackend",
]
```

Define an abstract user
- You need to define an abstract user model on path `project.abstract_user_model.AbstractCustomUser`.
- `user_manager` will use this as the base to create a concrete user model

```python
from django.contrib.auth.models import AbstractUser

class AbstractCustomUser(AbstractUser):
    # add any custom fields or methods you want

    class Meta:       abstract = True
```

Add to urls.py
```python
path('user_manager/', include( ('user_manager.urls', 'user_manager'), namespace='user_manager') ),
```

Customize the behavior of CHI_AUTH. These values can be set in the host project’s `settings.py` or in the process environment.
```python
# if using CHI AUTH, what is the root URL for the system
CHI_AUTH_URL = "https://chi.uc.edu/auth/"

# you need to provide an access token if using CHI_Auth
CHI_AUTH_API_ACCESS_TOKEN = "🤫"

# Which CHI_AUTH systems do you want to use for authentication?
# ucad is UC Active Directory, local is CHI_AUTH credentials for non-UC users
CHI_AUTH_CHECK_SYSTEMS = 'local, ucad'

# if user authenticates through CHI_AUTH but doesn't exist locally, create new user?
CHI_AUTH_AUTOCREATE_LOCAL_USER = True

# new users created locally should automatically generate new user in CHI_AUTH
CHI_AUTH_AUTOCREATE_CHI_AUTH_USER = False
```

Set login/logout paths
- this example is for local login, you could also configure it to use the CHI_AUTH login views
```python
# this url gets called when @login_required view is accessed
LOGIN_URL = '/user_manager/login'

# use as a sign in link <a href="{{ LOGIN_URL_FOR_LINK }}">Sign In</a>
LOGIN_URL_FOR_LINK = '/user_manager/login'

# use as a sign out link <a href="{{ LOGOUT_URL_FOR_LINK }}">Sign Out</a>
LOGOUT_URL_FOR_LINK = '/user_manager/logout'
```

Customize specifics
```python
# what to display for, “Sign in to: _______”
SITE_TITLE = "Center for Health Informatics"

# who to email for help
CONTACT_EMAIL = "combmichi@uc.edu"

# where to change a UC password
UC_PASSWORD_MANAGER_URL = "https://www.uc.edu/sspr"
```

## Dependencies

Depends on resources from [CHI Assets](https://chi.uc.edu/assets/) to display its login form. Specifically:

- [favicon.ico](https://chi.uc.edu/assets/favicon.ico)
- [login.css](https://chi.uc.edu/assets/login.css)
    - [opensans.css](https://chi.uc.edu/assets/fonts/opensans.css)
    - [care_crawley.jpg](https://chi.uc.edu/assets/care_crawley.jpg)


There are no other external dependencies (*e.g.* Bootstrap, jQuery, Font Awesome, *etc.*). Does not depend on particular templates existing in the host project.
