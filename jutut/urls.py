from django.conf.urls import url
from django.urls import include, path
from django.conf import settings
from django.contrib import admin

import core.urls
import accounts.urls
import feedback.urls
import timeusage.urls


urlpatterns = [
    url(r'^', include(feedback.urls)),
    url(r'^timeusage/', include(timeusage.urls)),
    url(r'^', include(core.urls)),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include(accounts.urls)),
]

if settings.ENABLE_DJANGO_DEBUG_TOOLBAR:
    import debug_toolbar
    urlpatterns.insert(
        0,
        path('__debug__/', include(debug_toolbar.urls)),
    )
