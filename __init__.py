"""
Multi-File Archive Format (MFAF) library for Python.
This library provides functionality to read, create, and modify MFAF files.
"""

from .core import MFAFFile, MFAFEntry
from .exceptions import MFAFError

__all__ = ['MFAFFile', 'MFAFEntry', 'MFAFError']
__version__ = '0.1.0'