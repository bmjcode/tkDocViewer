"""Backends for rendering various file types.

A backend processes an input file and returns image data that the
user interface code can display.

These are internal APIs and subject to change at any time.
"""

import os

# Shared items for public export
from .shared import Backend, BackendError

# Individual backends, in alphabetical order
from .ghostscript import GhostscriptBackend, gs_dpi


__all__ = [
    "BACKENDS_BY_EXTENSION",
    "AutoBackend",
    "Backend",
    "BackendError",
    "GhostscriptBackend",
    "gs_dpi"
]

# Backends by file extension
BACKENDS_BY_EXTENSION = {
    ".pdf": GhostscriptBackend,
    ".ps": GhostscriptBackend,
}


def AutoBackend(input_path, **kw):
    """Factory function to automatically select an appropriate backend."""

    base, ext = map(str.lower, os.path.splitext(input_path))

    if ext in BACKENDS_BY_EXTENSION:
        backend_cls = BACKENDS_BY_EXTENSION[ext]
        return backend_cls(input_path, **kw)

    else:
        raise BackendError(
            "Could not find an appropriate backend to render {0}."
            .format(input_path)
        )
