import logging
from datetime import timedelta
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from django_lti_login.signals import lti_login_authenticated
from . import SITES_SESSION_KEY, COURSES_SESSION_KEY
from .models import Site, Course


CLEAR_COURSES_DELTA = timedelta(days=30)

logger = logging.getLogger('feedback.receivers')


def clear_old_courses(sender, **kwargs): # pylint: disable=unused-argument
    """
    Clear authorized courses list if user has not legged in 30 days
    """
    request = kwargs.get('request', None)
    user = kwargs.get('user', None)
    if request and user:
        if user.last_login and user.last_login + CLEAR_COURSES_DELTA < timezone.now():
            user.courses.clear()


lti_login_authenticated.connect(clear_old_courses)


def add_course_permissions(sender, **kwargs): # pylint: disable=too-many-locals unused-argument
    """
    Add permissions to course user authenticated with (from oauth).
    Also add courses to session so they are used for permission checks
    """
    request = kwargs.get('request', None)
    user = kwargs.get('user', None)
    oauth = getattr(request, 'oauth', None)

    if request and user and oauth:
        api_token = getattr(oauth, 'custom_user_api_token', None)
        course_id = getattr(oauth, 'custom_context_api_id', None)
        course_api = getattr(oauth, 'custom_context_api', None)
        if api_token is None or course_id is None or course_api is None:
            # Invalid lti login to mooc jutut service. Missing stuff
            # pylint: disable=logging-format-interpolation
            logger.error("LTI login request doesn't contain all required "
                         "fields (custom_user_api_token, custom_context_api_id, "
                         "custom_context_api) for course membership update."
                         "User in question is {}".format(user))
            raise PermissionDenied("LTI request is missing some fields to allow login")

        # store API token
        site = Site.get_by_url(course_api)
        user.add_api_token(api_token, site) # will not add duplicates

        # get or create course
        try:
            course = Course.objects.using_namespace(site).get(api_id=course_id)
        except Course.DoesNotExist:
            apiclient = user.get_api_client(site)
            url, params = apiclient.normalize_url(course_api)
            apiclient.update_params(params)
            course_obj = apiclient.load_data(url)
            course, _created = Course.objects.get_new_or_updated(course_obj, namespace=site)

        # add course membership for permissions
        user.courses.add(course)

        # Redirect to notresponded page after login
        oauth.redirect_url = reverse(
            'feedback:notresponded-course',
            kwargs={'course_id': course.id}
        )

        # List LTI params in debug log
        logger.debug("LTI login for user %s on course %s", user, course)
        for k, v in sorted(oauth.params):
            logger.debug("  \w param -- %s: %s", k, v) # noqa: W605

    if request and user:
        # add courses to users session
        courses = list(user.courses.all())
        request.session[SITES_SESSION_KEY] = [course.namespace_id for course in courses]
        request.session[COURSES_SESSION_KEY] = [course.id for course in courses]


user_logged_in.connect(add_course_permissions)
