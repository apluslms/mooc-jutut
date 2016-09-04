from django.conf.urls import include, url
from django.contrib import admin

import accounts.urls


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include(accounts.urls)),
    url(r'^', include('feedback.urls', namespace='feedback')),
]
