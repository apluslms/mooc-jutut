from django.urls import path
from . import views
from .apps import TimeUsageConfig

app_name = TimeUsageConfig.name
urlpatterns = [
    path('<int:course_id>/',
    views.TimeUsageView.as_view(),
    name='time-usage')
]
