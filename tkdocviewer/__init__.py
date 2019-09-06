"""A document viewer widget for Tkinter.

tkDocViewer is an inefficient, yet practical, Tkinter widget
for previewing documents.

It supports a variety of document and image formats; see
DocViewer.known_extensions for this version's list. Support
for new formats can be added through a modular backend system.

Most backends require third-party Python modules and/or
external applications to work. See the tkdocviewer.backends
subpackage for details.
"""

from .widget import DocViewer

# The only thing we need to publicly export is the viewer widget
__all__ = ["DocViewer"]
