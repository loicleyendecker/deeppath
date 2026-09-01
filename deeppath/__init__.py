"""Top-level package for deeppath."""

__author__ = """Loic Leyendecker"""
__email__ = "loic.leyendecker@gmail.com"

from ._version import version as __version__
from ._version import version_tuple
from .deeppath import ddelete, dget, dset, dwalk, flatten, has

__all__ = ["ddelete", "dget", "dset", "dwalk", "flatten", "has", "__version__", "version_tuple"]
