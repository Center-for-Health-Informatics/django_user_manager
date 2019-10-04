from __future__ import unicode_literals

import requests

from django.conf import settings
from django.contrib.auth import get_user_model

class ChiAuthBackend(object):
    """
    Authenticates against UC's AD using the API from my SSO application.
    
    1. If user does not exist here already, they will not be created.
    2. The API call I'm using is just a proxy for UC's LDAP system.
       It only cares if the username/PW matches in LDAP, not how that user is
       defined locally on the SSO site.  
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        UserModel = get_user_model()
        oUser = UserModel.objects.filter(username=username).first()
        
        # if no user and we're not autocreating users, can quit here
        if oUser is None and not settings.CHI_AUTH_AUTOCREATE_LOCAL_USER:
            return None
        # attempt to authenticate
        payload = {
            'username' : username, 
            'systems' : settings.CHI_AUTH_CHECK_SYSTEMS,      
        }
        headers = {
           'x-password' :  password,
           'x-access-token' : settings.CHI_AUTH_API_ACCESS_TOKEN,
        }
        r = requests.get(settings.CHI_AUTH_URL + 'api/authenticate', params=payload, headers=headers)
        response = r.json()
        if 'authenticated' in response and response['authenticated']:
            authenticated = True
        else:
            authenticated = False
            
        # if user exists locally and they authenticated, we're good
        if authenticated and oUser:
            return oUser
        
        print(authenticated)
        print(oUser)
        print(settings.CHI_AUTH_AUTOCREATE_LOCAL_USER)
        
        # if we're autocreating and we authenticated a user that doesn't exist, create them
        if authenticated and oUser is None and settings.CHI_AUTH_AUTOCREATE_LOCAL_USER:
            oUser = UserModel.objects.create_user(
                username=response['user']['username'],
                email=response['user']['email'],
            )
            oUser.first_name = response['user']['first_name']
            oUser.last_name = response['user']['last_name']
            oUser.save()
            return oUser
    
        return None
    


    # this is just a copy of the default get_user method from django.contrib.auth.backends.ModelBackend
    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
    
    # this is only here because get_user uses it
    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don't have
        that attribute are allowed.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None
    
    
    
    
    
    
    
    
    
    
    
    