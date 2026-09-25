========
deeppath
========


.. image:: https://img.shields.io/pypi/v/deeppath.svg
        :target: https://pypi.python.org/pypi/deeppath

.. image:: https://github.com/loicleyendecker/deeppath/actions/workflows/python-package.yml/badge.svg
        :target: https://github.com/loicleyendecker/deeppath/actions/workflows/python-package.yml

.. image:: https://readthedocs.org/projects/deeppath/badge/?version=latest
        :target: https://deeppath.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://static.pepy.tech/badge/deeppath
     :target: https://pepy.tech/project/deeppath
     :alt: Downloads


Python module to easily manipulate complex nested structures


* Free software: MIT license
* Documentation: https://deeppath.readthedocs.io.


Features
--------

deeppath reads, writes, deletes and searches json-like data (nested
dictionaries and lists) using short ``/``-separated paths::

    from deeppath import ddelete, dget, dsearch, dset, dwalk, flatten, has

    data = {
        "users": [
            {"name": "John", "surname": "Doe", "tags": ["a", "b"]},
            {"name": "Jane", "surname": "Doe", "tags": ["c"]},
        ],
        "location": {"city": "London", "country": "United Kingdom"},
    }

    dget(data, "location/city")        # "London"
    dget(data, "users[-1]/name")       # "Jane"
    dget(data, "users[*]/name")        # ["John", "Jane"]
    dget(data, "users[*]/tags[*]")     # ["a", "b", "c"]
    dget(data, "users[:1]/name")       # ["John"]
    dget(data, "location/*")           # ["London", "United Kingdom"]
    dget(data, "missing", default=0)   # 0

    has(data, "users[1]/name")         # True

    dset(data, "location/zip", "E1")   # creates missing keys along the way
    ddelete(data, "users[*]/surname")  # True, removed from every user

    list(dsearch(data, "^name$"))      # [("users[0]/name", "John"), ("users[1]/name", "Jane")]
    list(dwalk(data))                  # every (path, leaf value) pair
    flatten([1, [2, [3, [4]]]])        # [1, 2, 3, 4]

Summary of the API:

* ``dget(data, path, default=None, strict=False)``: return the value at
  ``path``, or a list of every match when the path contains a wildcard or a
  slice.
* ``has(data, path)``: whether ``path`` matches anything. Stops at the first
  match, so it's cheap even on large wildcard fan-outs.
* ``dset(data, path, value)``: set a value, creating intermediate dicts and
  lists as needed.
* ``ddelete(data, path)``: remove every match. List elements are really
  removed, so later indices shift down.
* ``dsearch(data, pattern)``: find every key matching a regular expression, at
  any depth.
* ``dwalk(data)``: yield ``(path, value)`` for every leaf.
* ``flatten(nested_list)``: flatten arbitrarily nested lists.

Path syntax:

=====================  =====================================================
``a/b/c``              nested dictionary keys
``items[2]``           list index, negative indices allowed
``items[*]``           every element of a list
``*``                  every value of a dictionary
``items[1:3]``         slice (``[start:stop:step]``, each part optional)
=====================  =====================================================

Note that ``*`` only matches dictionary values and ``[*]`` only matches list
elements: ``dget(data, "users/*/name")`` returns ``[]`` because ``users`` is a
list. See the `usage guide`_ for details.

.. _`usage guide`: https://deeppath.readthedocs.io/en/latest/usage.html

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
