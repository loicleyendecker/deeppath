========
deeppath
========


.. image:: https://img.shields.io/pypi/v/deeppath.svg
        :target: https://pypi.python.org/pypi/deeppath

.. image:: https://img.shields.io/travis/loicleyendecker/deeppath.svg
        :target: https://travis-ci.com/loicleyendecker/deeppath

.. image:: https://readthedocs.org/projects/deeppath/badge/?version=latest
        :target: https://deeppath.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


.. image:: https://pyup.io/repos/github/loicleyendecker/deeppath/shield.svg
     :target: https://pyup.io/repos/github/loicleyendecker/deeppath/
     :alt: Updates



Python module to easily manipulate complex nested structures


* Free software: MIT license
* Documentation: https://deeppath.readthedocs.io.


Features
--------

With `~deeppath.dget`, you can access data in a complex nested
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

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
