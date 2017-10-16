from django.conf import settings
from django.conf.urls import url
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView

from . import views

def cache(time=60 * 15):
    if settings.DEBUG:
        return lambda x: x
    return cache_page(time)


urlpatterns = [
    url(r'^$',
        TemplateView.as_view(template_name="core/frontpage.html"),
        name='fronpage'),
    url(r'^servicestatus/$',
        views.ServiceStatusPage.as_view(),
        name='servicestatus'),
    url(r'^servicestatus/data/$',
        cache(10)(views.ServiceStatusData.as_view()),
        name='servicestatus-data'),
]
