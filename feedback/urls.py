from django.conf.urls import url

from .views import (
    FeedbackAverageView,
    FeedbackSubmissionView,
    UnRespondedCourseListView,
    UnRespondedFeedbackListView,
    UserListView,
    UserFeedbackListView,
    UserFeedbackView,
    RespondFeedbackView,
)


PATH_REGEX = r'[\w\d\-./]'


urlpatterns = [
    url(r'^feedback/$',
        FeedbackAverageView.as_view(),
        name='list'),
    url(r'^feedback/(?P<path_key>{path_regex}+)/$'.format(path_regex=PATH_REGEX),
        FeedbackSubmissionView.as_view(),
        name='submission'),
    url(r'^manage/unresponded/$',
        UnRespondedCourseListView.as_view(),
        name='course-list'),
    url(r'^manage/unresponded/course/(?P<course_id>\d+)/(?P<path_filter>{path_regex}*)$'.format(path_regex=PATH_REGEX),
        UnRespondedFeedbackListView.as_view(),
        name='notresponded-course'),
    url(r'^manage/unresponded/exercise/(?P<exercise_id>\d+)/$',
        UnRespondedFeedbackListView.as_view(),
        name='notresponded-exercise'),
    url(r'^manage/byuser/$',
        UserListView.as_view(),
        name='user-list'),
    url(r'^manage/byuser/(?P<user_id>\d+)/$',
        UserFeedbackListView.as_view(),
        name='user'),
    url(r'^manage/byuser/(?P<user_id>\d+)/(?P<exercise_id>\d+)/$',
        UserFeedbackView.as_view(),
        name='byuser'),
    url(r'^manage/respond/(?P<feedback_id>\d+)/$',
        RespondFeedbackView.as_view(),
        name='respond'),
]
