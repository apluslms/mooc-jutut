from django.urls import include, path, re_path
from django.conf import settings
from django.contrib import admin

import core.urls
import accounts.urls
import feedback.urls
import timeusage.urls


urlpatterns = [
    path('', include(feedback.urls)),
    path('timeusage/', include(timeusage.urls)),
    path('', include(core.urls)),
    path('i18n/', include('django.conf.urls.i18n')),
    re_path(r'^admin/', admin.site.urls),
    path('accounts/', include(accounts.urls)),
]

if settings.ENABLE_DJANGO_DEBUG_TOOLBAR:
    import debug_toolbar
    urlpatterns.insert(
        0,
        path('__debug__/', include(debug_toolbar.urls)),
    )
