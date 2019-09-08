"""Implementation of the viewer widget."""

import os
import sys
import threading
import gc

try:
    # Python 3
    import queue
except (ImportError):
    # Python 2
    import Queue as queue

try:
    # Python 3
    import tkinter as tk
except (ImportError):
    # Python 2
    import Tkinter as tk

try:
    try:
        # Python 3
        import tkinter.ttk as ttk
    except (ImportError):
        # Python 2
        import ttk
except (ImportError):
    # Can't provide ttk's Scrollbar
    pass

try:
    import PIL.Image
    import PIL.ImageTk
except (ImportError):
    PIL = None

from .backends import (BACKEND_DOC_EXTENSIONS,
                       BACKEND_IMAGE_EXTENSIONS,
                       BACKENDS_BY_EXTENSION,
                       GhostscriptBackend, gs_dpi)
from .rendering import DocumentStarted, PageCount, PageStarted, RenderingThread


__all__ = ["DocViewer"]


class DocViewer(tk.Frame, object):
    """Document viewer widget.

    The constructor accepts the usual Tkinter keyword arguments, plus
    a handful of its own:

      enable_downscaling (bool; default: False)
        Enables downscaling for PDF documents. Not usually needed.
        See the help text for the enable_downscaling property.

      force_text_display (bool; default: False)
        Force unrecognized file types to display as plain text.

      scrollbars (str; default: "both")
        Which scrollbars to provide.
        Must be one of "vertical", "horizontal," "both", or "neither".

      text_font (tkinter.font.Font)
        The default font used for plain text output.

      use_ttk (bool; default: False)
        Whether to use ttk widgets if available.
        The default is to use standard Tk widgets. This setting has
        no effect if ttk is not available on your system.

      wrap_text (bool; default: True)
        Enables wrapping long lines when displaying plain text.

    This widget supports several custom Tk events:

      <<DocumentStarted>>
        Rendering started on a document.

      <<PageCount>>
        The document's page count has been updated.

      <<PageStarted>>
        Rendering started on a page within a document.

      <<PageFinished>>
        Rendering finished on a page within a document.

      <<DocumentFinished>>
        Rendering finished on a document.

      <<RenderingError>>
        An error occurred while rendering a document.
    """

    # Note we explicitly inherit from object because Tkinter on Python 2
    # uses old-style classes.

    def __init__(self, master=None, **kw):
        """Return a new DocViewer widget."""

        tk.Frame.__init__(self, master)

        # The currently displayed file path and pages
        self._display_path = None
        self._display_pages = None

        # The number of pages in the displayed file
        self._page_count = 1

        # The number of pages that have been rendered so far
        self._rendered_page_count = 0

        # Used to track whether we are currently rendering a page.
        # Watch this with wait_variable() if you need to do anything
        # to the displayed file after it's been rendered.
        self._rendering = tk.BooleanVar()
        self._rendering.set(0)

        # Storage for rendered pages
        self._rendered_pages = []

        # Created as needed to communicate with a rendering thread
        self._queue = None
        self._canceler = None

        # Vertical offset for the next page on the canvas
        # Used in self._process_queue()
        self._y_offset = 0

        # Whether to enable downscaling for PDF files
        self._enable_downscaling = tk.BooleanVar()
        if "enable_downscaling" in kw:
            self._enable_downscaling.set(kw["enable_downscaling"])
            del kw["enable_downscaling"]
        else:
            self._enable_downscaling.set(0)

        # Whether to force unrecognized file types to display as plain text
        self._force_text_display = tk.BooleanVar()
        if "force_text_display" in kw:
            self._force_text_display.set(kw["force_text_display"])
            del kw["force_text_display"]
        else:
            self._force_text_display.set(0)

        # Which scrollbars to provide
        if "scrollbars" in kw:
            scrollbars = kw["scrollbars"]
            del kw["scrollbars"]

            if not scrollbars:
                scrollbars = self._DEFAULT_SCROLLBARS
            elif not scrollbars in self._VALID_SCROLLBARS:
                raise ValueError("scrollbars parameter must be one of "
                                 "'vertical', 'horizontal', 'both', or "
                                 "'neither'")
        else:
            scrollbars = self._DEFAULT_SCROLLBARS

        # Font for plain-text output
        if "text_font" in kw:
            self._text_font = kw["text_font"]
            del kw["text_font"]
        else:
            self._text_font = self._DEFAULT_TEXT_FONT

        # Whether to use ttk widgets if available
        if "use_ttk" in kw:
            if ttk and kw["use_ttk"]:
                Scrollbar = ttk.Scrollbar
            else:
                Scrollbar = tk.Scrollbar
            del kw["use_ttk"]
        else:
            Scrollbar = tk.Scrollbar

        # Whether to wrap long text lines for display
        self._wrap_text = tk.BooleanVar()
        if "wrap_text" in kw:
            self._wrap_text.set(kw["wrap_text"])
            del kw["wrap_text"]
        else:
            self._wrap_text.set(1)

        # The default appearance has a 1px border with sunken relief
        if not "relief" in kw:
            self["relief"] = "sunken"
        if not "borderwidth" in kw:
            self["borderwidth"] = 1

        # Canvas widget to display the document
        c = self._canvas = tk.Canvas(self,
                                     takefocus=1)

        # Forward focus events to the canvas
        self.focus_set = self._canvas.focus_set

        # Scrollbars
        xs = self._x_scrollbar = Scrollbar(self,
                                           orient="horizontal",
                                           command=c.xview)
        ys = self._y_scrollbar = Scrollbar(self,
                                           orient="vertical",
                                           command=c.yview)
        c.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)

        # Lay out our widgets
        c.grid(row=0, column=0, sticky="nsew")
        if scrollbars == "vertical" or scrollbars == "both":
            ys.grid(row=0, column=1, sticky="ns")
        if scrollbars == "horizontal" or scrollbars == "both":
            xs.grid(row=1, column=0, sticky="we")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Take the mouse focus when the canvas is clicked
        c.bind("<Button-1>", lambda event=None: c.focus_set())

        # Enable scrolling when the canvas has the focus
        self.bind_arrow_keys(c)
        self.bind_scroll_wheel(c)

        # Re-display text when the canvas is resized
        c.bind("<Configure>", self.refresh)

        # Process our remaining configuration options
        self.configure(**kw)

    def __setitem__(self, key, value):
        """Configure resources of a widget."""

        if key in self._CANVAS_KEYS:
            # Forward these to the canvas widget
            self._canvas.configure(**{key: value})

        else:
            # Handle everything else normally
            tk.Frame.configure(self, **{key: value})

    # ------------------------------------------------------------------------

    def bind_arrow_keys(self, widget):
        """Bind the specified widget's arrow key events to the canvas."""

        widget.bind("<Up>",
                    lambda event: self._canvas.yview_scroll(-1, "units"))

        widget.bind("<Down>",
                    lambda event: self._canvas.yview_scroll(1, "units"))

        widget.bind("<Left>",
                    lambda event: self._canvas.xview_scroll(-1, "units"))

        widget.bind("<Right>",
                    lambda event: self._canvas.xview_scroll(1, "units"))

    def bind_scroll_wheel(self, widget):
        """Bind the specified widget's mouse scroll event to the canvas."""

        widget.bind("<MouseWheel>", self._scroll_canvas)
        widget.bind("<Button-4>", self._scroll_canvas)
        widget.bind("<Button-5>", self._scroll_canvas)

    def can_display(self, path):
        """Return whether this widget can display the specified file."""

        base, ext = map(str.lower, os.path.splitext(path))
        return (ext in self.known_extensions or self._force_text_display.get())

    def cancel_rendering(self, event=None):
        """Cancel the current rendering process.

        This is safe to call if there is no current rendering process;
        it simply will have no effect. Called automatically when displaying
        a new file, erasing the canvas, or destroying the widget.
        """

        if self._canceler:
            self._canceler.set()

    def cget(self, key):
        """Return the resource value for a KEY given as string."""

        if key in self._CANVAS_KEYS:
            return self._canvas.cget(key)

        else:
            return tk.Frame.cget(self, key)

    # Also override this alias for cget()
    __getitem__ = cget

    def configure(self, cnf=None, **kw):
        """Configure resources of a widget."""

        # This is overridden so we can use our custom __setitem__()
        # to pass certain options directly to the canvas.
        if cnf:
            for key in cnf:
                self[key] = cnf[key]

        for key in kw:
            self[key] = kw[key]

    # Also override this alias for configure()
    config = configure

    def destroy(self):
        # The docstring is [sic] from Tkinter
        """Destroy this and all descendants widgets."""

        self.cancel_rendering()
        return tk.Frame.destroy(self)

    def display_file(self, path, pages=None):
        """Display the specified file.

        For file types like PDF that support multi-page documents,
        you can optionally specify a list of pages to display. This
        can be a standard Python list, or a string using "," and "-"
        to separate individual pages and ranges, respectively. The
        special value "end" refers to the last page in the file.

        An example page list string: "1-2,5,8,12-end"

        If no pages argument is specified, or the file type does not
        support multi-page documents, the entire file will be displayed.
        """

        # Blank the canvas
        self.erase()

        # Determine how to render the file based on its extension
        base, ext = map(str.lower, os.path.splitext(path))

        if ext in BACKENDS_BY_EXTENSION.keys():
            # File format supported by one of our backends
            self._start_rendering_thread(path, pages)

        elif ext in self._builtin_image_extensions:
            # Image format with built-in support
            self._render_image(path)

        elif (ext in self._builtin_text_extensions
              or self._force_text_display.get()):
            # Plain-text format with built-in support
            self._render_text(path)

        else:
            self.display_text(
                "Could not find an appropriate backend to render {0}."
                .format(path)
            )

        # Save the file path and pages
        self._display_path = path
        self._display_pages = pages

        self.scroll_to_top()

    def display_text(self, message):
        """Display the specified message."""

        # Blank the canvas
        self.erase()

        # Display the message text
        self._canvas.create_text(self._TEXT_X_MARGIN, self._TEXT_Y_MARGIN,
                                 anchor="nw", tags="message",
                                 text=message, font=self._text_font)
        self.refresh()

        # The displayed text is always considered to be the entire "document"
        self._rendered_page_count = 1

        self.scroll_to_top()

    def erase(self):
        """Erase all displayed content."""

        c = self._canvas

        # Cancel any current rendering process
        if self._rendering.get():
            self.cancel_rendering()
            self.wait_variable(self._rendering)

        # Blank the canvas
        c.delete("all")
        self._y_offset = 0

        # Delete rendered pages from memory
        del self._rendered_pages[:]

        # Forget the currently displayed file path and pages
        self._display_path = None
        self._display_pages = None

        # Reset the page counts
        self._page_count = 1
        self._rendered_page_count = 0

        if gc.isenabled():
            # Call the garbage collector to free unused memory
            gc.collect()

    def fit_page(self, width, height=None):
        """Resize the widget to fit a page of the specified dimensions.

        The width and height parameters are specified in inches.
        """

        self["width"] = width * gs_dpi
        if height:
            self["height"] = height * gs_dpi

    def refresh(self, event=None):
        """Refresh the display.

        This is called automatically when the canvas is resized.
        Your application can also call this directly -- for example,
        to redisplay text after toggling the "wrap_text" property.

        This function does NOT reload the displayed file from disk.
        """

        c = self._canvas

        if self._wrap_text.get():
            # Wrap the text to fit the canvas widget
            text_width = c.winfo_width() - self._TEXT_X_MARGIN
            c.itemconfigure("message", width=text_width)

        else:
            # Disable text wrapping
            c.itemconfigure("message", width=0)

        # Update the canvas's scroll region
        c.configure(scrollregion=c.bbox("all"))

    def reload(self, event=None):
        """Reload the currently displayed file from disk."""

        if self._display_path:
            self.display_file(self._display_path, self._display_pages)

    def scroll_to_top(self):
        """Scroll to the top-left corner of the canvas."""

        self._canvas.xview_moveto(0)
        self._canvas.yview_moveto(0)

    # ------------------------------------------------------------------------

    def _add_page_to_canvas(self, image_data):
        """Add a rendered page to the canvas."""

        c = self._canvas

        if PIL and isinstance(image_data, PIL.Image.Image):
            # This is an image processed by PIL, so convert it to something
            # Tkinter can display
            page_image = PIL.ImageTk.PhotoImage(image_data)

        elif isinstance(image_data, tk.PhotoImage):
            # This is a Tkinter PhotoImage
            page_image = image_data

        else:
            # Presume we're working with raw image data
            page_image = tk.PhotoImage(data=image_data)

        # Save a reference to this image
        self._rendered_pages.append(page_image)

        # Add this image to the canvas
        c.create_image(0, self._y_offset, anchor="nw",
                       image=page_image, tags="page_image")

        # Update the canvas's scroll region
        c.configure(scrollregion=c.bbox("all"))

        # Offset the next page by the height of this page, plus 4px padding
        self._y_offset += page_image.height() + 4

        # Increment the number of pages rendered
        self._rendered_page_count += 1

    def _process_queue(self):
        """Retrieve data from a rendering thread."""

        # Sanity check: Make sure we currently have a queue!
        if not self._queue:
            return

        timeout = 50    # msec

        try:
            # Pull the next item from the queue
            item = self._queue.get_nowait()

            if item is None:
                # A None value indicates we can exit the processing loop
                self._rendering.set(0)
                self.event_generate("<<DocumentFinished>>")

            elif isinstance(item, DocumentStarted):
                # Indicate rendering has started on the document
                self.event_generate("<<DocumentStarted>>")

            elif isinstance(item, PageStarted):
                # Indicate rendering has started on a page
                self.event_generate("<<PageStarted>>")

            elif isinstance(item, PageCount):
                # Update the number of pages in the document
                self._page_count = int(item)
                self.event_generate("<<PageCount>>")

            elif isinstance(item, Exception):
                # An exception occurred in the rendering thread
                self._rendering.set(0)

                # Display the error message on the canvas
                self.display_text(item)

                # Set the rendered page count to zero since no content
                # has actually been rendered
                self._rendered_page_count = 0

                self.event_generate("<<RenderingError>>")

            else:
                # Presume item contains image data
                self._add_page_to_canvas(item)
                self.event_generate("<<PageFinished>>")

        except (queue.Empty):
            # Still waiting on the next item
            pass

        except (tk.TclError):
            # Has the widget ceased to exist?
            pass

        # Keep the user interface updated
        self.master.update_idletasks()

        if self._rendering.get():
            # Keep the loop going until we're told to stop
            self.master.after(timeout, self._process_queue)

        else:
            # Delete the old queue and canceler
            del self._queue
            self._queue = None

            del self._canceler
            self._canceler = None

    def _render_image(self, path):
        """Render an image file using PIL.

        This is implemented here for performance reasons; it's much
        more efficient to process single-frame images in the main
        thread than to use a backend in a separate rendering thread.

        This function only displays the first frame of multi-frame
        images such as GIF and TIFF. To display all the frames, start
        a rendering thread using PILMultiframeBackend.
        """

        if PIL:
            try:
                im = PIL.Image.open(path)
                self._add_page_to_canvas(im)

            except (Exception) as err:
                self.display_text(err)

        else:
            self.display_text(
                "Could not render {0} because PIL is not available "
                "on your system."
                .format(path)
            )

    def _render_text(self, path):
        """Render a plain-text file."""

        try:
            with open(path, "r") as in_file:
                self.display_text(in_file.read())

        except (Exception) as err:
            self.display_text(err)

    def _scroll_canvas(self, event):
        """Scroll the canvas."""

        c = self._canvas

        if sys.platform.startswith("darwin"):
            # macOS
            c.yview_scroll(-1 * event.delta, "units")

        elif event.num == 4:
            # Unix - scroll up
            c.yview_scroll(-1, "units")

        elif event.num == 5:
            # Unix - scroll down
            c.yview_scroll(1, "units")

        else:
            # Windows
            c.yview_scroll(-1 * (event.delta // 120), "units")

    def _start_rendering_thread(self, path, pages=None):
        """Render a file in a background thread."""

        # Flag that we are currently rendering a page
        self._rendering.set(1)

        # Create a new queue for rendered pages
        # This avoids displaying the wrong file if display_file() is called
        # again before Ghostscript finishes rendering the current file. The
        # old queue will eventually be garbage-collected and its memory freed.
        self._queue = queue.Queue()

        # Create a canceler to stop rendering on demand
        self._canceler = threading.Event()

        # Whether to enable downscaling
        enable_downscaling = self._enable_downscaling.get()

        # Create a rendering thread to render the file
        rt = RenderingThread(self._queue, self._canceler, path, pages,
                             enable_downscaling=enable_downscaling)
        rt.start()

        # Start this in a loop to render each page on the canvas
        self._process_queue()

    # ------------------------------------------------------------------------

    @property
    def canvas(self):
        """The canvas widget used to display the document."""

        return self._canvas

    @property
    def display_pages(self):
        """The list of page numbers to display.

        This is only applicable to file types like PDF that support
        multi-page documents.
        """

        return self._display_pages

    @property
    def display_path(self):
        """The path to the currently displayed file."""

        return self._display_path

    @property
    def enable_downscaling(self):
        """Whether to enable downscaling for PDF documents.

        This was originally implemented as a workaround for poor
        rendering quality on a less capable version of Ghostscript;
        it is neither necessary nor recommended on most systems.

        When downscaling is enabled, Ghostscript will render PDF
        documents internally at a higher resolution, then DocViewer
        will resize them for display using PIL. This is inefficient,
        but it may improve the appearance and readability of some
        files, such as pure black-and-white scans.

        If PIL is not available on your system, the enable_downscaling
        setting will be silently ignored.

        This is a BooleanVar that your user interface can toggle at
        runtime via a Checkbutton widget.
        """

        return self._enable_downscaling

    @property
    def force_text_display(self):
        """Whether to force unrecognized file types to display as plain text.

        This is a BooleanVar that your user interface can toggle at
        runtime via a Checkbutton widget.
        """

        return self._force_text_display

    @property
    def page_count(self):
        """The number of pages in the displayed file.

        This property returns the number of logical pages in the document
        as defined by its file format. Note this is not necessarily the
        number of physical pages that would be needed to fit its contents.

        This is only applicable to file formats with an inherent concept
        of pages (or some equivalent unit, such as image frames).

        For animated images, this is the number of frames in the animation.

        Formats rendered as plain text are always considered to have one
        logical page, regardless of the actual length of their content.
        """

        return self._page_count

    @property
    def rendered_page_count(self):
        """The number of pages that have been rendered.

        This is based on local pages as defined by the displayed file's
        format. See the documentation for the page_count property, above.
        """

        return self._rendered_page_count

    @property
    def rendering(self):
        """Indicates whether there is an active rendering thread.

        This is a BooleanVar that your application can watch using
        wait_variable() to take action after rendering has finished.

        This property is intended as read-only; overriding its value
        may result in locking up or other undesirable behavior.
        """

        return self._rendering

    @property
    def wrap_text(self):
        """Whether to wrap long lines when displaying plain text.

        This is a BooleanVar that your user interface can toggle at
        runtime via a Checkbutton widget.
        """

        return self._wrap_text

    # ------------------------------------------------------------------------

    @staticmethod
    def filetypes():
        """Return a list of supported file types for use with file dialogs."""

        def stringify(extensions):
            return " ".join("*{0}".format(ext) for ext in extensions)

        return [
            ("All Supported Files", stringify(DocViewer.known_extensions)),
            ("Documents", stringify(DocViewer.doc_extensions)),
            ("Images", stringify(DocViewer.image_extensions)),
        ]

    # ------------------------------------------------------------------------

    # Keys for configure() to forward to the canvas widget
    _CANVAS_KEYS = "width", "height", "takefocus"

    # Default font for plain-text output
    _DEFAULT_TEXT_FONT = "Courier", 10

    # Margins for displaying plain text on the canvas
    _TEXT_X_MARGIN = 8
    _TEXT_Y_MARGIN = 8

    # Scrollbar-related configuration
    _DEFAULT_SCROLLBARS = "both"
    _VALID_SCROLLBARS = "vertical", "horizontal", "both", "neither"

    # ------------------------------------------------------------------------

    # These are left in for backwards compatibility with version 1.0.
    # New code should use can_display(), filetypes(), etc. as appropriate.
    #
    # These values are technically user-customizable, but this is considered
    # an undocumented feature, and may be removed from a future release.

    # Recognized image extensions
    # Note: GIF and TIFF support is handled by PILMultiframeBackend.
    _builtin_image_extensions = [".bmp", ".ico", ".jpe", ".jpg", ".jpeg",
                                 ".pbm", ".pcx", ".pgm", ".png", ".pnm",
                                 ".ppm", ".tga", ".xbm"]
    image_extensions = sorted(_builtin_image_extensions
                              + BACKEND_IMAGE_EXTENSIONS)

    # Recognized plain-text extensions
    _builtin_text_extensions = [".txt"]
    text_extensions = _builtin_text_extensions

    # Recognized document extensions
    doc_extensions = sorted(text_extensions
                            + BACKEND_DOC_EXTENSIONS)

    # All known file extensions
    known_extensions = sorted(doc_extensions + image_extensions)

    # ------------------------------------------------------------------------

    # Useful Ghostscript-related debugging information
    gs_executable = staticmethod(GhostscriptBackend.executable)
    gs_search_path = staticmethod(GhostscriptBackend.search_path)
    gs_version = staticmethod(GhostscriptBackend.version)
