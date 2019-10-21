from django.shortcuts import render, redirect, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.conf import settings

import requests





def login_view(request):
    next_url = request.GET.get('next', '/')
    
    if request.user.is_authenticated:
        return redirect(next_url)
    context = {
        'current_page' : 'login',
    }
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        # authenticates against all settings.AUTHENTICATION_BACKENDS
        oUser = authenticate(request, username=username, password=password)

        if oUser is None:
            context['login_error'] = 'Login failed. Please reenter your username and password.'
            return render(request, 'user_manager/login.html', context)
        
        # regardless of how they authenticated, do a standard login
        login(request, oUser, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(next_url)

    return render(request, 'user_manager/login.html', context)

@login_required
def logout_view(request):
    logout(request)
    
    next = getattr(settings, 'LOGOUT_REDIRECT_URL')
    if not next:
        next = '/'
    return redirect(next)


