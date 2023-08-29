from django.conf import settings
from django.utils.translation import get_language


def show_debug_toolbar(request):
    """Return True if the Django Debug Toolbar should be shown on a given page."""
    return settings.ENABLE_DJANGO_DEBUG_TOOLBAR and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS


def is_ajax(request):
    """Detect AJAX requests.
    Request object method is_ajax() was removed in Django 4.0, this can be used instead.
    """
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def str_in_selected_language(string):
    """If a string includes alternate translations wrapped with |-characters,
    return a version of the string with only the text in the language the page
    is in.
    If the language alternatives don't include the selected language, return
    the first alternative.
    """
    if string.count('|') < 2:
        # string doesn't include alternate translations
        return string
    parts = string.split('|')
    lang_alts = dict(map(
        lambda s: s.split(':'), # language key, text
        parts[1:-1] # only use parts between the | chars
    ))
    cur_lang = get_language()
    if cur_lang in lang_alts:
        content = lang_alts[cur_lang]
    else: # default to first value
        content = list(lang_alts.values())[0]
    return parts[0] + content + parts[-1]
