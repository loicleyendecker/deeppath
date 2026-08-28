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
    length = len(tokenized_path)
    current_level: list[tuple[Any, int]] = [(data, 0)]
    output = []
    while current_level:
        next_level: list[tuple[Any, int]] = []
        for node, idx in current_level:
            if idx == length:
                output.append(node)
                continue
            seg = tokenized_path[idx]
            kind = seg.kind
            if kind == "wildcard_map":
                # No isinstance check: .values() is a reliable enough signal for
                # "mapping-like" on its own (no common non-mapping type has it), and
                # duck-typing it accepts Mapping-like objects that don't register with
                # the ABC, matching Mapping and dict both through the same code path.
                with contextlib.suppress(AttributeError):
                    for value in node.values():
                        next_level.append((value, idx + 1))
            elif kind == "wildcard_seq":
                # Kept as isinstance: unlike .values(), plain iteration doesn't
                # distinguish "sequence" from "any iterable" - a bare `for val in node`
                # would silently iterate a dict's *keys* here instead of correctly not
                # matching at all.
                if isinstance(node, list):
                    for val in node:
                        next_level.append((val, idx + 1))
                elif isinstance(node, Sequence):
                    for val in node:
                        next_level.append((val, idx + 1))
            elif kind == "key":
                # No isinstance check: every non-mapping raises TypeError (not
                # KeyError) when subscripted with a string key, so the exception
                # itself distinguishes "not mapping-like" from "key not present".
                with contextlib.suppress(KeyError, TypeError):
                    next_level.append((node[seg.value], idx + 1))
            elif kind == "index":
                # `seg.value` is always an int here: it's the only way _classify_segment
                # constructs an "index" segment. cast(), not isinstance(), tells mypy
                # that without re-checking something already guaranteed at no cost.
                #
                # isinstance(node, Sequence) is still a real check, though: a dict with
                # an integer key (e.g. {3: "x"}) accepts int subscripting without
                # raising, so dropping this would let a dict silently match a
                # "[3]"-style path segment.
                if isinstance(node, Sequence):
                    with contextlib.suppress(IndexError):
                        next_level.append((node[cast(int, seg.value)], idx + 1))
        current_level = next_level

    # If there was an explicit repetition in the path (a "*"), then we return a
    # list, otherwise, we return a single element
    if repetition_flag:
        return output
    if output:
        return output[0]
    if strict:
        raise KeyError(f"Path {path!r} did not match the given structure")
    return default


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
