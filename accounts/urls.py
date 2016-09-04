from django.conf.urls import include, url
from django.contrib import admin



urlpatterns = [
    url('^', include('django.contrib.auth.urls')),
    url(r'^lti_login$', 'django_lti_login.views.lti_login', name='lti_login'),
]
