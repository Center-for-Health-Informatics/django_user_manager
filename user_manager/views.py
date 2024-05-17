from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.conf import settings


def login_view(request):
    default_redirect = getattr(settings, "LOGIN_REDIRECT_URL", "/")
    next_url = request.GET.get("next", default_redirect)

    if request.user.is_authenticated:
        return redirect(next_url)
    context = {
        "current_page": "login",
    }
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        # authenticates against all settings.AUTHENTICATION_BACKENDS
        oUser = authenticate(request, username=username, password=password)

        if oUser is None:
            context["login_error"] = "Incorrect username or password."
            return render(request, "user_manager/login.html", context)

        # regardless of how they authenticated, do a standard login
        login(request, oUser, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(next_url)

    return render(request, "user_manager/login.html", context)


@login_required
def logout_view(request):
    logout(request)

    next = getattr(settings, "LOGOUT_REDIRECT_URL")
    if not next:
        next = "/"
    return redirect(next)
