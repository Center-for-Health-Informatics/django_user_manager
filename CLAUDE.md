# user_manager — working notes

A Django app packaged as a library, pinned by tag in `daedalus`, `email_service` and
`monitor`. It is the estate's one *versioned package* coupling, in chi-platform
`conventions.md`'s sense: a change here reaches consumers on rebuild plus a pin bump, and
never before. That is the whole reason it is worth the ceremony — fix something once here
and every consumer gets it, instead of the same issue being filed *n* times.

Rules below are rules with reasons. If a reason has expired, change the rule and say so;
don't quietly work around it.

## Configuration

**`settings.py` is the only configuration surface.** `custom_settings.get_setting` reads
the Django setting, then its own default, and nothing else. It used to fall back to
`os.getenv`, which meant a variable could take effect in a deployment while appearing in no
`settings.py` and no `example.settings.env` — `CHI_AUTH_TIMEOUT` governed sign-in latency
for three services through a surface no repository documented. Don't add the fallback back;
a consumer wanting deployment configuration writes the `getenv` call itself.

**`_to_bool` is strict on purpose.** Only a case-insensitive `true`. This matches the
`env_bool` helper copied into all four consumers, whose docstring is the argument: a
setting that silently reads as False when someone wrote `'1'` is worse than one that never
accepts `'1'`, because the first kind is only noticed in production. The booleans here
decide whether header SSO is in use and whether accounts get provisioned.

**A new setting needs a reason to exist.** Issue #9 surveyed the deployed configs and
found most knobs were either uniform across every consumer or set nowhere at all. Options
nobody exercises are options nobody tests.

## Authentication

**Two login paths, and they must agree.** `ChiAuthLoginMiddleware` (header SSO) and
`ChiAuthBackend` (password) are separate code that answers the same questions — does this
user exist, may they in, do we create them. Issue #8 was those two drifting apart for
years. When you change one, check the other.

**Usernames match with `__iexact`, and the stored spelling is never rewritten.** The
directory behind CHI Auth is case-insensitive and the `SSO-Username` header carries
whatever the user typed. `already_logged_in` casefolds too — otherwise a changed casing
looks like a different person and re-`login()`s on every request, cycling the session key.

**`from_trusted_proxy` is correct only under one deployment topology, and that fact
belongs next to the code.** It compares `REMOTE_ADDR` against `CHI_AUTH_TRUSTED_PROXIES`.
With a namespace-sharing sidecar (`network_mode: "service:app"`) and gunicorn bound to
`127.0.0.1`, nginx reaches the app as `127.0.0.1` and nothing off-box can, so
`127.0.0.1/32` is a real check. With a *bridge*-networked sidecar it distinguishes
nothing — `REMOTE_ADDR` is the bridge gateway for proxied and direct requests alike — and
setting it merely silences `W001`. That is how daedalus ran fully bypassable with
`172.16.0.0/12` (daedalus#73), and it is what issue #10 was filed over. All three
consumers have since converted, so the check works today; the missing piece was never the
code, it was the precondition being written down. Keep it written down.

The primary control is still the port binding, not this — `conventions.md`, "A published
port must name an address that cannot default". `W001` firing at startup in a converted
deployment means the variable is not reaching the app: find out why, don't silence it.

**`logout` is POST-only.** A GET logout is CSRF-able and gets triggered by link
prefetchers, which is why Django dropped GET from its own `LogoutView` in 5.0.

**Sign-in and sign-out are deliberately asymmetric.** In goes upstream first (only CHI Auth
can mint the session the headers describe); out goes local first and chains upstream after
(CHI Auth's logout is GET-only in another app, so a cross-app POST fails CSRF).

**The `?uri=` encoding rule is load-bearing.** CHI Auth reads `uri` out of the raw query
string, taking everything to the end — so nothing may follow it, and `chi_auth_url` returns
a finished URL rather than something to append to. A plain path goes raw (the form nginx
sends, and the only readable one); anything carrying its own query string is quoted, so a
crafted `next` cannot smuggle a second `uri` to the next hop.

## The model

**No migrations ship.** The `User` model's shape comes from the project's
`AbstractCustomUser`, so it cannot live here. Every consumer sets `MIGRATION_MODULES`;
`user_manager.W003` warns when one forgets.

**`default_auto_field` stays `AutoField`.** The one place the estate departs from
`conventions.md`'s `BigAutoField` rule, deliberately — see the comment in `apps.py`.

## Tests

`python runtests.py` — the suite runs standalone, with no host project. `tests/settings.py`
is the whole "project".

The redirect-safety battery in `tests/test_views.py` exists so a refactor that stops
checking `next` fails the suite rather than shipping. Don't loosen it.

The standalone suite cannot see a real consumer. Anything touching settings resolution,
the checks, or the login paths should also be run against `email_service` with the branch
installed over its pin, because that is the deployment where the security-relevant
settings are actually set.
