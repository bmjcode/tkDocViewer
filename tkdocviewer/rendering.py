"""Support for rendering in a background thread.

These are internal APIs and subject to change at any time.
"""

import os
import threading

# Used for conversion of Postscript to PDF
import tempfile

from .backends import GhostscriptBackend


# On Python 2, basestring is the superclass for ASCII and Unicode strings.
# On Python 3, all strings are Unicode and basestring is not defined.
try: string_type = basestring
except (NameError): string_type = str


class RenderingThread(threading.Thread):
    """Thread to run a rendering operation in the background."""

    __slots__ = ["backend", "backend_cls",
                 "queue", "canceler", "path", "pages",
                 "render_kw", "temp_files"]

    def __init__(self, backend_cls, queue, canceler, path, pages=None, **kw):
        """Return a new rendering thread."""

        threading.Thread.__init__(self)

        # Rendering backend; created by self.create_backend()
        self.backend = None

        # Standard arguments
        self.backend_cls = backend_cls
        self.queue = queue
        self.canceler = canceler
        self.path = path
        self.pages = pages

        # Optional keyword arguments for self.backend.render_page()
        self.render_kw = {}

        # Temporary files to clean up after rendering; not used by the
        # standard RenderingThread, but may be necessary for subclasses
        self.temp_files = []

    # ------------------------------------------------------------------------

    def create_backend(self):
        """Create a backend for rendering the input file.

        Your subclass can override this if you need to do special
        pre-processing, such as converting to a different file type.
        """

        self.backend = self.backend_cls(self.path)

    def run(self):
        """Render the file."""

        # Sanity check: Make sure the file actually exists before continuing.
        if not os.path.isfile(self.path):
            self._push_error("File does not exist: {0}".format(self.path))
            return

        try:
            # Create a backend instance to render pages
            self.create_backend()

            for page in self._parse_page_list():
                if self.canceler.is_set():
                    # Halt further processing
                    break

                # Render the page
                image_data = self.backend.render_page(page, **self.render_kw)

                # Pass the image data to the DocViewer widget
                self.queue.put(image_data)

            # Signal we are done rendering this file
            self.queue.put(None)

        except (Exception) as err:
            # Forward the error message to the UI thread
            self._push_error(err)

        finally:
            # Clean up temporary files
            for path in self.temp_files:
                os.remove(path)

    # ------------------------------------------------------------------------

    def _parse_page_list(self):
        """Parse the list of pages to render."""

        pages = self.pages

        # Determine the page count
        pc = self.backend.page_count()

        # Default to displaying all pages in the file
        # This is here, not in an else-clause, so we'll still be covered
        # in case something goes weird within one of the if-clauses below.
        display_pages = range(1, pc + 1)

        if isinstance(pages, string_type):
            # Interpret a string as a list of pages
            display_pages = []

            # Remove spaces from the list of pages, and replace the
            # special value "end" with the number of the last page
            pages = (pages.strip()
                          .lower()
                          .replace(" ", "")
                          .replace("end", str(pc)))

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
        return filter(lambda page: 1 <= page <= pc, display_pages)

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


class GhostscriptThread(RenderingThread):
    """Thread to render a document using Ghostscript."""

    def __init__(self, queue, canceler, path, pages=None, **kw):
        """Return a new Ghostscript process thread."""

        RenderingThread.__init__(self, GhostscriptBackend,
                                 queue, canceler, path, pages)

        # Whether to enable downscaling
        if "enable_downscaling" in kw:
            self.render_kw["enable_downscaling"] = kw["enable_downscaling"]

    # ------------------------------------------------------------------------

    def create_backend(self):
        """Create a backend for rendering the input file."""

        base, ext = os.path.splitext(self.path)

        if ext.lower() == ".pdf":
            # Render PDF files directly
            self.backend = self.backend_cls(self.path)

        elif ext.lower() == ".ps":
            # We can't render individual pages from Postscript files,
            # so convert them to PDF first
            fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)

            pdf_backend = GhostscriptBackend(self.path)
            pdf_backend.render_to_pdf(pdf_path)

            # Render the converted PDF file
            self.backend = self.backend_cls(pdf_path)

            # Clean up the temporary file after exiting
            self.temp_files.append(pdf_path)

        else:
            # This should never happen
            raise RenderingThreadError("Could not render {0}: unrecognized "
                                       "file extension.".format(self.path))


class RenderingThreadError(Exception):
    """Exception representing an error in a rendering thread."""
    pass
