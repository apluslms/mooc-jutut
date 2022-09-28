from django.conf.urls import url
from django.contrib.auth import views as auth_views

import django_lti_login.views


urlpatterns = [
    # Only some of the auth.urls are currently enable
    #url('^', include('django.contrib.auth.urls')),
    url(r'^login/$', auth_views.LoginView.as_view(), name='login'),
    url(r'^logout/$', auth_views.LogoutView.as_view(), name='logout'),
    url(r'^lti_login$', django_lti_login.views.lti_login, name='lti_login'),
]
