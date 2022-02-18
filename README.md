# Django User Manager

A Django app named `user_manager` that helps with integrating Django Users and authentication into the CHI_AUTH tool.

- `user_manager` implements its own user table. Your life will be much easier if you put it in your project from the start, as moving the user table later without erasing the database is difficult.

## Install the App

Download the code from GitHub using pip

```
pip install git+https://github.com/Center-for-Health-Informatics/django_user_manager.git#egg=django_user_manager
```

### 1. Edit your Django settings.py

Add `user_manager` app to your installed apps

```
INSTALLED_APPS = [
	...
	'user_manager',
]
```

Set the user manager model as your User model

```
AUTH_USER_MODEL = "user_manager.User"
```

Select the authentication backends you want to use

```
# select auth backends to use when authenticating inside the app for development
# the following will first try local authentication, then try CHI Auth authentication
# checking both CHI Accounts and UC AD Accounts. On successful CHI Auth authentication,
# the local user will be created if they don't exist yet.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'user_manager.authentication_backends.ChiAuthBackend',
]
```

Customize the behavior of CHI_AUTH

```
# Which CHI_AUTH systems do you want to use for authentication?
# ucad is UC Active Directory, local is CHI_AUTH credentials for non-UC users
CHI_AUTH_CHECK_SYSTEMS = 'local, ucad'

# if user authenticates through CHI_AUTH but doesn't exist locally, create new user? 
CHI_AUTH_AUTOCREATE_LOCAL_USER = True

# new users created locally should automatically generate new user in CHI_AUTH
CHI_AUTH_AUTOCREATE_CHI_AUTH_USER = False
```

Set login/logout paths

```
# this url gets called when @login_required view is accessed
LOGIN_URL = '/user_manager/login'    

# use as a sign in link <a href="{{ LOGIN_URL_FOR_LINK }}">Sign In</a>
LOGIN_URL_FOR_LINK = '/user_manager/login'    

# use as a sign out link <a href="{{ LOGOUT_URL_FOR_LINK }}">Sign Out</a>
LOGOUT_URL_FOR_LINK = '/user_manager/logout'        
```



### 2. Add to urls.py

```    
path('user_manager/', include( ('user_manager.urls', 'user_manager'), namespace='user_manager') ),
```

 

### 3. Define an abstract user 

You need to define an abstract user model on path `project.abstract_user_model.AbstractCustomUser`.

- `user_manager` will use this as the base to create a concrete user model

```
from django.contrib.auth.models import AbstractUser

class AbstractCustomUser(AbstractUser):
    # add any custom fields or methods you want
    
    class Meta:
    	abstract = True
```

## Configuration 1 - Local Login

- people log in directly to your website
- the server makes API calls to CHI_AUTH to authenticate users


## Configuration 2 - Single Sign On

- people log in and log out using the CHI_AUTH login forms

- can be used on urls `chi.uc.edu`, `chi-tools.uc.edu`, `chi-test.uc.edu`, `chi-dev.uc.edu`
- CHI_AUTH is integrated with nginx for these urls
- All HTTP requests go through CHI_AUTH
- You configure this site as a resource in CHI_AUTH that requires login
- Once logged in, all HTTP requests will have headers that give user info
