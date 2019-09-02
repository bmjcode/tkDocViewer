"""A document viewer widget for Tkinter.

tkDocViewer is a document viewer widget for Python + Tkinter.
It is primarily intended for displaying file previews.

Currently supported file types include:
  * Plain text
  * PDF, Postscript (requires an external Ghostscript binary)
  * PNG, GIF, JPEG (requires PIL)

tkDocViewer is designed to be simple above all else. All dependencies
outside the Python standard library are optional (though file type
support will be limited). Its API is designed to let you accomplish
tasks with as few method calls as possible.

This emphasis on simplicity does come with some performance costs.
It is not necessarily the fastest nor the most resource-efficient
viewer, but it should generally run well enough to get the job done.
"""

from .widget import DocViewer

# The only thing we need to publicly export is the viewer widget
__all__ = ["DocViewer"]
