from django.conf.urls import url
from . import views
from .apps import TimeUsageConfig

app_name = TimeUsageConfig.name
urlpatterns = [
    url(r'^timeusage/(?P<course_id>\d+)/$',
    views.TimeUsageView.as_view(),
    name='time-usage')
]
