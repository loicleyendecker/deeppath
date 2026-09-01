"""Support some XPath-like syntax for accessing nested structures."""

from __future__ import annotations

import contextlib
from typing import (
    Any,
    Generator,
    Iterable,
    Literal,
    Mapping,
    MutableMapping,
    MutableSequence,
    NamedTuple,
    Sequence,
    cast,
)

_SegmentKind = Literal["key", "wildcard_map", "index", "wildcard_seq"]


class _Segment(NamedTuple):
    """A single classified path segment, computed once per `dget` call instead of
    being re-derived from the raw string on every node visited during traversal.

    `value` holds the dict key (str) for "key", or the sequence index (int) for
    "index"; it is unused (None) for the wildcard kinds.
    """

    kind: _SegmentKind
    value: str | int | None


def _classify_segment(token: str) -> _Segment:
    if token == "*":
        return _Segment("wildcard_map", None)
    if token.startswith("[") and token.endswith("]"):
        parsed = _parse_index(token[1:-1])
        if parsed == "*":
            return _Segment("wildcard_seq", None)
        if isinstance(parsed, int):
            return _Segment("index", parsed)
        # An unparseable "[...]" (e.g. "[abc]") is used verbatim as a literal key,
        # matching the historical behavior of the string-based matcher.
    return _Segment("key", token)


def _tokenize_path(path: str) -> list[_Segment]:
    """Split a path into its classified segments.

    Segments are separated by "/", except that a "[...]" group is always kept as
    a single, atomic token (so "key[0]" tokenizes to "key" and "[0]" separately).
    """
    tokens = []
    current = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == "/":
            if current:
                tokens.append(current)
                current = ""
        elif char == "[":
            if current:
                tokens.append(current)
                current = ""
            end = path.find("]", index)
            if end == -1:
                raise ValueError(f"Unterminated '[' in path {path!r}")
            tokens.append(path[index : end + 1])
            index = end
        else:
            current += char
        index += 1
    if current:
        tokens.append(current)
    return [_classify_segment(token) for token in tokens]


def flatten(nested_iterable: Iterable[Any]) -> list[Any]:
    """Flattens a nested list.

    E.g [[[[[1]]]],[2]] -> [1,2].
    """
    flattened_list = []
    for item in nested_iterable:
        if isinstance(item, list):
            flattened_list.extend(flatten(item))
        else:
            flattened_list.append(item)
    return flattened_list


def _parse_index(inner: str) -> int | str | None:
    """Parse the content of a "[...]" group into an int index, "*", or None if invalid."""
    if inner == "*":
        return "*"
    is_negative = inner.startswith("-")
    digits = inner[1:] if is_negative else inner
    if digits.isdigit():
        return -int(digits) if is_negative else int(digits)
    return None


def _get_repetition_index(key: str) -> tuple[str, int | str] | None:
    """Try to match a path for a repetition.

    This will return the key and the repetition index or None if the key
    does not contain a valid "[...]" repetition suffix.
    """
    start = key.find("[")
    if start == -1:
        return None
    end = key.find("]", start)
    if end == -1:
        return None
    index = _parse_index(key[start + 1 : end])
    if index is None:
        return None
    return key[:start], index


def _walk(node: Any, tokenized_path: list[_Segment]) -> Generator[Any, None, None]:
    """Yield every value that completely matches tokenized_path, in document order.

    Shared traversal core for `dget` and `has`: `dget` collects every yielded value into
    a list, `has` just asks for one and stops, which is what gives `has` its short
    circuit - once its `for _ in _walk(...): return True` stops pulling, the generator
    suspends and never builds the rest of a fan-out.
    """
    length = len(tokenized_path)
    if length == 0:
        yield node
        return
    current_level: list[tuple[Any, int]] = [(node, 0)]
    while current_level:
        next_level: list[tuple[Any, int]] = []
        for cur_node, cur_idx in current_level:
            seg = tokenized_path[cur_idx]
            kind = seg.kind
            next_idx = cur_idx + 1
            if kind == "wildcard_map":
                with contextlib.suppress(AttributeError):
                    for value in cur_node.values():
                        if next_idx == length:
                            yield value
                        else:
                            next_level.append((value, next_idx))
            elif kind == "wildcard_seq":
                if isinstance(cur_node, list):
                    for val in cur_node:
                        if next_idx == length:
                            yield val
                        else:
                            next_level.append((val, next_idx))
                elif isinstance(cur_node, Sequence):
                    for val in cur_node:
                        if next_idx == length:
                            yield val
                        else:
                            next_level.append((val, next_idx))
            elif kind == "key":
                with contextlib.suppress(KeyError, TypeError):
                    value = cur_node[seg.value]
                    if next_idx == length:
                        yield value
                    else:
                        next_level.append((value, next_idx))
            elif kind == "index":
                if isinstance(cur_node, Sequence):
                    with contextlib.suppress(IndexError):
                        value = cur_node[cast(int, seg.value)]
                        if next_idx == length:
                            yield value
                        else:
                            next_level.append((value, next_idx))
        current_level = next_level


def dget(
    data: Mapping[str, Any],
    path: str,
    default: Any | None = None,
    strict: bool = False,
) -> list[Any] | Any:
    """Match a path in a deep container.

    `data` should be a mapping of str to values, other mappings or sequences
    `path` is a /-separated list of keywords representing the path inside our container
    `default` will be returned if the path does not match and is not using any wildcards
    `strict`, if set, raises a `KeyError` instead of returning `default` when the path
    does not match. This only applies to non-wildcard paths, since a wildcard path
    naturally matches zero or more elements.

    This function will return a single value if no wildcard (*) is used in the path. If
    a wildcard is used, it will return a list of matching elements (so possibly an empty
    list).
    """
    tokenized_path = _tokenize_path(path)
    # A wildcard makes this a repetition path even if a missing key earlier in the
    # path means the wildcard segment itself is never reached during traversal.
    repetition_flag = any(seg.kind in ("wildcard_map", "wildcard_seq") for seg in tokenized_path)
    output = list(_walk(data, tokenized_path))

    # If there was an explicit repetition in the path (a "*"), then we return a
    # list, otherwise, we return a single element
    if repetition_flag:
        return output
    if output:
        return output[0]
    if strict:
        raise KeyError(f"Path {path!r} did not match the given structure")
    return default


def has(data: Mapping[str, Any], path: str) -> bool:
    """Check whether a path matches anything in a deep container.

    `data` should be a mapping of str to values, other mappings or sequences
    `path` is a /-separated list of keywords representing the path inside our container

    Returns True as soon as the path resolves to at least one value, even if that value
    is falsy (e.g. None, 0, or an empty list) - this checks whether the path *matches*,
    not whether the matched value is truthy. For a wildcard path, True means at least one
    element matched.

    Shares its traversal with `dget` via `_walk`; the short circuit falls out of
    generator laziness - once this stops pulling after the first yield, `_walk` never
    builds the rest of a fan-out.
    """
    tokenized_path = _tokenize_path(path)
    for _ in _walk(data, tokenized_path):
        return True
    return False


def dset(
    data: MutableMapping[str, Any],
    path: str,
    value: Any,
) -> None:
    """Set a key in a deeply nested structure."""
    if path.startswith("/"):
        path = path[1:]
    for key in path.split("/")[:-1]:
        subpath = _get_repetition_index(key)
        if not subpath:
            if key not in data:
                data[key] = {}
            data = data[key]
        else:
            subkey, index = subpath
            if subkey not in data:
                data[subkey] = [{}]
            elif len(data[subkey]) == index:
                data[subkey].append({})
            data = data[subkey][index]

    last = _get_repetition_index(path.split("/")[-1])
    if not last:
        data[path.split("/")[-1]] = value
    else:
        key, index = last
        if key not in data:
            data[key] = [value]
        elif len(data[key]) == index:
            data[key].append(value)
        else:
            data[key][index] = value


def _dwalk_with_path(
    data: Any,
    path: list[str],
) -> Generator[tuple[str, Any], None, None]:
    if isinstance(data, Mapping):
        for key, value in data.items():
            subpath = [*path, key]
            yield from _dwalk_with_path(value, subpath)
    elif isinstance(data, MutableSequence):
        for index, value in enumerate(data):
            if path:
                subpath = path[:]
                subpath[-1] = subpath[-1] + f"[{index}]"
            else:
                subpath = [f"[{index}]"]
            yield from _dwalk_with_path(value, subpath)
    else:
        yield "/".join(path), data


def dwalk(data: Mapping[str, Any] | Sequence[Any]) -> Generator[tuple[str, Any], None, None]:
    """Yield values for each path to a leaf of a nested structure.

    `data` can be a mapping or a sequence at the top level.
    """
    yield from _dwalk_with_path(data, [])
