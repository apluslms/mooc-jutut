import logging
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlencode, urlparse

from django.conf import settings
from django.urls import reverse
from django.template.loader import get_template
from django.utils import translation
from django.utils.safestring import mark_safe

from aplus_client.client import AplusGraderClient


# HTML tags allowed in teacher response messages (inserted by styling buttons)
_ALLOWED_RESPONSE_TAGS = frozenset(['b', 'i', 'u', 'strong', 'em', 'code', 'a', 'br'])
# Allowed attributes per tag; only 'href' and 'title' on <a>
_ALLOWED_RESPONSE_ATTRS = {
    'a': frozenset(['href', 'title']),
}
# URL schemes permitted in href values
_SAFE_URL_SCHEMES = frozenset(['http', 'https', 'mailto'])


class _ResponseMessageSanitizer(HTMLParser):
    """HTML parser that passes through a whitelist of tags/attributes and
    HTML-escapes everything else, so that text like ``<foo>`` is rendered
    literally rather than silently disappearing in the browser."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._output = []

    def handle_starttag(self, tag, attrs):
        if tag in _ALLOWED_RESPONSE_TAGS:
            allowed_attr_names = _ALLOWED_RESPONSE_ATTRS.get(tag, frozenset())
            safe_attrs = []
            for name, value in attrs:
                if name not in allowed_attr_names:
                    continue
                if value is None:
                    safe_attrs.append(html_escape(name))
                    continue
                if name == 'href':
                    scheme = urlparse(value).scheme.lower()
                    if scheme and scheme not in _SAFE_URL_SCHEMES:
                        continue
                safe_attrs.append('{}="{}"'.format(html_escape(name), html_escape(value)))
            attr_str = (' ' + ' '.join(safe_attrs)) if safe_attrs else ''
            self._output.append('<{}{}>'.format(tag, attr_str))
        else:
            attrs_str = ''
            for name, value in attrs:
                if value is None:
                    attrs_str += ' {}'.format(name)
                else:
                    attrs_str += ' {}="{}"'.format(name, value)
            self._output.append(html_escape('<{}{}>'.format(tag, attrs_str)))

    def handle_endtag(self, tag):
        if tag in _ALLOWED_RESPONSE_TAGS:
            self._output.append('</{}>'.format(tag))
        else:
            self._output.append(html_escape('</{}>'.format(tag)))

    def handle_data(self, data):
        self._output.append(html_escape(data))

    def handle_entityref(self, name):
        self._output.append('&{};'.format(name))

    def handle_charref(self, name):
        self._output.append('&#{};'.format(name))

    def get_output(self):
        return ''.join(self._output)


def sanitize_response_message(message):
    """Sanitize an HTML teacher response message.

    Allows a small whitelist of safe formatting tags (``<b>``, ``<i>``,
    ``<u>``, ``<strong>``, ``<em>``, ``<code>``, ``<a>``, ``<br>``) and
    HTML-escapes everything else so that text like ``<foo>`` is displayed
    as the literal characters ``<foo>`` instead of vanishing.

    Returns a :class:`~django.utils.safestring.SafeString` ready for
    insertion into a template without further escaping.
    """
    if not message:
        return mark_safe('')
    parser = _ResponseMessageSanitizer()
    parser.feed(message)
    return mark_safe(parser.get_output())


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
        'max_points': feedback.max_grade,
        'feedback': html,
        'grading_payload': '{}'
    }
    if feedback.response_notify:
        update_data['notify'] = feedback.response_notify_aplus
        update_data['regrade_when_notification_seen'] = True

    r = client.grade(update_data, timeout=(6.4, 46))
    feedback.response_uploaded = r.status_code
    log_method = logger.debug if r.status_code == 200 else logger.critical
    log_method(
        "Update of feedback %d to submission_url '%s' returned with %d: '%s'",
        feedback.id, submission_url, r.status_code, r.text
    )
    return (r.status_code == 200, r.status_code, r.text)


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
