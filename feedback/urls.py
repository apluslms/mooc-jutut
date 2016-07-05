from django.conf.urls import url

from .views import (
    FeedbackList,
    FeedbackSubmission,
)


urlpatterns = [
    url(r'^$', FeedbackList.as_view(), name='list'),
    url(r'^(?P<course_id>\d+)/(?P<group_path>[\w\d\-\.\/]+)/$', FeedbackSubmission.as_view(), name='submission'),
]
