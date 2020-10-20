"""
Support some XPath-like syntax for accessing nested structures
"""

from typing import Sequence, MutableSequence, Mapping
import re


def _flatdget(data, key):
    if not isinstance(data, Sequence) or isinstance(key, int):
        return data[key]
    return [_flatdget(value, key) for value in data]


_REPETITION_REGEX = re.compile(r"([\w\*]+)\[([\d-]+)\]")


def _get_repetition_index(key):
    """Try to match a path for a repetition.
    This will return the key and the repetition index or None if the key
    does not match the expected regex"""
    match = _REPETITION_REGEX.search(key)
    if match:
        key = match.group(1)
        repetition_number = match.group(2)
        return key, int(repetition_number)


def dget(data, path, default=None):
    """
    Gets a deeply nested value in a dictionary.
    Returns default if provided when any key doesn't match.
    """
    if path.startswith("/"):
        path = path[1:]
    try:
        for key in path.split("/"):
            repetition = _get_repetition_index(key)
            if repetition:
                key, index = repetition
                if key != "*":
                    data = _flatdget(data, key)
                    data = _flatdget(data, index)
                else:
                    data = [_flatdget(value, index) for value in data.values()]
            else:
                if key != "*":
                    data = _flatdget(data, key)
                else:
                    if not isinstance(data, Sequence):
                        data = [value for value in data.values()]
    except (KeyError, TypeError, IndexError):
        return default
    return data


def dset(data, path, value):
    """Set a key in a deeply nested structure"""
    if path.startswith("/"):
        path = path[1:]
    for key in path.split("/")[:-1]:
        subpath = _get_repetition_index(key)
        if not subpath:
            if key not in data:
                data[key] = {}
            data = data[key]
        else:
            key, index = subpath
            if key not in data:
                data[key] = [{}]
            elif len(data[key]) == index:
                data[key].append({})
            data = data[key][index]

    last = _get_repetition_index(path.split("/")[-1])
    if not last:
        data[path.split("/")[-1]] = value
    else:
        key, index = last
        if key not in data:
            data[key] = [value]
        else:
            if len(data[key]) == index:
                data[key].append(value)
            else:
                data[key][index] = value


def _dwalk_with_path(data, path):
    if isinstance(data, Mapping):
        for key, value in data.items():
            subpath = path + [key]
            yield from _dwalk_with_path(value, subpath)
    elif isinstance(data, MutableSequence):
        for index, value in enumerate(data):
            subpath = path[:]
            subpath[-1] = subpath[-1] + f"[{index}]"
            yield from _dwalk_with_path(value, subpath)
    else:
        yield "/".join(path), data


def dwalk(data):
    """Generator that will yield values for each path to a leaf of a nested structure"""
    yield from _dwalk_with_path(data, [])
