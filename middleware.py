import datetime

from django.contrib.auth.middleware import RemoteUserMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
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
        with open(log_folder + 'header_inspection.log', mode='a+') as file_object:
            print('', file=file_object)
            print( datetime.datetime.now(), file=file_object )
            for key in request.META:
                if key.startswith('HTTP'):
                    print(key, request.META[key], file=file_object)

        response = self.get_response(request)

        # Code to be executed after view

        return response
    
class ChiAuthLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        username = request.META.get('HTTP_SSO_USERNAME')
        if username:
            User = get_user_model()
            oUser = User.objects.filter(username=username).first()
            if not oUser:
                oUser = User(
                    username=username,
                    email = request.META.get('HTTP_SSO_EMAIL', ''),
                    first_name = request.META.get('HTTP_SSO_FIRSTNAME', ''),
                    last_name = request.META.get('HTTP_SSO_LASTNAME', '')
                )
                oUser.save()
            request.user = oUser
        else:
            request.user = AnonymousUser()
            
        
        # continue to next entry in middleware chain
        response = self.get_response(request)

        # Code to be executed after view

        return response
    

                    

# class ChiAuthLoginMiddlewareOld(RemoteUserMiddleware):
#     """authenticate user using the header HTTTP_UID from OIM"""
#     header = 'HTTP_SSO_USERNAME'
#     first_name = 'HTTP_SSO_FIRSTNAME'
#     last_name = 'HTTP_SSO_LASTNAME'
#     email = 'HTTP_SSO_EMAIL'
# 
#     def store_user_info(self, request, user):
#         if not user.first_name or not user.last_name or not user.email:
#             # if user did not have a name or email, add it
#             user.first_name = request.META[self.first_name]
#             user.last_name = request.META[self.last_name]
#             user.email = request.META[self.email]
#             user.save()
# 
#     def process_request(self, request):
#         username = ''
#         if self.header in request.META:
#             username = request.META[self.header].lower()
#             request.META[self.header] = username
#         super(ChiAuthLoginMiddleware, self).process_request(request)
#         try:
#             if username:
#                 User = get_user_model()
#                 user = User.objects.get(username=username)
#                 self.store_user_info(request, user)
#         except ObjectDoesNotExist:
#             # user did not exist
#             self._remove_invalid_user(request)
#         except KeyError:
#             # if could not find first_name, last_name or email
#             pass
