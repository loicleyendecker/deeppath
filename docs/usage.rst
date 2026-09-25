=====
Usage
=====

To use deeppath in a project::

    import json

    from deeppath import dget

    with open("my_data.json") as json_data:
        data = json.load(json_data)

    nested_value = dget(data, "some/path/to/the/data")

deeppath works on json-like structures: dictionaries and lists nested in any
combination. The examples below all use this data::

    nested_data = {
        "users": [
            {"name": "John", "surname": "Doe", "tags": ["a", "b"]},
            {"name": "Jane", "surname": "Doe", "tags": ["c"]},
        ],
        "location": {
            "city": "London",
            "country": "United Kingdom",
        },
    }

Reading values with dget
------------------------

Dict-like structures
~~~~~~~~~~~~~~~~~~~~

The simplest use case is nested dictionaries: a dict of dict of dict... (it's
dictionaries all the way). If your data supports ``[key]`` access, list the
keys of the successive dictionaries separated by ``/`` in a single string. A
leading ``/`` is ignored::

    dget(nested_data, "location/city")   # "London"
    dget(nested_data, "/location/city")  # also "London"

List-like structures
~~~~~~~~~~~~~~~~~~~~

If your data is contained in a list-like (a container in which you can access
elements by index), add the index in brackets after the key.
:py:func:`~deeppath.dget` supports the same semantics as Python lists, so
negative indices work too:

.. code-block:: python

    dget(nested_data, "users[0]/name")   # "John"
    dget(nested_data, "users[-1]/name")  # "Jane"

A path can also start with an index when the data itself is a list:
``dget([{"a": 1}], "[0]/a")`` returns ``1``.

Mixing data structure types
~~~~~~~~~~~~~~~~~~~~~~~~~~~

As far as ``dget`` is concerned, it does not matter what the underlying data
types are. It only requires that elements are accessible either through string
keys (for dictionaries) or indices (for lists). Any ``Mapping`` or
``Sequence`` works, not only ``dict`` and ``list``.

Missing paths
~~~~~~~~~~~~~

When a path doesn't match, ``dget`` returns ``default`` (``None`` unless you
pass one). Pass ``strict=True`` to get a ``KeyError`` instead:

.. code-block:: python

    dget(nested_data, "location/zip")                  # None
    dget(nested_data, "location/zip", default="n/a")   # "n/a"
    dget(nested_data, "location/zip", strict=True)     # raises KeyError

Wildcards
~~~~~~~~~

A wildcard makes ``dget`` return a list of every match instead of a single
value. There are two wildcards, one for each kind of container:

* ``[*]`` matches every element of a list.
* ``*`` matches every value of a dictionary.

.. code-block:: python

    dget(nested_data, "users[*]/name")     # ["John", "Jane"]
    dget(nested_data, "location/*")        # ["London", "United Kingdom"]

Wildcards can be combined, and the result is always a flat list:

.. code-block:: python

    dget(nested_data, "users[*]/tags[*]")  # ["a", "b", "c"]

Each wildcard only matches its own kind of container. ``users`` is a list, so
``dget(nested_data, "users/*/name")`` returns ``[]``; use ``users[*]/name``.

A wildcard path always returns a list, even when nothing matches, and
``default`` and ``strict`` don't apply to it:
``dget(nested_data, "missing[*]")`` returns ``[]``.

Slices
~~~~~~

``[start:stop]`` and ``[start:stop:step]`` select part of a list, with the same
rules as Python slicing. Each part is optional:

.. code-block:: python

    dget(nested_data, "users[:1]/name")    # ["John"]
    dget(nested_data, "users[::-1]/name")  # ["Jane", "John"]

A slice behaves like a wildcard limited to the selected elements: the rest of
the path is applied to each of them and the result is a flat list. Out-of-range
slices return ``[]`` rather than raising.

Checking a path exists with has
-------------------------------

:py:func:`~deeppath.has` returns ``True`` when a path matches something, even
when the matched value is falsy (``None``, ``0``, ``[]``):

.. code-block:: python

    has(nested_data, "users[1]/name")      # True
    has(nested_data, "users[5]/name")      # False
    has({"a": None}, "a")                  # True

For a wildcard path, ``has`` returns ``True`` if at least one element matches.
It stops at the first match, so it's much cheaper than ``bool(dget(...))`` on a
large list.

Writing values with dset
------------------------

:py:func:`~deeppath.dset` sets a value and creates any missing dictionaries
along the way:

.. code-block:: python

    data = {}
    dset(data, "a/b/c", 1)
    # {"a": {"b": {"c": 1}}}

Indices create lists. An index equal to the list's length appends a new
element; an existing index updates it in place:

.. code-block:: python

    data = {}
    dset(data, "items[0]/id", 1)
    dset(data, "items[1]/id", 2)
    dset(data, "items[0]/name", "first")
    # {"items": [{"id": 1, "name": "first"}, {"id": 2}]}

An index past the end of the list raises ``IndexError``. Wildcards and slices
aren't supported by ``dset``.

Deleting values with ddelete
----------------------------

:py:func:`~deeppath.ddelete` removes whatever a path matches, and returns
``True`` if something was removed:

.. code-block:: python

    data = {"users": [{"name": "John", "age": 42}, {"name": "Jane", "age": 37}]}

    ddelete(data, "users[*]/age")  # True
    # {"users": [{"name": "John"}, {"name": "Jane"}]}

    ddelete(data, "users[0]")      # True
    # {"users": [{"name": "Jane"}]}

    ddelete(data, "missing")       # False

Wildcards and slices delete every match. Removing a list element shifts the
following elements down, the same as ``del a_list[i]``, so
``ddelete(data, "users[*]")`` leaves an empty list.

Searching keys with dsearch
---------------------------

:py:func:`~deeppath.dsearch` finds keys at any depth, without spelling out the
path to them. It yields ``(path, value)`` pairs in document order:

.. code-block:: python

    list(dsearch(nested_data, "^name$"))
    # [("users[0]/name", "John"), ("users[1]/name", "Jane")]

The pattern is a regular expression matched with ``re.search``, so it
matches anywhere in the key unless you anchor it. ``"name"`` also matches
``surname``; ``"^name$"`` doesn't. A compiled pattern works too:

.. code-block:: python

    list(dsearch(nested_data, "^(city|country)$"))
    # [("location/city", "London"), ("location/country", "United Kingdom")]

A match's value can be a whole dictionary or list, and the search continues
inside it, so nested keys with the same name are found as well:

.. code-block:: python

    list(dsearch({"price": {"price": 1}}, "price"))
    # [("price", {"price": 1}), ("price/price", 1)]

Only dictionary keys are matched, never list indices.

Walking every leaf with dwalk
-----------------------------

:py:func:`~deeppath.dwalk` yields a ``(path, value)`` pair for every leaf,
using the same path syntax as ``dget``:

.. code-block:: python

    list(dwalk({"user": {"name": "John", "tags": ["a", "b"]}}))
    # [("user/name", "John"), ("user/tags[0]", "a"), ("user/tags[1]", "b")]

The data can be a list at the top level too:
``list(dwalk([{"a": 1}]))`` gives ``[("[0]/a", 1)]``.

Flattening nested lists
-----------------------

:py:func:`~deeppath.flatten` flattens lists nested to any depth. Only lists
are flattened; tuples and other iterables are kept as single items:

.. code-block:: python

    flatten([1, [2, [3, [4]]]])  # [1, 2, 3, 4]
