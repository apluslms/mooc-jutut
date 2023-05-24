from django.conf import settings


def show_debug_toolbar(request):
    """Return True if the Django Debug Toolbar should be shown on a given page."""
    return settings.ENABLE_DJANGO_DEBUG_TOOLBAR and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS


def is_ajax(request):
    """Detect AJAX requests.
    Request object method is_ajax() was removed in Django 4.0, this can be used instead.
    """
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'
