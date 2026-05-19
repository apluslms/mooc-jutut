from django.conf import settings
from django.urls import path
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
    path('feedback/',
        FeedbackSubmissionView_view,
        name='submission'),
    re_path(r'^feedback/(?P<path_key>{path_regex}+)$'.format(path_regex=PATH_REGEX),
        FeedbackSubmissionView_view,
        name='submission'),

    # Feedback management and responding
    path('manage/',
        views.ManageSiteListView.as_view(),
        name='site-list'),
    path('manage/courses/',
        ManageCourseListView_view,
        name='course-list'),
    path('manage/courses/<int:site_id>/',
        ManageCourseListView_view,
        name='course-list'),
    path('manage/<int:course_id>/update-studenttags/',
        views.ManageUpdateStudenttagsView.as_view(),
        name='update-studenttags'),
    path('manage/<int:course_id>/unread/',
        ManageNotRespondedListView_view,
        name='notresponded-course'),
    re_path(r'^manage/(?P<course_id>\d+)/unread/(?P<path_filter>{path_regex}*)$'.format(path_regex=PATH_REGEX),
        ManageNotRespondedListView_view,
        name='notresponded-course'),
    path('manage/<int:course_id>/feedbacks/',
        views.ManageFeedbacksListView.as_view(),
        name='list'),
    path('manage/<int:course_id>/background/<int:student_id>/',
        views.StudentBackgroundView.as_view(),
        name='background'),
    path('manage/points/<int:conversation_id>/',
        views.FeedbackPointsView.as_view(),
        name='points'),
    path('manage/<int:course_id>/user/',
        UserListView_view,
        name='user-list'),
    path('manage/<int:course_id>/byuser/<int:user_id>/',
        UserFeedbackListView_view,
        name='byuser'),
    path('manage/<int:course_id>/tags/',
        views.FeedbackTagListView.as_view(),
        name='tags'),
    path('manage/<int:course_id>/tags/<int:tag_id>/',
        views.FeedbackTagEditView.as_view(),
        name='tags-edit'),
    path('manage/<int:course_id>/tags/<int:tag_id>/remove/',
        views.FeedbackTagDeleteView.as_view(),
        name='tags-remove'),
    path('manage/<int:course_id>/tags/import/',
        views.ImportTagsView.as_view(),
        name='tags-import'),
    path('manage/<int:course_id>/contexttags/',
        views.ContextTagListView.as_view(),
        name='contexttags'),
    path('manage/<int:course_id>/contexttags/<int:tag_id>/',
        views.ContextTagEditView.as_view(),
        name='contexttags-edit'),
    path('manage/<int:course_id>/contexttags/<int:tag_id>/remove/',
        views.ContextTagDeleteView.as_view(),
        name='contexttags-remove'),
    path('manage/respond/<int:feedback_id>/',
        RespondFeedbackView_view,
        name='respond'),
    path('manage/status/<int:feedback_id>/',
        views.ResponseStatusView.as_view(),
        name='status'),
    path('manage/tag/<int:conversation_id>/',
        views.FeedbackTagView.as_view(),
        name='tag-list'),
    path('manage/tag/<int:conversation_id>/<int:tag_id>/',
        views.FeedbackTagView.as_view(),
        name='tag'),

    # support for old urls
    path('manage/notresponded/course/<int:course_id>/',
         ManageNotRespondedListView_view),
    re_path(r'^manage/notresponded/course/(?P<course_id>\d+)/(?P<path_filter>{path_regex}*)$'
    .format(path_regex=PATH_REGEX),
         ManageNotRespondedListView_view),
    path('manage/user/<int:course_id>/',
        UserListView_view),
    path('manage/byuser/<int:course_id>/<int:user_id>/',
        UserFeedbackListView_view),
]
