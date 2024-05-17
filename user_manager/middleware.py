import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings


class InspectHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # code to be executed before view
        try:
            log_folder = settings.SPECIAL_LOG_FOLDER
        except AttributeError:
            return
        with open(log_folder + "header_inspection.log", mode="a+") as file_object:
            print("", file=file_object)
            print(datetime.datetime.now(), file=file_object)
            for key in request.META:
                if key.startswith("HTTP"):
                    print(key, request.META[key], file=file_object)

        response = self.get_response(request)

        # Code to be executed after view

        return response


class ChiAuthLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        username = request.META.get("HTTP_SSO_USERNAME")
        if username and not username.lower().strip() in ["", "none", "null"]:
            User = get_user_model()
            oUser = User.objects.filter(username=username).first()
            if not oUser:
                oUser = User(
                    username=username,
                    email=request.META.get("HTTP_SSO_EMAIL", ""),
                    first_name=request.META.get("HTTP_SSO_FIRSTNAME", ""),
                    last_name=request.META.get("HTTP_SSO_LASTNAME", ""),
                )
                oUser.save()
            request.user = oUser
        else:
            request.user = AnonymousUser()

        # continue to next entry in middleware chain
        response = self.get_response(request)

        # Code to be executed after view

        return response
