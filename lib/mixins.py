from calendar import timegm
from django.utils.cache import get_conditional_response
from django.utils.decorators import method_decorator
from django.utils.http import http_date, quote_etag
from django.views.decorators.csrf import csrf_exempt


class CSRFExemptMixin:
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class ConditionalMixin:
    def get_etag(self, request):
        """Returns etag string"""
        return None

    def get_last_modified(self, request):
        """Return datetime of last modified"""
        return None

    def get(self, request, *args, **kwargs):
        """Mixin implementation of django.views.decorators.http.condition"""

        # Resolve etag and last_modified
        etag = self.get_etag(request)
        etag = quote_etag(etag) if etag is not None else None
        last_modified = self.get_last_modified(request)
        last_modified = timegm(last_modified.utctimetuple()) if last_modified else None

        # Check request headers
        response = get_conditional_response(request, etag=etag, last_modified=last_modified)
        if response:
            return response

        # If we need get new data, do that
        response = super().get(request, *args, **kwargs)

        # Set relevant headers on the response if they don't already exist.
        if last_modified and not response.has_header('Last-Modified'):
            response['Last-Modified'] = http_date(last_modified)
        if etag and not response.has_header('ETag'):
            response['ETag'] = etag

        return response
