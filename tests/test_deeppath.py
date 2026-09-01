"""Validate the dget function that accesses values in nested dictionaries, using the xpath syntax"""

import datetime
from dataclasses import dataclass
from typing import List

import pytest

from deeppath import ddelete, dget, dset, dwalk, flatten, has


@dataclass(frozen=True)
class Person:
    name: str
    age: int
    birthday: datetime.datetime

    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Read from `data` and initialise a new `Person` object
        """
        name = dget(data, "deeply/nested/name")
        age = int(dget(data, "somewhere/else/age"))
        birthday = datetime.date(*dget(data, "other/location/birthday/*"))
        return cls(name, age, birthday, **kwargs)


@dataclass(frozen=True)
class InterestedPerson(Person):
    """A normal person with a list of hobbies"""

    hobbies: List[str]

    @classmethod
    def from_dict(cls, data, **kwargs):
        hobbies = dget(data, "list/of/hobbies[*]/title")
        additional_args = {**kwargs, "hobbies": hobbies}
        return super().from_dict(data, **additional_args)


def test_dget_basic():
    """Basic test, with and without default value"""
    data = {"deeply": {"nested": {"path": 2}}}
    assert dget(data, "deeply/nested/path") == 2
    assert not dget(data, "some/wrong/path")
    assert not dget(data, "deeply/nested/path/toomuch")

    assert dget(data, "deeply/nested/path", default=1) == 2
    assert dget(data, "/deeply/nested/path", default=1) == 2
    assert dget(data, "some/wrong/path", default=1) == 1
    assert dget(data, "deeply/nested/path/toomuch", default=1) == 1


def test_dget_strict():
    """Check that strict mode raises instead of returning the default"""
    data = {"deeply": {"nested": {"path": 2}}}
    assert dget(data, "deeply/nested/path", strict=True) == 2

    with pytest.raises(KeyError):
        dget(data, "some/wrong/path", strict=True)

    with pytest.raises(KeyError):
        dget(data, "some/wrong/path", default=1, strict=True)

    # Wildcard paths are unaffected by strict mode, they just return an empty list,
    # even if a missing key earlier in the path means the wildcard is never reached
    assert dget(data, "deeply/*/nonexistent", strict=True) == []
    assert dget(data, "some/wrong/path/*", strict=True) == []


def test_dget_wildcard_short_circuits_on_missing_key():
    """A wildcard anywhere in the path should always return a list, even if an
    earlier segment fails to match and the wildcard is never actually reached"""
    data = {"deeply": {"nested": {"path": 2}}}
    assert dget(data, "some/wrong/path/*") == []
    assert dget(data, "some/wrong[*]/path") == []


def test_has_basic():
    """has() should match whether or not the matched value is truthy"""
    data = {"deeply": {"nested": {"path": 2, "falsy": None, "zero": 0, "empty": []}}}
    assert has(data, "deeply/nested/path")
    assert not has(data, "some/wrong/path")
    assert not has(data, "deeply/nested/path/toomuch")

    # A match on a falsy value is still a match
    assert has(data, "deeply/nested/falsy")
    assert has(data, "deeply/nested/zero")
    assert has(data, "deeply/nested/empty")


def test_has_repetitions():
    """has() over indexed and wildcard paths"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert has(data, "deeply/nested[0]/path")
    assert not has(data, "deeply/nested[10]/path")
    assert has(data, "deeply/nested[-1]/path")

    # A wildcard matches if at least one element matches
    assert has(data, "deeply/nested[*]/path")
    assert not has(data, "deeply/nested[*]/missing")
    assert not has(data, "deeply/nested/*")  # bare "*" doesn't match a list, see dget


def test_has_wildcard_short_circuits_on_missing_key():
    """Same short-circuit-to-no-match behavior as dget for a wildcard past a
    missing earlier segment"""
    data = {"deeply": {"nested": {"path": 2}}}
    assert not has(data, "some/wrong/path/*")
    assert not has(data, "some/wrong[*]/path")


def test_has_empty_path():
    """An empty path always matches the root, same as dget"""
    assert has({"a": 1}, "")
    assert has([], "")


def test_ddelete_basic():
    """A plain key delete removes just that key, leaving siblings untouched"""
    data = {"a": {"b": 1, "c": 2}}
    assert ddelete(data, "a/b") is True
    assert data == {"a": {"c": 2}}
    assert not has(data, "a/b")
    assert dget(data, "a/b", default="GONE") == "GONE"


def test_ddelete_no_match():
    """Deleting a path that doesn't match anything is a no-op that reports False"""
    data = {"a": 1}
    assert ddelete(data, "b/c") is False
    assert data == {"a": 1}


def test_ddelete_empty_path():
    """An empty path never deletes anything - there's no container to remove the root
    itself from"""
    data = {"a": 1}
    assert ddelete(data, "") is False
    assert data == {"a": 1}


def test_ddelete_list_index_shifts():
    """Deleting a list element actually removes it and shifts later items down,
    rather than leaving a hole (e.g. a None placeholder) in its place"""
    data = {"items": [10, 20, 30]}
    assert ddelete(data, "items[1]") is True
    assert data == {"items": [10, 30]}


def test_ddelete_negative_index():
    data = {"items": [10, 20, 30]}
    assert ddelete(data, "items[-1]") is True
    assert data == {"items": [10, 20]}


def test_ddelete_wildcard_removes_every_match():
    """A wildcard path deletes every match, consistent with dget/has treating a
    wildcard as "every element", not just the first"""
    data = {"items": [{"drop": 1, "keep": "a"}, {"drop": 2, "keep": "b"}, {"keep": "c"}]}
    assert ddelete(data, "items[*]/drop") is True
    assert data == {"items": [{"keep": "a"}, {"keep": "b"}, {"keep": "c"}]}


def test_ddelete_wildcard_seq_multiple_indices_no_shift_bug():
    """Deleting several list elements via a single wildcard call must not corrupt
    later deletions by shifting indices out from under them"""
    data = {"items": [10, 20, 30, 40, 50]}
    assert ddelete(data, "items[*]") is True
    assert data == {"items": []}


def test_ddelete_nested_wildcards():
    data = {"groups": [{"vals": [1, 2, 3]}, {"vals": [4, 5]}, {"vals": [6]}]}
    assert ddelete(data, "groups[*]/vals[*]") is True
    assert data == {"groups": [{"vals": []}, {"vals": []}, {"vals": []}]}


def test_ddelete_immutable_sequence_is_a_graceful_no_op():
    """A wildcard fanning into a tuple can't delete from it (tuples are immutable) -
    that must not be silently reported as a successful delete"""
    data = {"items": (1, 2, 3)}
    assert ddelete(data, "items[0]") is False
    assert data == {"items": (1, 2, 3)}


def test_dget_slice():
    """A slice acts like a bounded wildcard: it always returns a list (even a
    single-element or empty one), same as a "*"/"[*]" wildcard would"""
    data = {"items": [0, 1, 2, 3, 4]}
    assert dget(data, "items[1:3]") == [1, 2]
    assert dget(data, "items[:3]") == [0, 1, 2]
    assert dget(data, "items[2:]") == [2, 3, 4]
    assert dget(data, "items[:]") == [0, 1, 2, 3, 4]
    assert dget(data, "items[::2]") == [0, 2, 4]
    assert dget(data, "items[::-1]") == [4, 3, 2, 1, 0]
    assert dget(data, "items[-3:-1]") == [2, 3]

    # Out-of-bounds and empty ranges behave like plain Python slicing: no error,
    # just an empty result - never a crash, and never treated as "no match" for
    # purposes of the default/strict machinery, since a slice is always a wildcard.
    assert dget(data, "items[10:20]") == []
    assert dget(data, "items[-1:1]") == []


def test_dget_slice_continues_the_path_per_element():
    """Each element the slice selects fans out and continues the rest of the path
    independently, exactly like [*] does but bounded to the slice's range"""
    data = {"items": [{"name": f"item{i}"} for i in range(5)]}
    assert dget(data, "items[1:3]/name") == ["item1", "item2"]


def test_has_slice():
    data = {"items": [{"name": f"item{i}"} for i in range(5)]}
    assert has(data, "items[1:3]/name")
    assert not has(data, "items[10:20]/name")


def test_ddelete_slice():
    """Deleting a slice removes every selected element and shifts the rest down,
    same as ddelete does for a single index or a full wildcard"""
    data = {"items": [0, 1, 2, 3, 4]}
    assert ddelete(data, "items[1:3]") is True
    assert data == {"items": [0, 3, 4]}


def test_ddelete_stepped_slice():
    """A stepped slice deletes a non-contiguous set of indices in one call - this
    exercises ddelete's descending-index-sort logic on indices that aren't adjacent"""
    data = {"items": [0, 1, 2, 3, 4]}
    assert ddelete(data, "items[::2]") is True
    assert data == {"items": [1, 3]}


def test_dget_malformed_slice_falls_back_to_literal_key():
    """A "[...]" that looks like it might be a slice but isn't valid (too many colons,
    or a non-integer component) is used verbatim as a literal key - including the
    brackets - the same fallback an unparseable bracket like "[abc]" already gets.

    The bracket is its own path token, separate from the key before it (the same way
    "items[0]" tokenizes to "items" then "[0]"), so the literal key it falls back to
    is "[1:2:3:4]" itself, not "items[1:2:3:4]" as one combined string."""
    data = {"items": {"[1:2:3:4]": "a", "[1:abc]": "b"}}
    assert dget(data, "items[1:2:3:4]") == "a"
    assert dget(data, "items[1:abc]") == "b"


def test_dset_with_colon_bracket_path_is_unaffected():
    """dset shares its own path parsing with dget's tokenizer only through
    _parse_index(), which never recognizes "a:b" - a colon-bracket path segment is
    still just a literal dict key for dset, exactly as before slicing existed"""
    data: dict = {}
    dset(data, "items[1:3]/x", 42)
    assert data == {"items[1:3]": {"x": 42}}


def test_dget_repetitions():
    """Check that repetitions are correctly handled"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert dget(data, "deeply/nested[0]/path") == 2
    assert not dget(data, "deeply/nested[10]/path")
    assert dget(data, "deeply/nested[-1]/path") == 4


def test_dget_repetition_from_start():
    data = [1, 2]
    assert dget(data, "[0]") == 1
    assert dget(data, "[1]") == 2


def test_dget_flatten_list():
    """
    Check flattening a list
    """
    data = [{"a": [1, 2]}, {"b": [3, 4]}]
    assert dget(data, "[*]") == data
    assert dget(data, "[*]/a") == [[1, 2]]
    assert dget(data, "[*]/a[*]") == [1, 2]
    assert dget(data, "[1]/b[*]") == [3, 4]


def test_dget_flatten_incompatible_list_dict():
    """
    What happens if you flatten a dict with list syntax, or a list with
    dict syntax ?
    """
    data = {"list": [1, 2], "dict": {"1": 1, "2": 2}}
    assert dget(data, "list/*") == []
    assert dget(data, "dict[*]") == []


def test_dget_double_flatten():
    data = {"a": {"b": {"c": 1}, "b2": {"c": 2}}}
    assert dget(data, "*") == [{"b": {"c": 1}, "b2": {"c": 2}}]
    assert dget(data, "*/*") == [{"c": 1}, {"c": 2}]
    assert dget(data, "*/*/c") == [1, 2]


def test_dget_flatten_excludes_unmatched_path():
    data = {"a": {"b": {"c": 1}, "b2": {"c": 2}}}
    assert dget(data, "*/b2/*") == [2]


def test_dget_flatten_from_start():
    """
    Check the flattening works from the start of the structure
    """
    data = {"any1": 1, "any2": 2}
    assert dget(data, "*") == [1, 2]


def test_dget_flatten_and_repetition():
    """
    Check that the flatten and repetitions features are compatible
    """
    reps = [
        {
            "nested_in_rep": 1,
        },
        {"nested_in_rep": 2, "other_nested": {"other": 3}},
    ]
    data1 = {"flattened": reps}
    data2 = {"a": [1, 2], "b": [3, 4]}
    assert dget(data1, "*") == [reps]
    assert dget(data1, "flattened[0]") == {"nested_in_rep": 1}
    # */ is a list, it needs explicit unfold
    assert dget(data1, "*/nested_in_rep") == []
    assert dget(data1, "*[*]/nested_in_rep") == [1, 2]
    assert dget(data2, "*[0]") == [1, 3]
    assert dget(data2, "*/a") == []


def test_dget_flatten():
    """Check that we can successfully flatten a nested structure"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert dget(data, "deeply/*[*]/path") == [2, 3, 4]
    data = {
        "deeply": {"nested": {"path": 2}, "other": {"path": 3}, "more": {"path": 4}}
    }
    assert dget(data, "deeply/*/path") == [2, 3, 4]


def test_decoded_classes():
    """Decode a nested dictionary into a nicer structure"""

    data = {
        "deeply": {"nested": {"name": "John"}},
        "somewhere": {"else": {"age": 25}},
        "other": {"location": {"birthday": {"year": 2020, "month": 1, "day": 20}}},
    }
    assert Person("John", 25, datetime.date(2020, 1, 20)) == Person.from_dict(data)


def test_extended_class():
    """Extend a class and validate the whole decoding logic still works"""

    data = {
        "deeply": {"nested": {"name": "John"}},
        "somewhere": {"else": {"age": 25}},
        "other": {"location": {"birthday": {"year": 2020, "month": 1, "day": 20}}},
        "list": {
            "of": {
                "hobbies": [
                    {"title": "tennis", "description": "racket sport"},
                    {"title": "football", "description": "foot sport"},
                ]
            }
        },
    }
    assert InterestedPerson(
        "John", 25, datetime.date(2020, 1, 20), ["tennis", "football"]
    ) == InterestedPerson.from_dict(data)


def test_dset():
    """Test setting some values using dset"""
    data = {}
    dset(data, "some/new/value", 1)
    assert data == {"some": {"new": {"value": 1}}}, "Simple dset OK"

    dset(data, "repetition[0]", 2)
    assert data == {
        "some": {"new": {"value": 1}},
        "repetition": [2],
    }, "Simple dset with repetition OK"

    data = {}
    dset(data, "nested[0]/repetition/value", 1)
    assert data == {
        "nested": [{"repetition": {"value": 1}}]
    }, "Repetition with nested value OK"

    data = {}
    dset(data, "multiple[0]/repetition[0]", 1)
    assert data == {"multiple": [{"repetition": [1]}]}, "Multiple repetitions OK"
    dset(data, "multiple[1]", 2)
    assert data == {"multiple": [{"repetition": [1]}, 2]}, "Appending to repetitions OK"
    dset(data, "/multiple[2]", 3)
    assert data == {"multiple": [{"repetition": [1]}, 2, 3]}, "Leading '/' supported"

    with pytest.raises(IndexError):
        dset(data, "multiple[5]", 1)


def test_dwalk():
    """
    Test iterating through a nested structure
    """
    data = {
        "value": 1,
        "nested": {"other": 2},
        "repetition": ["repetition1", {"inside": "repetition"}],
    }
    assert list(dwalk(data)) == [
        ("value", 1),
        ("nested/other", 2),
        ("repetition[0]", "repetition1"),
        ("repetition[1]/inside", "repetition"),
    ]


def test_dwalk_top_level_list():
    """dwalk should support a top-level list, not just a top-level mapping"""
    data = [1, 2, "three"]
    assert list(dwalk(data)) == [
        ("[0]", 1),
        ("[1]", 2),
        ("[2]", "three"),
    ]


def test_dwalk_top_level_list_of_mappings():
    """A top-level list of mappings should mix list and mapping path segments"""
    data = [{"a": 1}, {"a": 2, "b": {"c": 3}}]
    assert list(dwalk(data)) == [
        ("[0]/a", 1),
        ("[1]/a", 2),
        ("[1]/b/c", 3),
    ]


def test_dwalk_top_level_nested_list():
    """A top-level list of lists should chain the index segments"""
    data = [[1, 2], [3]]
    assert list(dwalk(data)) == [
        ("[0][0]", 1),
        ("[0][1]", 2),
        ("[1][0]", 3),
    ]


def test_dget_heterogenous_dicts_in_list():
    """dget shouldn't assume all dicts in a list have the same structure. However, this may have
    wider implications. A design decision is required as this behaviour is now becoming controversial
    since if you dget a list with 5 dicts but the key exists in 3 out of 5, how long should the list
    be. If you say three well how do you know which value belongs to which dict, if you say five then
    we need to design on a default value."""
    complex_dict = [
        {
            "eventID": "123",
            "entries": [
                {"type": "message", "data": {"formatted": "some-error-str"}},
                {
                    "type": "exception",
                    "data": {"values": [{"stacktrace": {"err": "why"}}]},
                },
            ],
        }
    ]
    assert dget(complex_dict, "[*]/entries") == [
        [
            {"type": "message", "data": {"formatted": "some-error-str"}},
            {
                "type": "exception",
                "data": {"values": [{"stacktrace": {"err": "why"}}]},
            },
        ]
    ]

    assert dget(complex_dict, "[*]/entries[*]/data") == [
        {"formatted": "some-error-str"}, {"values": [{"stacktrace": {"err": "why"}}]}
    ]

    # Even if each dictionary does not have all the keys, we shouldn't fail
    assert dget(complex_dict, "[*]/entries[*]/data/values") == [
        [{"stacktrace": {"err": "why"}}]
    ]


def test_flatten():
    """Ensure nested structures are flattened"""
    assert flatten([[[[[1]]]], [2]]) == [1, 2]
    assert flatten([[[[[[[[1]]]]]]]]) == [1]
    assert flatten([[]]) == []
    assert flatten([[{"documentDetails": {"number": "0"}}]]) == [
        {"documentDetails": {"number": "0"}}
    ]
