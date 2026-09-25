=======
History
=======

.. towncrier release notes start

deeppath 1.1.0 (2026-09-25)
===========================

Features
--------

- Add ``ddelete(data, path)`` to remove whatever a path matches. Wildcards
  delete every match, and removing a list element shifts later indices down.
- Add ``dsearch(data, pattern)`` to find every key matching a regular
  expression, at any depth.
- Add ``has(data, path)`` to check whether a path matches anything. It stops at
  the first match, including on wildcard paths.
- Add ``strict=True`` to ``dget`` to raise ``KeyError`` instead of returning
  ``default`` when a path does not match.
- Support ``[start:stop]`` and ``[start:stop:step]`` slices in ``dget``,
  ``has`` and ``ddelete`` paths.
- ``dwalk`` accepts a list at the top level.


Improved Documentation
----------------------

- Document the full API in the README and usage guide: wildcards, slices,
  ``strict``, ``has``, ``dset``, ``ddelete``, ``dsearch``, ``dwalk`` and
  ``flatten``.


Deprecations and Removals
-------------------------

- Drop support for Python 3.6, 3.7 and 3.8. deeppath now requires Python 3.9 or
  later.


Misc
----

- Rewrite path parsing and traversal: path segments are classified once per
  call instead of on every node visited. Wildcard reads are up to 28% faster
  and bracket-indexed ``dset`` up to 3x faster.


deeppath 0.1.6 (2022-11-10)
===========================

Improved Documentation
----------------------

- Use a pyproject.toml instead of setup.(cfg|py) (+random)
- Automate the releasing from github (#7)


deeppath 0.1.4 (2021-12-15)
---------------------------

* Bug fix: Allow ``dget`` to use any ``typing.Mapping`` as input (fixed regression introduced in 0.1.3)

deeppath 0.1.3 (2021-12-2)
---------------------------

* Allow trailing forward slash in second argument of dget
* Added type hints

deeppath 0.1.2 (2021-11-30)
---------------------------

* Added flatten. To flatten nested lists (returned by dget).

0.1.0 (2020-10-20)
---------------------------

* First release on PyPI.