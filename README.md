**tkDocViewer** is an inefficient, yet practical, Tkinter widget for displaying file previews.

It supports a variety of document and image formats; see below for the complete list. Support for new formats can be added through a modular backend system.

Both Python 2 and 3 are supported, on Windows and Unix platforms.


## Usage

tkDocViewer consists of a single module, `tkdocviewer` (note the module name is lowercase), which exports a single class, `DocViewer`.

A brief example program:

```python
#!/usr/bin/env python3

from tkinter import *
from tkdocviewer import *

# Create a root window
root = Tk()

# Create a DocViewer widget
v = DocViewer(root)
v.pack(side="top", expand=1, fill="both")

# Display some document
v.display_file("example.pdf")

# Start Tk's event loop
root.mainloop()
```

For detailed documentation, try `python3 -m pydoc tkdocviewer`.


## Supported Formats

**Note**: Most file formats require third-party modules or external applications. tkDocViewer will still run without them, but file format support will be limited by what's available on your system.

### Document Formats
Format | Extensions | Backend | Requirements | Notes
------ | ---------- | ------- | ------------ | -----
PDF | `.pdf` | `GhostscriptBackend` | [Ghostscript](https://ghostscript.com/) |
Plain text | `.txt` | built-in | none |
Postscript | `.ps` | `GhostscriptBackend` | Ghostscript |

### Image Formats
Format | Extensions | Backend | Requirements | Notes
------ | ---------- | ------- | ------------ | -----
Bitmap image | `.bmp`, `.pcx` | built-in | [Pillow](https://python-pillow.org/)  |
GIF | `.gif` | `PILMultiframeBackend` | Pillow | Animations are displayed as individual frames.
JPEG | `.jpg`, `.jpeg` | built-in | Pillow |
PNG | `.png` | built-in | Pillow |
Netpbm | `.pbm`, `.pgm`, `.pnm`, `.ppm` | built-in | Pillow |
Targa | `.tga` | built-in | Pillow |
TIFF | `.tif`, `.tiff` | `PILMultiframeBackend` | Pillow | Supports multi-page documents.
Windows icon | `.ico` | built-in | Pillow |
X bitmap | `.xbm` | built-in | Pillow
