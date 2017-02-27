import logging
from urllib.parse import urljoin, urlencode
from django.conf import settings
from django.core.urlresolvers import reverse
from django.forms import CharField
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
    if feedback.response_notify:
        update_data['notify'] = feedback.response_notify_aplus

    r = client.grade(update_data, timeout=(6.4, 46))
    feedback.response_uploaded = r.status_code
    log_method = logger.debug if r.status_code == 200 else logger.critical
    log_method("Update of feedback %d to submission_url '%s' returned with %d: '%s'", feedback.id, submission_url, r.status_code, r.text)
    return (r.status_code == 200, r.text)


def obj_with_attrs(obj, **kwargs):
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def get_url_reverse_resolver(urlname, kwargs, data_func, query=None, query_func=None):
    """
    Django doesn't support caching url reverse resolving,
    thus we hack around it

    Expects the url pointed by the urlname to contain only keyword arguments
    and that the url doesn't contain `/<some numbers>/  parts.
    """
    replace_map = {n: i*100+i for i, n in enumerate(kwargs, 2)}
    url = str(reverse(urlname, kwargs=replace_map))
    for n, i in replace_map.items():
        url = url.replace('/{}/'.format(i), '/{{{}}}/'.format(n))

    def resolver(*sources):
        data = dict(zip(kwargs, data_func(*sources)))
        location = url.format(**data)
        qdict = query or ()
        if query_func:
            qdict = dict(qdict, **query_func(*sources))
        if qdict:
            location = urljoin(location, '?' + urlencode(qdict))
        return location
    return resolver


## Augment dynamicform to tell us few jutut specifig things
# if this is correct source for the information in long run,
# then dynamicform should be subclasses and functionality moved there

def augment_form_with_optional_field_info(form):
    """
    adds .jutut_meta with keys required_text_fields and optional_text_fields
    to form
    """
    required_text_fields = {}
    optional_text_fields = {}

    for name, field in form.fields.items():
        if isinstance(field, CharField):
            d = required_text_fields if field.required else optional_text_fields
            d[name] = field

    form.jutut_meta = {
        'required_text_fields': required_text_fields,
        'optional_text_fields': optional_text_fields,
    }

def augment_form_with_optional_answers_info(form, use_cleaned_data=True):
    """
    requires .jutut_meta with key optional_text_fields
    adds key has_optional_answers
    """
    data_key = 'cleaned_data' if use_cleaned_data else 'data'
    data = getattr(form, data_key, None)
    assert data is not None, "form given is missing .{}".format(data_key)
    jutut_meta = getattr(form, 'jutut_meta', None)
    assert jutut_meta is not None, "Form given is missing .jutut_meta"
    optional_text_fields = jutut_meta['optional_text_fields']

    min_len = settings.JUTUT_TEXT_FIELD_MIN_LENGTH
    ok = lambda x: bool(x) and len(x) > min_len
    jutut_meta['has_optional_answers'] = any(
        ok(data[name]) for name, field in optional_text_fields.items()
    )

def form_can_be_autoaccepted(form):
    """
    requires .jutut_meta with required_text_fields and has_optional_answers
    returns if form can be automatically accepted
    """
    jutut_meta = getattr(form, 'jutut_meta', None)
    assert jutut_meta is not None, "Form is missing .jutut_meta"

    has_no_required_text_fields = not jutut_meta['required_text_fields']
    has_no_optional_texT_answers = not jutut_meta['has_optional_answers']

    return has_no_required_text_fields and has_no_optional_texT_answers

def is_grade_restricted_to_good(form):
    """
    requires .jutut_meta with key required_text_fields
    returns if only good grade should be shown
    """
    jutut_meta = getattr(form, 'jutut_meta', None)
    assert jutut_meta is not None, "Form is missing .jutut_meta"

    return not jutut_meta['required_text_fields']
