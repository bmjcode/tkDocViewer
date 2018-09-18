**tkDocViewer** is a document viewer widget for Python + Tkinter. It is primarily intended for displaying file previews.

Currently supported file types include:

* Plain text
* PDF, Postscript (requires an external Ghostscript binary)
* PNG, GIF, JPEG (requires PIL)

tkDocViewer is designed to be simple above all else. All dependencies outside the Python standard library are optional (though file type support will be limited). Its API is designed to let you accomplish tasks with as few method calls as possible.

This emphasis on simplicity does come with some performance costs. It is not necessarily the fastest nor the most resource-efficient viewer, but it should generally run well enough to get the job done.

Both Python 2 and 3 are supported, on Windows and Unix platforms.


## Usage

tkDocViewer consists of a single module, `tkdocviewer` (note the module name is lowercase), which exports a single class, `DocViewer`.

A brief example program:

```python
# This assumes Python 3
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

For detailed documentation, try `python -m pydoc tkdocviewer`.


## Dependencies

Most file formats require third-party modules or external applications. tkDocViewer will still run without them, but file format support will be limited by what's available on your system.

Name | Type | Notes
---- | ---- | -----
[Ghostscript](https://ghostscript.com/) | External application | Required for PDF and Postscript support.
[Pillow](https://python-pillow.org/) | Python module | Required for most image formats; optional for PDF support.
