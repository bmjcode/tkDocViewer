"""Backends for rendering various file types.

Backends are used to render complex file formats that require
special processing to display. They normally run in a background
thread that communicates with the UI thread via a queue.

The base class for backends is backends.shared.Backend.

All backend constructors require the path to an input file as
their first positional argument. Backend constructors may optionally
accept additional keyword arguments; keywords not recognized by a
particular backend are silently ignored.

A minimal backend implements two functions:

  page_count()
    Return the number of pages in the input file.

  render_page(page_num)
    Render the specified page of the input file.
    Supported return types are:
      PIL Image object
      Tkinter PhotoImage object
      Raw image data understood by PhotoImage

These are internal APIs and subject to change at any time.
"""

import os

# Shared items for public export
from .shared import Backend, BackendError

# Individual backends, in alphabetical order
from .ghostscript import GhostscriptBackend, gs_dpi
from .pil_multiframe import PILMultiframeBackend


# To register a new backend:
#  1. Import its class.
#  2. Add its class name to __all__.
#  3. Add entries to BACKENDS_BY_EXTENSION for each supported file extension.
#     Use the extension as the key, and your class as the value.
#  4. Add each supported extension to the appropriate BACKEND_*_EXTENSIONS.

__all__ = [
    "BACKENDS_BY_EXTENSION",
    "BACKEND_DOC_EXTENSIONS",
    "BACKEND_IMAGE_EXTENSIONS",
    "AutoBackend",
    "Backend",
    "BackendError",
    "GhostscriptBackend",
    "PILMultiframeBackend",
    "gs_dpi"
]

# Backends by file extension
BACKENDS_BY_EXTENSION = {
    ".gif": PILMultiframeBackend,
    ".pdf": GhostscriptBackend,
    ".ps": GhostscriptBackend,
    ".tif": PILMultiframeBackend,
    ".tiff": PILMultiframeBackend,
}

# Document extensions supported by our backends
BACKEND_DOC_EXTENSIONS = [".pdf", ".ps"]

# Image extensions supported by our backends
BACKEND_IMAGE_EXTENSIONS = [".gif", ".tif", ".tiff"]


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
