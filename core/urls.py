from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView

from .apps import CoreConfig
from . import views

def cache(time=60 * 15):
    if settings.DEBUG:
        return lambda x: x
    return cache_page(time)


app_name = CoreConfig.name
urlpatterns = [
    path('',
        TemplateView.as_view(template_name="core/frontpage.html"),
        name='fronpage'),
    path('manage/servicestatus/',
        views.ServiceStatusPage.as_view(),
        name='servicestatus'),
    path('manage/servicestatus/data/',
        cache(10)(views.ServiceStatusData.as_view()),
        name='servicestatus-data'),
    path('manage/clear-cache/',
        views.ClearCache.as_view(),
        name='clear-cache'),
]
