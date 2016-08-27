from django.conf.urls import url

from .views import (
    FeedbackAverageView,
    FeedbackSubmissionView,
    ManageSiteListView,
    ManageCourseListView,
    ManageNotRespondedListView,
    UserListView,
    UserFeedbackListView,
    UserFeedbackView,
    RespondFeedbackView,
)

join = lambda *x: '/'.join(x)


PATH_REGEX = r'[\w\d\-./]'
MANAGE = r'^manage/'
MANAGE_SITE = MANAGE + r'(?P<site_id>\d+)/'


urlpatterns = [
    # Aplus feedback submission
    url(r'^feedback/$',
        FeedbackAverageView.as_view(),
        name='list'),
    url(r'^feedback/(?P<path_key>{path_regex}+)/$'.format(path_regex=PATH_REGEX),
        FeedbackSubmissionView.as_view(),
        name='submission'),

    # Feedback management and responding
    url(r'^manage/$',
        ManageSiteListView.as_view(),
        name='site-list'),
    url(r'^manage/courses/$',
        ManageCourseListView.as_view(),
        name='course-list'),
    url(r'^manage/courses/(?P<site_id>\d+)/$',
        ManageCourseListView.as_view(),
        name='course-list'),
    url(r'^manage/notresponded/course/(?P<course_id>\d+)/(?P<path_filter>{path_regex}*)$'.format(path_regex=PATH_REGEX),
        ManageNotRespondedListView.as_view(),
        name='notresponded-course'),
    url(r'^manage/notresponded/exercise/(?P<exercise_id>\d+)/$',
        ManageNotRespondedListView.as_view(),
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
