from django.urls import re_path
from django.contrib.auth import views as auth_views

import django_lti_login.views


urlpatterns = [
    # Only some of the auth.urls are currently enable
    #re_path('^', include('django.contrib.auth.urls')),
    re_path(r'^login/$', auth_views.LoginView.as_view(), name='login'),
    re_path(r'^logout/$', auth_views.LogoutView.as_view(), name='logout'),
    re_path(r'^lti_login$', django_lti_login.views.lti_login, name='lti_login'),
]
