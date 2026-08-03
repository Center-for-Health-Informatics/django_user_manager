from django.urls import path

from . import views

# so {% url 'user_manager:login' %} can’t be confused with django.contrib.auth’s own
# 'login' and 'logout' url names
app_name = "user_manager"

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
]
