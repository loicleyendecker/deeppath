"""Top-level package for deeppath."""

__author__ = """Loic Leyendecker"""
__email__ = "loic.leyendecker@gmail.com"

from ._version import version as __version__, version_tuple

from .deeppath import dget, dset, dwalk, flatten

__all__ = ["dget", "dset", "dwalk", "flatten", "__version__", "version_tuple"]
