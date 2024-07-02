from django.conf import settings
from django.urls import re_path
from django.views.decorators.cache import cache_page
from .apps import FeedbackConfig
from . import views

cache = cache_page(60 * 15) if not settings.DEBUG else lambda x: x

FeedbackSubmissionView_view = cache(views.FeedbackSubmissionView.as_view())
ManageCourseListView_view = views.ManageCourseListView.as_view()
ManageNotRespondedListView_view = views.ManageNotRespondedListView.as_view()
UserListView_view = views.UserListView.as_view()
UserFeedbackListView_view = views.UserFeedbackListView.as_view()
RespondFeedbackView_view = views.respond_feedback_view_select(
    views.RespondFeedbackView.as_view(),
    views.RespondFeedbackViewAjax.as_view()
)
FeedbackTagView_view = views.FeedbackTagView.as_view()


PATH_REGEX = r'[\w\d\-./]'
MANAGE = r'^manage/'
MANAGE_SITE = MANAGE + r'(?P<site_id>\d+)/'


app_name = FeedbackConfig.name
urlpatterns = [
    # Aplus feedback submission
    re_path(r'^feedback/$',
        FeedbackSubmissionView_view,
        name='submission'),
    re_path(r'^feedback/(?P<path_key>{path_regex}+)$'.format(path_regex=PATH_REGEX),
        FeedbackSubmissionView_view,
        name='submission'),

    # Feedback management and responding
    re_path(r'^manage/$',
        views.ManageSiteListView.as_view(),
        name='site-list'),
    re_path(r'^manage/courses/$',
        ManageCourseListView_view,
        name='course-list'),
    re_path(r'^manage/courses/(?P<site_id>\d+)/$',
        ManageCourseListView_view,
        name='course-list'),
    re_path(r'^manage/(?P<course_id>\d+)/update-studenttags/$',
        views.ManageUpdateStudenttagsView.as_view(),
        name='update-studenttags'),
    re_path(r'^manage/(?P<course_id>\d+)/unread/$',
        ManageNotRespondedListView_view,
        name='notresponded-course'),
    re_path(r'^manage/(?P<course_id>\d+)/unread/(?P<path_filter>{path_regex}*)$'.format(path_regex=PATH_REGEX),
        ManageNotRespondedListView_view,
        name='notresponded-course'),
    re_path(r'^manage/(?P<course_id>\d+)/feedbacks/$',
        views.ManageFeedbacksListView.as_view(),
        name='list'),
    re_path(r'^manage/(?P<course_id>\d+)/background/(?P<student_id>\d+)/$',
        views.StudentBackgroundView.as_view(),
        name='background'),
    re_path(r'^manage/points/(?P<conversation_id>\d+)/$',
        views.FeedbackPointsView.as_view(),
        name='points'),
    re_path(r'^manage/(?P<course_id>\d+)/user/$',
        UserListView_view,
        name='user-list'),
    re_path(r'^manage/(?P<course_id>\d+)/byuser/(?P<user_id>\d+)/$',
        UserFeedbackListView_view,
        name='byuser'),
    re_path(r'^manage/(?P<course_id>\d+)/tags/$',
        views.FeedbackTagListView.as_view(),
        name='tags'),
    re_path(r'^manage/(?P<course_id>\d+)/tags/(?P<tag_id>\d+)/$',
        views.FeedbackTagEditView.as_view(),
        name='tags-edit'),
    re_path(r'^manage/(?P<course_id>\d+)/tags/(?P<tag_id>\d+)/remove/$',
        views.FeedbackTagDeleteView.as_view(),
        name='tags-remove'),
    re_path(r'^manage/(?P<course_id>\d+)/tags/import/$',
        views.ImportTagsView.as_view(),
        name='tags-import'),
    re_path(r'^manage/(?P<course_id>\d+)/contexttags/$',
        views.ContextTagListView.as_view(),
        name='contexttags'),
    re_path(r'^manage/(?P<course_id>\d+)/contexttags/(?P<tag_id>\d+)/$',
        views.ContextTagEditView.as_view(),
        name='contexttags-edit'),
    re_path(r'^manage/(?P<course_id>\d+)/contexttags/(?P<tag_id>\d+)/remove/$',
        views.ContextTagDeleteView.as_view(),
        name='contexttags-remove'),
    re_path(r'^manage/respond/(?P<feedback_id>\d+)/$',
        RespondFeedbackView_view,
        name='respond'),
    re_path(r'^manage/status/(?P<feedback_id>\d+)/$',
        views.ResponseStatusView.as_view(),
        name='status'),
    re_path(r'^manage/tag/(?P<conversation_id>\d+)/$',
        views.FeedbackTagView.as_view(),
        name='tag-list'),
    re_path(r'^manage/tag/(?P<conversation_id>\d+)/(?P<tag_id>\d+)/$',
        views.FeedbackTagView.as_view(),
        name='tag'),

    # support for old urls
    re_path(r'^manage/notresponded/course/(?P<course_id>\d+)/$',
         ManageNotRespondedListView_view),
    re_path(r'^manage/notresponded/course/(?P<course_id>\d+)/(?P<path_filter>{path_regex}*)$'
    .format(path_regex=PATH_REGEX),
         ManageNotRespondedListView_view),
    re_path(r'^manage/user/(?P<course_id>\d+)/$',
        UserListView_view),
    re_path(r'^manage/byuser/(?P<course_id>\d+)/(?P<user_id>\d+)/$',
        UserFeedbackListView_view),
]
