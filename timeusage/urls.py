from django.urls import re_path
from . import views
from .apps import TimeUsageConfig

app_name = TimeUsageConfig.name
urlpatterns = [
    re_path(r'^(?P<course_id>\d+)/$',
    views.TimeUsageView.as_view(),
    name='time-usage')
]
