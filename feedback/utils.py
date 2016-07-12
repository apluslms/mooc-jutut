from django.template import Context
from django.template.loader import get_template

from aplus_client.client import AplusGraderClient
from dynamic_forms.forms import DummyForm, DynamicForm


def update_response_to_aplus(feedback):
    submission_url = feedback.submission_url
    client = AplusGraderClient(submission_url)

    form_obj = feedback.form
    form_spec = form_obj.form_spec if form_obj else None
    form_class = DynamicForm.get_form_class_by(form_spec) if form_spec else DummyForm
    form = form_class(data=feedback.form_data)

    template = get_template('feedback/_feedback_form.html')
    context = Context({
        'feedback': feedback,
        'post_url': feedback.post_url,
        'form': form,
    })
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
