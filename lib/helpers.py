import functools
import warnings
from collections import OrderedDict
from django.utils.crypto import get_random_string as django_get_random_string
from django.utils.deprecation import RemovedInNextVersionWarning


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


class Enum(object):
    """
    Represents constant enumeration.

    Usage:
        OPTS = Enum(
            ('FOO', 1, 'help string for foo'),
            ('BAR', 2, 'help string for bar'),
        )

        if OPTS.FOO == test_var:
            return OPTS[test_var]

        ChoicesField(choices=OPTS.choices)
    """
    def __init__(self, *choices):
        if len(choices) == 1 and isinstance(choices[0], list):
            choices = choices[0]
        self._strings = OrderedDict()
        self._keys = []
        for name, value, string in choices:
            assert value not in self._strings, "Multiple choices have same value"
            self._strings[value] = string
            self._keys.append(name)
            setattr(self, name, value)

    @property
    def choices(self):
        return tuple(sorted(self._strings.items()))

    def keys(self):
        return (x for x in self._keys)

    def __getitem__(self, key):
        return self._strings[key]

    def __str__(self):
        s = ["<%s([" % (self.__class__.__name__,)]
        for key in self.keys():
            val = getattr(self, key)
            txt = self[val]
            s.append("  (%s, %s, %s)," % (key, val, txt))
        s.append("])>")
        return '\n'.join(s)
