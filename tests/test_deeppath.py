"""Validate the dget function that accesses values in nested dictionaries, using the xpath syntax"""

import datetime
from dataclasses import dataclass
from typing import List

import pytest

from deeppath import dget, dset, dwalk, flatten

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
        hobbies = dget(data, "list/of/hobbies/*/title")
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


def test_dget_repetitions():
    """Check that repetitions are correctly handled"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert dget(data, "deeply/nested[0]/path") == 2
    assert not dget(data, "deeply/nested[10]/path")
    assert dget(data, "deeply/nested[-1]/path") == 4


@pytest.mark.skip
def test_dget_repetition_from_start():
    data = [1, 2]
    assert dget(data, "[0]") == 1
    assert dget(data, "[1]") == 2


@pytest.mark.skip
def test_dget_flatten_list():
    """
    Check flattening a list
    """
    data = [{"a": [1, 2]}, {"b": [3, 4]}]
    assert dget(data, "[*]") == data
    assert dget(data, "[*]/a") == [[1, 2]]
    assert dget(data, "[*]/a[*]") == [1, 2]
    assert dget(data, "[1]/b[*]") == [3, 4]


@pytest.mark.skip
def test_dget_flatten_incompatible_list_dict():
    """
    What happens if you flatten a dict with list syntax, or a list with
    dict syntax ?
    """
    data = {"list": [1, 2], "dict": {"1": 1, "2": 2}}
    assert dget(data, "list/*") is None
    assert dget(data, "dict[*]") is None


@pytest.mark.skip
def test_dget_double_flatten():
    data = {"a": {"b": {"c": 1}, "b2": {"c": 2}}}
    assert dget(data, "*") == [{"b": {"c": 1}, "b2": {"c": 2}}]
    assert dget(data, "*/*") == [{"c": 1}, {"c": 2}]
    assert dget(data, "*/*/c") == [1, 2]


@pytest.mark.skip
def test_dget_flatten_excludes_unmatched_path():
    data = {"a": {"b": {"c": 1}, "b2": {"c": 2}}}
    assert dget(data, "*/b2/*") == [2]


def test_dget_flatten_form_start():
    """
    Check the flattening works from the start of the structure
    """
    data = {"any1": 1, "any2": 2}
    assert dget(data, "*") == [1, 2]


@pytest.mark.skip
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
    assert dget(data1, "*/nested_in_rep") is None
    assert dget(data1, "*[*]/nested_in_rep") == [1, 2]
    assert dget(data2, "*[0]") == [1, 3]
    assert dget(data2, "*/a") is None



def test_dget_flatten():
    """Check that we can successfully flatten a nested structure"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert dget(data, "deeply/*/path") == [[2, 3, 4]]
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


def test_flatten():
    """Ensure nested structures are flattened"""
    assert flatten([[[[[1]]]], [2]]) == [1, 2]
    assert flatten([[[[[[[[1]]]]]]]]) == [1]
    assert flatten([[]]) == []
    assert flatten([[{"documentDetails": {"number": "0"}}]]) == [
        {"documentDetails": {"number": "0"}}
    ]
