import os

from user_manager.custom_settings import DEFAULTS

# user_manager reads its settings from the process environment when there is no Django
# setting, so a developer's ambient CHI_AUTH_* exports would otherwise change test results.
for _name in DEFAULTS:
    os.environ.pop(_name, None)

SECRET_KEY = "not-a-secret-only-used-by-the-test-suite"  # noqa: S105
DEBUG = False
ALLOWED_HOSTS = ["testserver", "example.com"]

USER_MANAGER_ABSTRACT_USER_MODEL = "tests.abstract_user_model.AbstractCustomUser"
AUTH_USER_MODEL = "user_manager.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "user_manager",
]

# user_manager ships no migrations on purpose (see the Migrations section of the README);
# None tells Django to create its tables straight from the models.
MIGRATION_MODULES = {"user_manager": None}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "user_manager.authentication_backends.ChiAuthBackend",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "user_manager.context_processors.settings_context_processor",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/goodbye/"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

USE_TZ = True
