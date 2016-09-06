from hashlib import sha1
from collections import Iterable


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
