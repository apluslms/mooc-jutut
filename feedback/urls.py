from django.conf.urls import url

from .views import (
    FeedbackAverageView,
    FeedbackSubmissionView,
    UnRespondedFeedbackListView,
    UserFeedbackView,
    RespondFeedbackView,
)


urlpatterns = [
    url(r'^feedback/$',
        FeedbackAverageView.as_view(),
        name='list'),
    url(r'^feedback/(?P<course_id>\d+)/(?P<group_path>[\w\d\-\.\/]+)/$',
        FeedbackSubmissionView.as_view(),
        name='submission'),
    url(r'^manage/unresponded/(?P<course_id>\d+)/(?P<group_filter>[\w\d\-\.\/]*)$',
        UnRespondedFeedbackListView.as_view(),
        name='notresponded'),
    url(r'^manage/byuser/(?P<user_id>\d+)/(?P<course_id>\d+)/(?P<group_path>[\w\d\-\.\/]*)$',
        UserFeedbackView.as_view(),
        name='byuser'),
    url(r'^manage/respond/(?P<feedback_id>\d+)/$',
        RespondFeedbackView.as_view(),
        name='respond'),
]
