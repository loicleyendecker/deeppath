"""Support some XPath-like syntax for accessing nested structures"""

import re
from typing import (
    Generator,
    List,
    Mapping,
    MutableSequence,
    Sequence,
    Iterable,
    Any,
    Union,
    Optional,
    Tuple,
    Dict,
)

_REPETITION_REGEX = re.compile(r"([\w\*]+)\[([\d-]+)\]")

JsonData = Dict[str, Any]


def flatten(nested_iterable: Iterable[Any]) -> List[Any]:
    """Flattens a nested list.
    E.g [[[[[1]]]],[2]] -> [1,2]
    """
    flattened_list = []
    for item in nested_iterable:
        if isinstance(item, list):
            flattened_list.extend(flatten(item))
        else:
            flattened_list.append(item)
    return flattened_list


def _get_repetition_index(key: str) -> Optional[Tuple[str, int]]:
    """Try to match a path for a repetition.
    This will return the key and the repetition index or None if the key
    does not match the expected regex"""
    match = _REPETITION_REGEX.search(key)
    if match:
        key = match.group(1)
        repetition_number = match.group(2)
        return key, int(repetition_number)

    return None


def _flatdget(data: Union[Sequence[Any], JsonData, str], key: Union[int, str]) -> Any:
    if isinstance(data, Sequence) and isinstance(key, int):
        return data[key]
    if isinstance(data, Dict) and isinstance(key, str):
        return data[key]
    return [_flatdget(value, key) for value in data]


def dget(input_dict: JsonData, path: str, default: Any = None) -> Any:
    """Gets a deeply nested value in a dictionary.
    Returns default if provided when any key doesn't match.
    """
    path = path.strip("/")
    data: Union[List[Any], JsonData] = input_dict
    try:
        for key in path.split("/"):
            repetition = _get_repetition_index(key)
            if repetition:
                key, index = repetition
                if key != "*":
                    data = _flatdget(data, key)
                    data = _flatdget(data, index)
                elif isinstance(data, Dict):
                    data = [_flatdget(value, index) for value in data.values()]
            else:
                if key != "*":
                    data = _flatdget(data, key)
                elif not isinstance(data, Sequence):
                    data = list(data.values())
    except (KeyError, TypeError, IndexError):
        return default
    return data


def dset(
    data: JsonData,
    path: str,
    value: Any,
) -> None:
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


def _dwalk_with_path(
    data: JsonData, path: List[str]
) -> Generator[Tuple[str, JsonData], None, None]:
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


def dwalk(data: Dict[str, Any]) -> Generator[Tuple[str, JsonData], None, None]:
    """Generator that will yield values for each path to a leaf of a nested structure"""
    yield from _dwalk_with_path(data, [])
