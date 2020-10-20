"""Validate the dget function that accesses values in nested dictionaries, using the xpath syntax"""

import datetime
from dataclasses import dataclass
from typing import List

import pytest

from deeppath import dget, dset, dwalk


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


def test_dget_flatten():
    """Check that we can successfully flatten a nested structure"""
    data = {"deeply": {"nested": [{"path": 2}, {"path": 3}, {"path": 4}]}}
    assert dget(data, "deeply/*/path") == [[2, 3, 4]]
    data = {
        "deeply": {"nested": {"path": 2}, "other": {"path": 3}, "more": {"path": 4}}
    }
    assert dget(data, "deeply/*/path") == [2, 3, 4]


@dataclass
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

    @dataclass
    class InterestedPerson(Person):
        """A normal person with a list of hobbies"""

        hobbies: List[str]

        @classmethod
        def from_dict(cls, data, **kwargs):
            hobbies = dget(data, "list/of/hobbies/*/title")
            additional_args = {**kwargs, "hobbies": hobbies}
            return super().from_dict(data, **additional_args)

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
    assert data == {"some": {"new": {"value": 1}}, "repetition": [2]}, "Simple dset with repetition OK"

    data = {}
    dset(data, "nested[0]/repetition/value", 1)
    assert data == {"nested": [{"repetition": {"value": 1}}]}, "Repetition with nested value OK"

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
        "nested": {
            "other": 2
        },
        "repetition": [
            "repetition1",
            {"inside": "repetition"}
        ]
    }
    assert list(dwalk(data)) == [
        ("value", 1),
        ("nested/other", 2),
        ("repetition[0]", "repetition1"),
        ("repetition[1]/inside", "repetition")
    ]
