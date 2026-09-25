"""Support some XPath-like syntax for accessing nested structures."""

from __future__ import annotations

import contextlib
import re
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

_SegmentKind = Literal["key", "wildcard_map", "index", "wildcard_seq", "slice"]


class _Segment(NamedTuple):
    """A single classified path segment, computed once per `dget` call instead of
    being re-derived from the raw string on every node visited during traversal.

    `value` holds the dict key (str) for "key", the sequence index (int) for "index",
    or the parsed slice object for "slice"; it is unused (None) for the wildcard kinds.
    """

    kind: _SegmentKind
    value: str | int | slice | None


def _classify_segment(token: str) -> _Segment:
    if token == "*":
        return _Segment("wildcard_map", None)
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1]
        parsed = _parse_index(inner)
        if parsed == "*":
            return _Segment("wildcard_seq", None)
        if isinstance(parsed, int):
            return _Segment("index", parsed)
        # _parse_index() deliberately never recognizes "a:b" - _get_repetition_index()
        # (dset's own path parser) shares it, and dset has no sensible "set one value
        # at a slice" semantic. Slicing is checked separately, only here, so it stays
        # a dget/has/ddelete-only capability rather than leaking into dset.
        parsed_slice = _parse_slice(inner)
        if parsed_slice is not None:
            return _Segment("slice", parsed_slice)
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


def _parse_signed_int(text: str) -> int | None:
    """Parse an optional leading "-" followed by digits into an int, or None if `text`
    isn't in that shape (including the empty string)."""
    is_negative = text.startswith("-")
    digits = text[1:] if is_negative else text
    if digits.isdigit():
        return -int(digits) if is_negative else int(digits)
    return None


def _parse_index(inner: str) -> int | str | None:
    """Parse the content of a "[...]" group into an int index, "*", or None if invalid."""
    if inner == "*":
        return "*"
    return _parse_signed_int(inner)


def _parse_slice(inner: str) -> slice | None:
    """Parse "start:stop" or "start:stop:step" (each component optional, e.g. "1:",
    ":3", "::2", "::-1") into a `slice` object, or None if the shape doesn't fit - more
    than two colons, or a non-empty component that isn't a valid signed integer.
    """
    if ":" not in inner:
        return None
    parts = inner.split(":")
    if len(parts) > 3:
        return None
    components: list[int | None] = []
    for part in parts:
        if part == "":
            components.append(None)
            continue
        value = _parse_signed_int(part)
        if value is None:
            return None
        components.append(value)
    while len(components) < 3:
        components.append(None)
    return slice(*components)


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
            elif kind == "slice":
                # `seg.value` is always a slice here: it's the only way
                # _classify_segment constructs a "slice" segment. `slice.indices()`
                # resolves it to concrete, in-bounds (start, stop, step) for this
                # specific node - handling negative/omitted bounds and reverse steps
                # the same way a plain a_list[a:b:c] would, rather than reimplementing
                # that ourselves. Like a bounded wildcard_seq: every element the slice
                # selects fans out and continues the rest of the path independently.
                if isinstance(cur_node, Sequence):
                    seg_slice = cast(slice, seg.value)
                    for index in range(*seg_slice.indices(len(cur_node))):
                        val = cur_node[index]
                        if next_idx == length:
                            yield val
                        else:
                            next_level.append((val, next_idx))
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
    repetition_flag = any(
        seg.kind in ("wildcard_map", "wildcard_seq", "slice") for seg in tokenized_path
    )
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


def _locate(node: Any, tokenized_path: list[_Segment]) -> Generator[tuple[Any, Any, Any], None, None]:
    """Yield (parent, key_or_index, value) for every value that completely matches
    tokenized_path, in document order.

    A deliberate near-duplicate of `_walk`, not a variant sharing its code: `_walk`
    yields bare values, which is enough for `dget`/`has` and lets those two branches
    iterate directly over `.values()` / a plain `for`. Locating a value's parent+key for
    deletion needs `.items()` / `enumerate()` instead, which costs a tuple per fanned-out
    element - measured at 17-27% slower on wildcard-heavy `dget`/`has` calls when that
    cost was pushed into a unified `_walk`. `dget`/`has` are the hot path; `ddelete` is
    not, so the duplication is the trade made here on purpose, not an oversight.
    """
    length = len(tokenized_path)
    if length == 0:
        yield None, None, node
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
                    for key, value in cur_node.items():
                        if next_idx == length:
                            yield cur_node, key, value
                        else:
                            next_level.append((value, next_idx))
            elif kind == "wildcard_seq":
                if isinstance(cur_node, list):
                    for index, val in enumerate(cur_node):
                        if next_idx == length:
                            yield cur_node, index, val
                        else:
                            next_level.append((val, next_idx))
                elif isinstance(cur_node, Sequence):
                    for index, val in enumerate(cur_node):
                        if next_idx == length:
                            yield cur_node, index, val
                        else:
                            next_level.append((val, next_idx))
            elif kind == "key":
                with contextlib.suppress(KeyError, TypeError):
                    value = cur_node[seg.value]
                    if next_idx == length:
                        yield cur_node, seg.value, value
                    else:
                        next_level.append((value, next_idx))
            elif kind == "index":
                if isinstance(cur_node, Sequence):
                    with contextlib.suppress(IndexError):
                        idx_value = cast(int, seg.value)
                        value = cur_node[idx_value]
                        if next_idx == length:
                            yield cur_node, idx_value, value
                        else:
                            next_level.append((value, next_idx))
            elif kind == "slice":
                # Yielding the concrete, absolute index (not a position within the
                # slice) is what lets ddelete's existing descending-index-sort logic
                # handle a slice delete correctly with no changes of its own - it
                # already sorts and removes any set of int-keyed matches from the same
                # list highest-index-first.
                if isinstance(cur_node, Sequence):
                    seg_slice = cast(slice, seg.value)
                    for index in range(*seg_slice.indices(len(cur_node))):
                        val = cur_node[index]
                        if next_idx == length:
                            yield cur_node, index, val
                        else:
                            next_level.append((val, next_idx))
        current_level = next_level


def ddelete(data: MutableMapping[str, Any], path: str) -> bool:
    """Remove whatever a path matches.

    `data` should be a mapping of str to values, other mappings or sequences
    `path` is a /-separated list of keywords representing the path inside our container

    Returns True if at least one match was removed, False if the path didn't match
    anything (an empty path never removes anything - there's no container to remove the
    root itself from).

    A wildcard path removes every match, consistent with `dget`/`has` treating a
    wildcard as "every element", not just the first. Deleting a list element actually
    removes it and shifts later indices down (like `del a_list[i]`) rather than leaving
    a hole in its place.
    """
    tokenized_path = _tokenize_path(path)
    list_deletions: list[tuple[MutableSequence[Any], int]] = []
    other_deletions: list[tuple[Any, Any]] = []
    for parent, key, _value in _locate(data, tokenized_path):
        if parent is None:
            continue
        if isinstance(key, int) and isinstance(parent, MutableSequence):
            list_deletions.append((parent, key))
        else:
            other_deletions.append((parent, key))

    if not list_deletions and not other_deletions:
        return False

    # A plain `del` can still fail here (e.g. a wildcard fanning into an immutable
    # Sequence like a tuple), and that must not be reported as a successful delete, so
    # this tracks real success rather than suppressing and assuming.
    deleted_any = False
    for parent, key in other_deletions:
        try:
            del parent[key]
            deleted_any = True
        except (KeyError, TypeError):
            pass

    # Highest index first within each list, so removing one match doesn't shift the
    # position of another match still to be removed from that same list. Deletions
    # against different lists don't interact, so a single global sort is enough - it
    # still preserves descending order among entries that do share a list.
    list_deletions.sort(key=lambda item: item[1], reverse=True)
    for parent, index in list_deletions:
        try:
            del parent[index]
            deleted_any = True
        except (IndexError, TypeError):
            pass

    return deleted_any


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


def _search_with_path(
    data: Any,
    path: list[str],
    compiled: re.Pattern[str],
) -> Generator[tuple[str, Any], None, None]:
    if isinstance(data, Mapping):
        for key, value in data.items():
            subpath = [*path, key]
            if compiled.search(key):
                yield "/".join(subpath), value
            yield from _search_with_path(value, subpath, compiled)
    elif isinstance(data, MutableSequence):
        for index, value in enumerate(data):
            if path:
                subpath = path[:]
                subpath[-1] = subpath[-1] + f"[{index}]"
            else:
                subpath = [f"[{index}]"]
            yield from _search_with_path(value, subpath, compiled)


def dsearch(
    data: Mapping[str, Any] | Sequence[Any],
    pattern: str | re.Pattern[str],
) -> Generator[tuple[str, Any], None, None]:
    """Find every key matching `pattern`, at any depth - covers dpath's ``"**/key"`` and
    jsonpath-ng's ``"$..key"`` descendant search, which `dget`'s own wildcards can't do
    since they need the path shape spelled out in advance.

    `data` can be a mapping or a sequence at the top level.
    `pattern` is always treated as a regex via `re.search` (not a plain string equality
    check) - this is a search tool, not a path-matching one like `dget`/`has`. A plain
    key name like "price" still works as a pattern (it matches itself), so this isn't
    any harder to use for the simple case; `re.search` rather than `re.fullmatch` means
    it also matches as a substring unless the caller anchors it (e.g. "^price$").

    Yields (path, value) in document order for every match. `value` is whatever's
    there, not just a leaf - a matched key's value can itself be a nested dict or list.
    Continues searching inside a match too, so a nested key with a matching name is
    also found on its own, not just as part of the outer match's subtree.

    List elements are walked transparently - a match can be found inside a list, and a
    list can appear as a match's value - but a list index is never itself treated as a
    key to search, only dict keys are (matching dpath/jsonpath-ng: they search key
    names, not array positions).
    """
    compiled = re.compile(pattern)
    yield from _search_with_path(data, [], compiled)
