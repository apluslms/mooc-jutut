from django.conf import settings


def show_debug_toolbar(request):
    """Return True if the Django Debug Toolbar should be shown on a given page."""
    return settings.ENABLE_DJANGO_DEBUG_TOOLBAR and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS


def is_ajax(request):
    """Detect AJAX requests.
    Request object method is_ajax() was removed in Django 4.0, this can be used instead.
    """
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def pick_localized(entry, lang):
    """
    Picks the selected language's value from
    |lang:value|lang:value| -format text.
    """
    # Note: This method is a direct copy from the a-plus repo.
    # In future we may want to consider a "a-plus-common" submodule for common utility functions
    text = entry if isinstance(entry, str) else str(entry)
    variants = text.split('|')
    if len(variants) > 2:
        prefix = variants[0]
        suffix = variants[-1]
        variants = variants[1:-1]
        for variant in variants:
            if variant.startswith(lang + ":"):
                return prefix + variant[(len(lang)+1):] + suffix
        for variant in variants:
            if ':' in variant:
                return prefix + variant.split(':', 1)[1] + suffix
    return text
