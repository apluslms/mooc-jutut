from django.conf import settings


def show_debug_toolbar(request):
    """Return True if the Django Debug Toolbar should be shown on a given page."""
    return settings.ENABLE_DJANGO_DEBUG_TOOLBAR and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS
