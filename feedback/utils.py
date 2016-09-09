from django.conf import settings
from django.template.loader import get_template
from django.utils import translation

from aplus_client.client import AplusGraderClient
from dynamic_forms.forms import DummyForm, DynamicForm


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
        'points': feedback.response_grade,
        'max_points': feedback.MAX_GRADE,
        'feedback': html,
        'grading_payload': '{}'
    }

    r = client.grade(update_data)
    feedback.response_uploaded = r.status_code
    return (r.status_code == 200, r.text)
