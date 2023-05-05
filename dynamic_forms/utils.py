from hashlib import sha1
from collections.abc import Iterable
from itertools import chain as iterchain
from operator import itemgetter
from django.utils import translation
from django.utils.functional import lazy


def bytefy(data):
    def encode(x):
        if isinstance(x, bytes):
            return x
        return str(x).encode('utf-8')
    if isinstance(data, dict):
        keys = [(str(k), k, v) for k, v in data.items()]
        keys.sort(key=itemgetter(0))
        return b'{' + b','.join(encode(k) + b':' + bytefy(v) for _, k, v in keys) + b'}'
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return b'[' + b','.join(bytefy(v) for v in data) + b']'
    return encode(data)


def freeze(data):
    if isinstance(data, dict):
        return tuple(((k, freeze(v)) for k, v in sorted(data.items())))
    if isinstance(data, list):
        return tuple((freeze(v) for v in data))
    return data


def freeze_digest(frozen_spec, frozen_i18n):
    sha = sha1(frozen_spec)
    if frozen_i18n:
        sha.update(frozen_i18n)
    return sha.hexdigest()


def hashsum(data, hash_func=None):
    if not hash_func:
        hash_func = sha1()

    def recurse(data):
        if isinstance(data, dict):
            data = sorted(data.items())
        if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
            for v in data:
                recurse(v)
        else:
            hash_func.update(str(data).encode('utf-8'))
    recurse(data)
    return hash_func


def cleaned_css_classes(css_classes, ignore=None):
    cleaned = (
        c.strip() for c in
        iterchain.from_iterable(x.split(' ') for x in css_classes.split(','))
    )
    if not ignore:
        return [c for c in cleaned if c]
    return [c for c in cleaned if c and c not in ignore]


def _translate_lazy(input, dictionary): # pylint: disable=redefined-builtin
    if dictionary:
        lang = translation.get_language()
        return dictionary.get(input, {}).get(lang) or input
    return input


translate_lazy = lazy(_translate_lazy, str)
