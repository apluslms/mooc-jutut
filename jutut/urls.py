from django.conf.urls import include, url
from django.contrib import admin

import core.urls
import accounts.urls
import feedback.urls


urlpatterns = [
    url(r'^', include(feedback.urls)),
    url(r'^', include(core.urls)),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include(accounts.urls)),
]
