"""Support some XPath-like syntax for accessing nested structures"""

import contextlib
import re
from typing import (
    Generator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
    Iterable,
    Any,
    Union,
    Optional,
    Tuple,
    Dict,
)

_REPETITION_REGEX = re.compile(r"([\w\*]*)\[([\d\-\*]+)\]")
TOKENIZER_REGEX = re.compile(r"(\[[^\]]+\]|[^/\[\]]+)")


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


def _get_repetition_index(key: str) -> Optional[Tuple[str, Union[int, str]]]:
    """Try to match a path for a repetition.
    This will return the key and the repetition index or None if the key
    does not match the expected regex"""
    match = _REPETITION_REGEX.search(key)
    if match:
        key = match.group(1)
        repetition_number = match.group(2)
        if repetition_number == "*":
            return key, repetition_number
        return key, int(repetition_number)

    return None


def _get_sequence_index(path: str) -> Tuple[bool, Union[None, int, str]]:
    """
    Checks if a given path is for a repetition and returns the index if applicable
    and a boolean indicating if it was indeed a repetition.

    There are essentially three possible cases:
    * the path is a repetition path (i.e. "key[1]", "key[-3]", or "key[*]")
    * the path is a wildcard ("*")
    * the path is not a repetition path at all

    We need to treat the pure wildcard specifically because we still need to know
    that this needs to be handled "as a repetition" in the sense that multiple sub-paths
    need to be searched.
    """
    match = re.match(r"\[(-?[\d\*]+)\]", path)
    if match:
        index = match.group(1)
        index_is_numberic = index.isnumeric() or index[0] == "-" and index[1:].isnumeric()
        return True, (int(index) if index_is_numberic else index)
    return False, ("*" if path == "*" else None)


def dget(
    data: Mapping[str, Any], path: str, default: Optional[Any] = None
) -> Union[List[Any], Any]:
    """
    Match a path in a deep container.

    `data` should be a mapping of str to values, other mappings or sequences
    `path` is a /-separated list of keywords representing the path inside our container
    `default` will be returned if the path does not match and is not using any wildcards

    This function will return a single value if no wildcard (*) is used in the path. If
    a wildcard is used, it will return a list of matching elements (so possibly an empty
    list).
    """
    repetition_flag = False
    tokenized_path = TOKENIZER_REGEX.findall(path)
    nodes = [(data, tokenized_path)]
    output = []
    while nodes:
        node, remainder = nodes.pop(0)
        if not remainder:
            output.append(node)
            continue
        next_path, *remainder = remainder
        if not next_path:
            continue

        sequence, index = _get_sequence_index(next_path)
        if index == "*":
            repetition_flag = True
            if not sequence and isinstance(node, Mapping):
                nodes.extend((value, remainder) for value in node.values())
            elif sequence and isinstance(node, Sequence):
                nodes.extend((val, remainder) for val in node)
        else:
            if index is None:
                if isinstance(node, Mapping):
                    with contextlib.suppress(KeyError):
                        nodes.append((node[next_path], remainder))
            elif isinstance(index, int) and isinstance(node, Sequence):
                with contextlib.suppress(IndexError):
                    nodes.append((node[index], remainder))

    # If there was an explicit repetition in the path (a "*"), then we return a
    # list, otherwise, we return a single element
    if repetition_flag:
        return output
    if output:
        return output[0]
    return default


def dset(
    data: MutableMapping[str, Any],
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
    data: Mapping[str, Any], path: List[str]
) -> Generator[Tuple[str, Mapping[str, Any]], None, None]:
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


def dwalk(data: Dict[str, Any]) -> Generator[Tuple[str, Mapping[str, Any]], None, None]:
    """Generator that will yield values for each path to a leaf of a nested structure"""
    yield from _dwalk_with_path(data, [])
