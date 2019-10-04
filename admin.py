# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models
from . import forms






class CustomUserAdmin(UserAdmin):
    '''We want to override the Add User form to remove password and add
       name and email fields.
    '''
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name'),
        }),
    )
    
    add_form = forms.CustomUserCreationForm



admin.site.register(models.User, CustomUserAdmin)