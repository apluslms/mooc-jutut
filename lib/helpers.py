from django.utils.crypto import get_random_string as django_get_random_string
from django.utils.deprecation import RemovedInNextVersionWarning
import functools
import warnings


try:
    from django.core.management.utils import get_random_secret_key
except ImportError:
    def get_random_secret_key():
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        return django_get_random_string(50, chars)


def deprecated(message):
    '''
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    '''
    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            warnings.warn(message, category=RemovedInNextVersionWarning, stacklevel=2)
            return func(*args, **kwargs)
        return new_func
    return wrapper


def create_secret_key_file(filename):
    key = get_random_secret_key()
    with open(filename, 'w') as f:
        f.write('''"""
Automatically generated SECRET_KEY for django.
This needs to be unique and SECRET. It is also installation specific.
You can change it here or in local_settings.py
"""
SECRET_KEY = '%s'
''' % (key))
