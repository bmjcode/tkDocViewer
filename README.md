**tkDocViewer** is an inefficient, yet practical, Tkinter widget for displaying file previews.

It supports a variety of document and image formats; see below for the complete list. Support for new formats can be added through a modular backend system.

Both Python 2 and 3 are supported, on Windows and Unix platforms.


## Development Status

**tkDocViewer is discontinued. I will no longer be issuing updates or providing technical support.**

I created tkDocViewer to fill a particular need using the tools I had available at the time. It did the job, but was never an elegant solution. Its design suffers from poor accessibility, high resource consumption, and limited support for advanced file-format features. For example, tkDocViewer displays PDF files simply by rendering each page as a bitmap image. This uses huge amounts of memory and processor time, and prevents tkDocViewer from supporting useful features like find-in-page, since it does not actually process textual content in PDF files as text.

Given its design limitations, and given that I no longer need it for my own projects, I have decided to discontinue development of tkDocViewer. The code will remain available on GitHub, since others may still find value in it. However, I will no longer be issuing updates or providing technical support.

If you are starting a new project where PDF support is important, I strongly encourage you to consider a more modern toolkit like GTK, Qt, or wxWidgets. These toolkits offer far more robust viewer widgets with greater accessibility, lower resource consumption, and more extensive file-format support than tkDocViewer can provide.

If you are still using tkDocViewer in an existing project, please note that users have reported PDF rendering problems with Ghostscript 9.5*x* releases. For more information, please see [issue #1](https://github.com/bmjcode/tkDocViewer/issues/1) on GitHub. Downgrading to Ghostscript 9.27 may help as a short-term workaround.


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

**Note**: Most file formats require third-party modules or external applications to be present at runtime. tkDocViewer will still work without them, but file format support will be limited by what's available on your system.

### Document Formats
Format | Extensions | Requirements | Notes
------ | ---------- | ------------ | -----
PDF | `.pdf` | [Ghostscript](https://ghostscript.com/) |
Plain text | `.txt` | none |
Postscript | `.ps` | Ghostscript |
XPS | `.xps` | Ghostscript, [GhostXPS](https://www.ghostscript.com/download/gxpsdnld.html) | OpenXPS has not been tested.

### Image Formats
Format | Extensions | Requirements | Notes
------ | ---------- | ------------ | -----
Bitmap image | `.bmp`, `.pcx` | [Pillow](https://python-pillow.org/) |
GIF | `.gif` | Pillow | Animations are displayed as individual frames.
JPEG | `.jpe`, `.jpg`, `.jpeg` | Pillow |
PNG | `.png` | Pillow |
Netpbm | `.pbm`, `.pgm`, `.pnm`, `.ppm` | Pillow |
Targa | `.tga` | Pillow |
TIFF | `.tif`, `.tiff` | Pillow | Supports multi-page documents.
Windows icon | `.ico` | Pillow |
X bitmap | `.xbm` | Pillow |
