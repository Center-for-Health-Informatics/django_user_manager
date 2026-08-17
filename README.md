# user_manager

## About

This is a Django app that integrates well with the [CHI_AUTH](https://github.com/Center-for-Health-Informatics/chi_auth) tool (though it doesn’t require the CHI_AUTH tool to use). There are a few possible configurations:

- normal Django local login
    - not much benefit over normal Django user system
- local login integration with CHI_AUTH
    - allows users to log in with their UC or CHI credentials
- CHI_AUTH login
    - all login is handled by CHI_AUTH and credentials are passed to this application through nginx as HTTP headers

Supports Django 5.2 and 6.0 on Python 3.10+.

Projects using it: daedalus, ocr_importer, monitor, neurords, rap_subsystem, fcc_tracker,
email_service, covidicus. Daedalus is the most recently updated and is the best worked
example to copy from.

## Setup

Install from GitHub with pip

```shell
pip install "user_manager @ git+https://github.com/Center-for-Health-Informatics/django_user_manager.git@v3.0.0"
```

or add to a `requirements.txt` file
```
user_manager @ git+https://github.com/Center-for-Health-Informatics/django_user_manager.git@v3.0.0
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
- `user_manager` uses this as the base to build its concrete `User` model, so this is where you add any custom fields or methods.
- By default it is looked for at `project.abstract_user_model.AbstractCustomUser`. Set `USER_MANAGER_ABSTRACT_USER_MODEL` if you want it somewhere else.

```python
from django.contrib.auth.models import AbstractUser

class AbstractCustomUser(AbstractUser):
    # add any custom fields or methods you want

    class Meta:
        abstract = True
```

Register the context processor, so the login page can see `SITE_TITLE`, `CONTACT_EMAIL` and the CHI Auth help links. Without this the login page still renders, but with those values blank.

```python
TEMPLATES = [
    {
        ...
        "OPTIONS": {
            "context_processors": [
                ...
                "user_manager.context_processors.settings_context_processor",
            ],
        },
    },
]
```

Add to urls.py
```python
path('user_manager/', include('user_manager.urls')),
```

Customize the behavior of CHI_AUTH. These values can be set in the host project’s `settings.py` or in the process environment (the Django setting wins).
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

# seconds to wait on any call out to CHI Auth before giving up and failing the login
CHI_AUTH_TIMEOUT = 5
```

Set login/logout paths. These are the same in both modes — under header SSO the login view
redirects to CHI Auth rather than rendering its own form, so nothing here has to change and
nothing has to hard-code CHI Auth’s URL. See “Header based SSO” below.

```python
# this url gets called when @login_required view is accessed
LOGIN_URL = '/user_manager/login'

# use as a sign in link <a href="{{ LOGIN_URL_FOR_LINK }}">Sign In</a>
LOGIN_URL_FOR_LINK = '/user_manager/login'

# post here to sign out — see “Signing out” below
LOGOUT_URL_FOR_LINK = '/user_manager/logout'
```

Prefix all three with your `FORCE_SCRIPT_NAME` if the app is served under a sub-path.

Customize specifics
```python
# what to display for, “Sign in to: _______”
SITE_TITLE = "Center for Health Informatics"

# who to email for help
CONTACT_EMAIL = "combmichi@uc.edu"

# where to change a UC password
UC_PASSWORD_MANAGER_URL = "https://www.uc.edu/sspr"
```

## Migrations

`user_manager` ships **no migrations**, because the shape of its `User` model is decided by
the abstract base class your project supplies — including any project-specific fields and
foreign keys — so the migration can’t live in this shared package.

**Every project must set `MIGRATION_MODULES`**, pointing at a package in its own repo:

```python
MIGRATION_MODULES = {
    "user_manager": "project.user_manager_migrations",
}
```

Create that package (a directory containing an empty `__init__.py`), then run
`makemigrations user_manager` as normal. The migrations land in your repo and are versioned
with the rest of your project.

Without this, `user_manager` is an *unmigrated* app: it is silently skipped by
`makemigrations` autodetection, and its tables only get created by `migrate --run-syncdb`,
never by a plain `migrate`. Running `makemigrations user_manager` in that state writes the
files into `site-packages`, where they are lost the next time the virtualenv is rebuilt.

> If your abstract user model has a `ForeignKey` to one of your own apps, the auto-generated
> initial migration may deadlock: your app’s initial migration has a
> `swappable_dependency(AUTH_USER_MODEL)` on `user_manager`, so `user_manager` cannot depend
> on it in turn. Split the FK into a second migration that runs after the target model
> exists. (Daedalus’ `project/user_manager_migrations/` is a worked example.)

## Signing out

`logout` accepts **POST only**. A GET logout can be triggered by any page that links to it and
by link prefetchers, which is why Django dropped GET support from its own `LogoutView` in 5.0.
Use a form rather than a link:

```html
<form action="{{ LOGOUT_URL_FOR_LINK }}" method="post">
  {% csrf_token %}
  <button type="submit">Sign Out</button>
</form>
```

## Header based SSO (CHI_AUTH login)

In this mode nginx authenticates the user against CHI Auth and passes their identity to the
application as `SSO-*` request headers. Add the middleware **after** Django’s
`AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "user_manager.middleware.ChiAuthLoginMiddleware",
    ...
]

# tells the login view it is in this mode; MIDDLEWARE alone is not visible to it
CHI_AUTH_USE_MIDDLEWARE = True
```

`manage.py check` warns if those two disagree — `user_manager.W004` when the setting is on
without the middleware, `user_manager.W005` when the middleware is installed without the
setting.

### Signing in under header SSO

`login_view` cannot sign anyone in in this mode. The middleware only ever *derives* a local
session from the `SSO-*` headers, and only CHI Auth can mint the upstream session those
headers describe — so with `CHI_AUTH_USE_MIDDLEWARE = True` the view redirects to
`CHI_AUTH_URL + "login"`, carrying wherever the user was heading as CHI Auth’s `uri`
parameter. Rendering the local form instead would collect an AD password the application
has no reason to see, and produce a local session with no upstream session behind it.

So `LOGIN_URL` and `LOGIN_URL_FOR_LINK` stay pointed at `/user_manager/login` in both modes,
and `@login_required` keeps its destination across the round trip — CHI Auth reads `uri`, not
Django’s `next`, and this is what translates between them.

### Signing out under header SSO

Signing out crosses the same two sessions in the opposite order, and that asymmetry is
deliberate: `logout_view` clears the local session **first** — POST, same-origin, CSRF
intact, none of which a cross-app POST to CHI Auth’s GET-only logout could manage — and
then chains on to `CHI_AUTH_URL + "logout"` to drop the upstream session. Without that
second hop the `SSO-*` headers sign the user straight back in on their next request, which
looks like a broken sign-out button rather than a misconfiguration.

The chaining is automatic as of 3.1.0, so `LOGOUT_REDIRECT_URL` means the same thing in
both modes — where the user should land **on this site** once signed out — and gets handed
to CHI Auth as its `uri`:

```python
LOGOUT_REDIRECT_URL = "/my_app/"
```

Leaving it unset works too, as of 3.1.1: `LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL`
both fall back to `FORCE_SCRIPT_NAME`, so an app served under a prefix lands the user on
its own root rather than the host’s. Django’s own default for `LOGOUT_REDIRECT_URL` is
`None`, and “/” on a host serving several applications is somebody else’s.

> Projects upgrading from 3.0 will have CHI Auth’s logout written into that setting by
> hand, since nothing chained there for them. Such a value is honoured as-is rather than
> wrapped — sign-out keeps working — but the user is left on CHI Auth instead of back on
> your site, and `manage.py check` reports `user_manager.W006` until it is replaced with a
> local path.

Between this and the login handoff, no application needs to write a CHI Auth URL anywhere:
`CHI_AUTH_URL`, `CHI_AUTH_USE_MIDDLEWARE` and your own script prefix determine all of them.

A local superuser who is not in CHI Auth can still reach Django’s admin login at
`/admin/login/`, which is unaffected by any of this.

The headers read are `SSO-Username`, `SSO-Email`, `SSO-Firstname` and `SSO-Lastname`. A user
who doesn’t exist locally is created on first sight, with an unusable password. When there is
no `SSO-Username` header the middleware does nothing, so ordinary session login keeps working
alongside it.

> **These headers are trusted.** Anyone who can reach the application server without going
> through nginx can log in as any user simply by sending `SSO-Username: someone`. Two things
> must be true:
>
> 1. nginx **strips any inbound `SSO-*` headers** before setting its own.
> 2. The application server is not reachable except through nginx.
>
> Set `CHI_AUTH_TRUSTED_PROXIES` and the middleware will enforce (2) itself, ignoring the
> headers on requests that came from anywhere else. `manage.py check` emits
> `user_manager.W001` while it is unset.

```python
# IPs or CIDR ranges of your nginx server(s)
CHI_AUTH_TRUSTED_PROXIES = ["10.0.0.1", "10.1.0.0/24"]
```

nginx side, in outline:

```nginx
location / {
    # set every SSO-* header explicitly, so nothing the client sent survives
    proxy_set_header SSO-Username  $sso_username;
    proxy_set_header SSO-Email     $sso_email;
    proxy_set_header SSO-Firstname $sso_firstname;
    proxy_set_header SSO-Lastname  $sso_lastname;
    proxy_pass http://app;
}
```

### Debugging headers

`user_manager.middleware.InspectHeadersMiddleware` appends the headers of every request to
`header_inspection.log` in `SPECIAL_LOG_FOLDER`, which is useful while getting the nginx
configuration right. Credentials are redacted, but the log still records who visited what —
**it is a debugging aid, not something to leave enabled in production.** It does nothing
unless `SPECIAL_LOG_FOLDER` is set, and `manage.py check` warns (`user_manager.W002`) if it
is active outside `DEBUG`.

```python
MIDDLEWARE = [..., "user_manager.middleware.InspectHeadersMiddleware"]
SPECIAL_LOG_FOLDER = "/var/log/myproject/"
```

## Upgrading from 3.1.0 to 3.1.1

- **`LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL` fall back to `FORCE_SCRIPT_NAME`**
  rather than to “/” when unset. This only changes behaviour for an app served under a
  script prefix that leaves them unset, where the old fallback sent the user to the host
  root — another application, or a 404. Projects that set both are unaffected.

## Upgrading from 3.0 to 3.1

- **`login_view` redirects to CHI Auth when `CHI_AUTH_USE_MIDDLEWARE` is on**, instead of
  rendering its own form. Projects that had pointed `LOGIN_URL` / `LOGIN_URL_FOR_LINK`
  straight at CHI Auth to work around that can point them back at `/user_manager/login` and
  drop the hard-coded URL; `@login_required` then keeps its destination across the round
  trip, which it could not before — Django sends `?next=`, and CHI Auth reads `uri`.
- **`logout_view` chains on to CHI Auth’s logout by itself** in the same mode, so
  `LOGOUT_REDIRECT_URL` should become a path on your own site — where the user lands once
  signed out — rather than the `/auth/logout?uri=…` every project had to write by hand. The
  old form is honoured rather than wrapped, so sign-out does not break on upgrade;
  `user_manager.W006` reports it until it is replaced.
- **`CHI_AUTH_USE_MIDDLEWARE` is now a `user_manager` setting**, read like every other one
  (Django setting, then environment, then default `False`). Projects already setting it from
  the environment need no edit. `manage.py check` reports `user_manager.W004` / `W005` if it
  disagrees with what is actually in `MIDDLEWARE`.

## Upgrading from 2.x to 3.0

- **`logout` is POST only.** Replace any `<a href="{{ LOGOUT_URL_FOR_LINK }}">` with the form
  shown above. This is the only change most projects need.
- **URL names are namespaced by the app.** `user_manager/urls.py` now sets
  `app_name = "user_manager"`, so `include()` no longer needs the two-tuple form.
  `{% url 'user_manager:login' %}` continues to work.
- **The abstract user model path is now a setting.** The default is unchanged
  (`project.abstract_user_model.AbstractCustomUser`), so existing projects need no edit.
- **Users created through the admin and through SSO now get an unusable password** rather
  than an empty one. Set a password on the change form if a local login is wanted.
- **Inactive users are refused by `ChiAuthBackend` and by the SSO middleware.** Previously
  `is_active = False` only blocked local password login. If you were relying on that, note
  that deactivating an account now locks it out completely.
- Add `CHI_AUTH_TRUSTED_PROXIES` if you use header based SSO; see above.

## Dependencies

Depends on resources from [CHI Assets](https://chi.uc.edu/assets/) to display its login form. Specifically:

- [favicon.ico](https://chi.uc.edu/assets/favicon.ico)
- [login.css](https://chi.uc.edu/assets/login.css)
    - [opensans.css](https://chi.uc.edu/assets/fonts/opensans.css)
    - [care_crawley.jpg](https://chi.uc.edu/assets/care_crawley.jpg)


There are no other external dependencies (*e.g.* Bootstrap, jQuery, Font Awesome, *etc.*). Does not depend on particular templates existing in the host project.

## Development

The test suite runs standalone, without a host project:

```shell
pip install -e . ruff
python runtests.py                     # everything
python runtests.py tests.test_views    # one module
ruff check . && ruff format --check .
```
