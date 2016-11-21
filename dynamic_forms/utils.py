from hashlib import sha1
from collections import Iterable
from itertools import chain as iterchain


def freeze(data):
    if isinstance(data, dict):
        return tuple(((k, freeze(v)) for k, v in sorted(data.items())))
    elif isinstance(data, list):
        return tuple((freeze(v) for v in data))
    return data


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
    else:
        return [c for c in cleaned if c and c not in ignore]
