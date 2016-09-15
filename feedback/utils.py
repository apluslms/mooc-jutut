import logging
from urllib.parse import urljoin
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils import translation

from aplus_client.client import AplusGraderClient
from dynamic_forms.forms import DummyForm, DynamicForm


logger = logging.getLogger("feedback.utils")


def update_response_to_aplus(feedback):
    submission_url = feedback.submission_url
    client = AplusGraderClient(submission_url, debug_enabled=settings.DEBUG)

    template = get_template('feedback/_form.html')
    context = {
        'feedback': feedback,
        'post_url': feedback.post_url,
        'exercise': feedback.exercise,
        'form': feedback.form_obj,
    }
    with translation.override(feedback.language):
        html = template.render(context)

    update_data = {
        # A-Plus API doc:
        # * `points` (required)
        # * `max_points` (required)
        # * `feedback` (optional)
        #     Feedback presented to the student for the submission.
        # * `grading_payload` (optional)
        #     Payload stored in the submission for course staff. If the submission
        #     was not created with FORM POST this is important for later investigations.
        # * `error` (optional)
        #     Sets the submission to an error state.
        # * `notify` (optional)
        #     If exists and not empty, create notification in a-plus for students in submission
        'points': feedback.response_grade,
        'max_points': feedback.MAX_GRADE,
        'feedback': html,
        'grading_payload': '{}'
    }
    if feedback.response_msg.strip():
        update_data['notify'] = "true"

    r = client.grade(update_data)
    feedback.response_uploaded = r.status_code
    log_method = logger.debug if r.status_code == 200 else logger.critical
    log_method("Update to submission_url '%s' returned with code %d and text '%s'", submission_url, r.status_code, r.text)
    return (r.status_code == 200, r.text)


def obj_with_attrs(obj, **kwargs):
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def get_url_reverse_resolver(urlname, kwargs, query=None):
    """
    Django doesn't support caching url reverse resolving,
    thus we hack around it
    """
    if not isinstance(kwargs, dict):
        kwargs = {n: i*100+i for i, n in enumerate(kwargs, 2)}
    url = str(reverse(urlname, kwargs=kwargs))
    for n, i in kwargs.items():
        url = url.replace('/{}/'.format(i), '/{{{}}}/'.format(n))
    if query:
        url = urljoin(url, '?'+query)
    return url.format
