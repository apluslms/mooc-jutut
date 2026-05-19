from django.urls import path
from django.contrib.auth import views as auth_views

import django_lti_login.views


urlpatterns = [
    # Only some of the auth.urls are currently enable
    #re_path('^', include('django.contrib.auth.urls')),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('lti_login', django_lti_login.views.lti_login, name='lti_login'),
]
