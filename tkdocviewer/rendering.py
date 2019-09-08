"""Support for rendering in a background thread.

This module implements the RenderingThread class, which is used
to run a rendering backend in a separate thread. This allows slow
operations, like rendering PDF files with Ghostscript, to run in
the background without locking up the user interface.

These are internal APIs and subject to change at any time.
"""

import os
import threading

from .backends import AutoBackend


# On Python 2, basestring is the superclass for ASCII and Unicode strings.
# On Python 3, all strings are Unicode and basestring is not defined.
try: string_type = basestring
except (NameError): string_type = str


class DocumentStarted(object):
    """Trivial class used to indicate rendering has started on a document."""

    pass


class PageCount(object):
    """Trivial class used to pass a page count back to the UI."""

    __slots__ = ["_count"]

    def __init__(self, count):
        self._count = count

    def __int__(self):
        return self._count


class PageStarted(object):
    """Trivial class used to indicate rendering has started on a page."""

    pass


class RenderingThread(threading.Thread):
    """Thread to run a rendering operation in the background.

    An appropriate backend is automatically selected based on the
    file extension.

    Positional arguments:
    queue -- a queue.Queue object used to pass rendered data back
      to the user interface thread.
    canceler -- a threading.Event that, if set, causes further
      processing to be aborted.
    path -- the path to the input file.
    pages -- a list of pages (or image frames, etc.) to render.

    Keyword arguments are forwarded to the backend constructor.

    Exceptions raised in a RenderingThread are passed to the user
    interface and displayed as text strings.
    """

    __slots__ = ["backend", "kw",
                 "queue", "canceler", "path", "pages"]

    def __init__(self, queue, canceler, path, pages=None, **kw):
        """Return a new rendering thread."""

        threading.Thread.__init__(self)

        # Rendering backend; created in run() for performance reasons
        self.backend = None

        # Standard arguments
        self.queue = queue
        self.canceler = canceler
        self.path = path
        self.pages = pages

        # Keyword arguments to forward to the backend constructor
        self.kw = kw

    # ------------------------------------------------------------------------

    def run(self):
        """Render the file."""

        # Sanity check: Make sure the file actually exists before continuing.
        if not os.path.isfile(self.path):
            self._push_error("File does not exist: {0}".format(self.path))
            return

        try:
            # Create a backend instance to render pages
            self.backend = AutoBackend(self.path, **self.kw)

            # Indicate rendering has started on the document
            self.queue.put(DocumentStarted())

            # Determine the page count
            page_count = self.backend.page_count()
            self.queue.put(PageCount(page_count))

            for page in self._parse_page_list(page_count):
                if self.canceler.is_set():
                    # Halt further processing
                    break

                # Indicate we have started rendering the page
                self.queue.put(PageStarted())

                # Render the page
                image_data = self.backend.render_page(page)

                # Pass the image data to the DocViewer widget
                self.queue.put(image_data)

            # Signal we are done rendering this file
            self.queue.put(None)

        except (Exception) as err:
            # Forward the error message to the UI thread
            self._push_error(err)

    # ------------------------------------------------------------------------

    def _parse_page_list(self, page_count):
        """Parse the list of pages to render.

        The page_count argument specifies the number of pages in the
        document. It was formerly calculated here, but is now calculated
        in run() so it can also be passed back to the UI thread.
        """

        pages = self.pages

        # Default to displaying all pages in the file
        # This is here, not in an else-clause, so we'll still be covered
        # in case something goes weird within one of the if-clauses below.
        display_pages = range(1, page_count + 1)

        if isinstance(pages, string_type):
            # Interpret a string as a list of pages
            display_pages = []

            # Remove spaces from the list of pages, and replace the
            # special value "end" with the number of the last page
            pages = (pages.strip()
                          .lower()
                          .replace(" ", "")
                          .replace("end", str(page_count)))

            # Process this as a comma-separated list of individual
            # page numbers and/or ranges
            for item in pages.split(","):
                if item.isdigit():
                    # This item is a single page number
                    display_pages.append(int(item))

                elif "-" in item:
                    # This item appears to specify a range of pages
                    try:
                        start, end = map(int, item.split("-"))
                        display_pages += range(start, end + 1)

                    except (ValueError):
                        pass

        elif isinstance(pages, int):
            # Single page number
            display_pages = [pages]

        elif (hasattr(pages, "__iter__")
              or hasattr(pages, "__getitem__")):
            # Iterable sequence: list, tuple, range, set, frozenset...
            display_pages = pages

        # Return the pages to render, filtering out invalid page numbers
        return filter(lambda page: 1 <= page <= page_count, display_pages)

    def _push_error(self, err):
        """Push an error message onto the queue."""

        if isinstance(err, string_type):
            # Process err as a string
            message = err

        elif isinstance(err, Exception):
            # Process err as an exception
            message = str(err)

        else:
            # This should never happen
            message = "Something happened, but we're not sure what."

        # Put the exception into the queue and let DocViewer process it
        # in the main thread
        self.queue.put(RenderingThreadError(message))


class RenderingThreadError(Exception):
    """Exception representing an error in a rendering thread."""
    pass
