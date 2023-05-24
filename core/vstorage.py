from os.path import join, getatime, getctime, getmtime
from datetime import datetime
from io import StringIO

from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.core.files.storage import Storage
from django.contrib.staticfiles.finders import BaseFinder
from django.template.loader import get_template
from django.contrib.staticfiles.utils import get_files


if DJANGO_VERSION >= (1, 10):
    def datetime_from_timestamp(ts):
        # src: django.core.files.storage.FileSystemStorage._datetime_from_timestamp
        if settings.USE_TZ:
            return datetime.utcfromtimestamp(ts).replace(tzinfo=datetime.timezone.utc)
        return datetime.fromtimestamp(ts)
else:
    datetime_from_timestamp = datetime.fromtimestamp


class VirtualStorage(Storage):
    def __init__(self):
        map_ = settings.RENDERED_STATIC_FILES
        # RODO: raise configuration error
        if isinstance(map_, dict):
            map_ = map_.items()
        self._map = {k: (v[0] if isinstance(v, (list, tuple)) else v) for k, v in map_}
        self._default_context = settings.RENDERED_CONTEXT if hasattr(settings, 'RENDERED_CONTEXT') else {}
        self._contexts = {k: v[1] for k, v in map_ if isinstance(v, (list, tuple))}
        self._templates = {}
        self._cache = {}

    def _get_context(self, name):
        context = self._default_context.copy()
        if name in self._contexts:
            context.update(self._contexts[name])
        return context

    def _get_template(self, name):
        template = self._templates.get(name)
        if template is None:
            template_name = self._map[name]
            template = get_template(template_name)
            self._templates[name] = template
        return template

    def _get_template_file(self, name):
        return self._get_template(name).origin.name

    def _get(self, name):
        rendered = self._cache.get(name)
        if rendered is None:
            template = self._get_template(name)
            rendered = template.render(self._get_context(name))
            self._cache[name] = rendered
        return rendered

    # Public api or privates for super implementations of public api

    def _open(self, name, mode): # pylint: disable=unused-argument
        return StringIO(self._get(name))

    def _save(self, name, content):
        raise NotImplementedError("VirtualStorage is read only")

    def path(self, name):
        path = self._get_template_file(name)
        return "{} (will be rendered as {})".format(path, name)

    def delete(self, name):
        raise NotImplementedError("VirtualStorage is read only")

    def exists(self, name):
        return name in self._map

    def listdir(self, path):
        if path and path[-1] != '/':
            path += '/'
        prefix_len = len(path)
        all_ = [p[prefix_len:] for p in self._map.keys() if p.startswith(path)]
        dirs = [p.split('/', 1)[0] for p in all_ if '/' in p]
        files = [p for p in all_ if '/' not in p]
        return (dirs, files)

    def size(self, name):
        return len(self._get(name).encode('utf-8'))

    def url(self, name):
        raise NotImplementedError('subclasses of Storage must provide a url() method')

    def get_accessed_time(self, name):
        return datetime_from_timestamp(getatime(self._get_template_file(name)))

    def get_created_time(self, name):
        return datetime_from_timestamp(getctime(self._get_template_file(name)))

    def get_modified_time(self, name):
        return datetime_from_timestamp(getmtime(self._get_template_file(name)))

    # Django 1.9 support
    accessed_time = get_accessed_time
    created_time = get_created_time
    modified_time = get_modified_time


class VirtualFinder(BaseFinder):
    def __init__(self):
        self._storage = VirtualStorage()

    def find(self, path, all=False): # pylint: disable=redefined-builtin
        if self._storage.exists(path):
            abs_path = join(settings.STATIC_ROOT, path)
            return {abs_path} if all else abs_path
        return []

    def list(self, ignore_patterns):
        storage = self._storage
        for path in get_files(storage, ignore_patterns):
            yield path, storage
