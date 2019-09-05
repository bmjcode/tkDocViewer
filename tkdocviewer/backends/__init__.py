"""Backends for rendering various file types.

A backend processes an input file and returns image data that the
user interface code can display.

These are internal APIs and subject to change at any time.
"""

# Shared items for public export
from .shared import BackendError

# Individual backends, in alphabetical order
from .ghostscript import GhostscriptThread, gs_dpi
