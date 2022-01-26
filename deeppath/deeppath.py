"""Support some XPath-like syntax for accessing nested structures"""

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
        if repetition_number != "*":
            return key, int(repetition_number)
        return key, repetition_number

    return None


def _get_sequence_index(path: str) -> Tuple[bool, Union[None, int, str]]:
    match = re.match(r"\[(-?[\d\*]+)\]", path)
    if match:
        index = match.group(1)
        if index.isnumeric() or index[0] == "-" and index[1:].isnumeric():
            return True, int(index)
        else:
            return True, index
    if path == "*":
        return False, "*"
    return False, None


def dget(
    data: Dict[str, Any], path: str, default: Optional[Any] = None
) -> Union[List[Any], Any]:
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
                for value in node.values():
                    nodes.append((value, remainder))
            elif sequence and isinstance(node, Sequence):
                nodes.extend((val, remainder) for val in node)
        else:
            if index is None:
                try:
                    nodes.append((node[next_path], remainder))
                except (KeyError, TypeError):
                    pass
            elif isinstance(index, int) and isinstance(node, Sequence):
                try:
                    nodes.append((node[index], remainder))
                except IndexError:
                    pass

    # If there was an explicit repetition in the path (a "*"), then we return a
    # list, otherwise, we return a single element
    if repetition_flag:
        return output
    elif output:
        return output[0]
    else:
        return default


def dset(
    data: MutableMapping,
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
    data: Mapping, path: List[str]
) -> Generator[Tuple[str, Mapping], None, None]:
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


def dwalk(data: Dict[str, Any]) -> Generator[Tuple[str, Mapping], None, None]:
    """Generator that will yield values for each path to a leaf of a nested structure"""
    yield from _dwalk_with_path(data, [])
