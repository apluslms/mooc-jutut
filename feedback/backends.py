import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import PermissionDenied

from aplus_client.client import AplusTokenClient
from .models import Site, Course


logger = logging.getLogger('feedback.backends')


@receiver(user_logged_in)
def add_course_permissions(sender, **kwargs):
    request = kwargs.get('request', None)
    user = kwargs.get('user', None)
    oauth = getattr(request, 'oauth', None)
    if oauth is not None:
        api_token = getattr(oauth, 'custom_user_api_token', None)
        course_id = getattr(oauth, 'custom_context_api_id', None)
        course_api = getattr(oauth, 'custom_context_api', None)
        if api_token is None or course_id is None or course_api is None:
            # Invalid lti login to mooc jutut service. Missing stuff
            logger.error("LTI login request doesn't contain all required "
                         "fields (custom_user_api_token, custom_context_api_id, "
                         "custom_context_api) for course membership update."
                         "User in question is {}".format(user))
            raise PermissionDenied("LTI request is missing some fields to allow login")

        site = Site.get_by_url(course_api)
        user.add_api_token(api_token, site) # will not add duplicates

        try:
            course = Course.objects.using_namespace(site).get(api_id=course_id)
        except Course.DoesNotExist:
            apiclient = user.get_api_client(site)
            url, params = apiclient.normalize_url(course_api)
            apiclient.update_params(params)
            course_obj = apiclient.load_data(url)
            course = Course.objects.get_new_or_updated(course_obj, namespace=site)

        logger.debug("LTI login for user %s on course %s", user, course)
        for k, v in sorted(oauth.params):
            logger.debug("  \w param -- %s: %s", k, v)

