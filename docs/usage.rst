=====
Usage
=====

To use deeppath in a project::

    from deeppath import dget

    with open("my_data.json") as json_data
        data = json.load(json_data)

    nested_value = dget(data, "some/path/to/the/data")

With :py:func:`~deeppath.dget`, you can access data in a complex nested
structure. The nested structure should be a json-like structure, so
essentially consisting of dictionary- and list-like structures::

    nested_data = {
        "users": [
            {"surname": "Doe", "name": "John"},
            {"name": "Jane", "surname": "Doe"},
        ],
        "location": {
            "city": "London",
            "country": "United Kingdom",
        },
    }

    dget(nested_data, "location/city")  # returns "London"
    dget(nested_data, "users[0]/name")  # returns "John"

As can be seen in this example, the data can be heterogenous,
`dget` will access whatever path matches!

Dealing with dict-like structure
--------------------------------

The simplest use case is to deal with nested dictionaries: a
dict of dict of dict... (it's dictionaries all the way).
If your data is stored in a structure supporting `[key]` access, you
can simply list the keys of the successive
dictionaries separated by "/" in a single string::

    nested_data = {
        "first": {
            "second": {
                "third": "value"
            }
        }
    }

    dget(nested_data, "first/second/third")  # returns "value"

Dealing with list-like structures
---------------------------------

If your data is contained in a list-like (a container in which you can access
elements by index), you can simply enhance your string to use indexes. `dget`
supports the same semantics as python lists so you can also use negative
indices.

.. code-block:: python

    nested_data = {"names": ["John", "Jane"]}

    dget(nested_data, "names[1]")  # returns "Jane"
    dget(nested_data, "names[-1]")  # also returns "Jane"


Mixing data structure types
---------------------------

As far as `dget` is concerned, it does not matter what is the underlying data
type. It merely requires that elements are accessible either through string
keys (for dictionaries) or indices (for lists). You can have heterogenous data
and use it in a very natural way.
