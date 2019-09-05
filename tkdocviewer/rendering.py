"""Support for rendering in a background thread.

These are internal APIs and subject to change at any time.
"""

import os
import threading
import io
import subprocess

# Used for conversion of Postscript to PDF
import tempfile
import shutil

# Downscaling support requires PIL
try:
    import PIL
except (ImportError):
    PIL = None

from .backends import GhostscriptBackend, gs_dpi
from .backends.shared import string_type


class GhostscriptThread(threading.Thread):
    """Thread to render a document using Ghostscript."""

    def __init__(self, queue, canceler, path, pages=None, **kw):
        """Return a new Ghostscript process thread."""

        threading.Thread.__init__(self)

        self.queue = queue
        self.canceler = canceler
        self.path = path
        self.pages = pages

        # Save this name for our Ghostscript backend
        self.gs = None

        # Whether to enable downscaling
        # This has no effect if PIL is not available on your system.
        if "enable_downscaling" in kw:
            self.enable_downscaling = kw["enable_downscaling"]
        else:
            self.enable_downscaling = False

        # Determine what resolution Ghostscript should run at
        if PIL and self.enable_downscaling:
            self.gs_res = hr_dpi
        else:
            self.gs_res = gs_dpi

    # ------------------------------------------------------------------------

    def run(self):
        """Render the specified file."""

        # Sanity check: Make sure the file actually exists before continuing.
        if not os.path.isfile(self.path):
            self._push_error("File does not exist: {0}".format(self.path))
            return

        try:
            base, ext = os.path.splitext(self.path)

            if ext.lower() == ".pdf":
                self._render_pdf()

            elif ext.lower() == ".ps":
                self._render_ps()

            else:
                # DocViewer should have already caught this, but just in case...
                self._push_error("Could not render file: {0}\n"
                                 "Unrecognized file type.".format(self.path))

        except (OSError):
            # This indicates the Ghostscript executable was not found
            self._push_error("Could not render file: {0}\n"
                             "Please make sure you have Ghostscript ({1}) "
                             "installed somewhere on your system."
                             .format(self.path, ", ".join(gs_names)))

    # ------------------------------------------------------------------------

    def _parse_page_list(self):
        """Parse the list of pages to render."""

        pages = self.pages

        # Determine the page count
        pc = self.gs.page_count()

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
            # A CalledProcessError indicates something went wrong with
            # the call to Ghostscript
            if isinstance(err, subprocess.CalledProcessError) and err.output:
                # Display the output from Ghostscript
                message = bytes_to_str(err.output)[:-1]

                # Quote command line arguments containing spaces
                args = []
                for arg in err.cmd:
                    if " " in arg:
                        args.append('"{0}"'.format(arg))
                    else:
                        args.append(arg)

                # Append the Ghostscript command line and return value
                message += ("\n\n"
                            "Ghostscript command line (return code = {0}):\n"
                            "{1}").format(err.returncode, " ".join(args))

            else:
                # Format err as a generic exception
                message = "{0}".format(err)

        else:
            # This should never happen
            message = "Something happened, but we're not sure what."

        # Put the exception into the queue and let DocViewer process it
        # in the main thread
        self.queue.put(BackendError(message))

    def _render_pages(self, display_pages):
        """Render pages using Ghostscript.

        The rendered pages are passed to the DocViewer widget via the queue.
        """

        # Putting the for loop here, so there is only one call to
        # self._render_pages(), is an optimization because Python
        # method calls are expensive.
        for page in display_pages:
            # Halt processing if the canceler has been set
            if self.canceler.is_set():
                break

            page_data = self.gs.render_page(page, res=self.gs_res)

            # If we're using downscaling, use PIL to resize
            # the output from Ghostscript for display
            if PIL and self.enable_downscaling:
                page_bytes = io.BytesIO(page_data)
                page_image = PIL.Image.open(page_bytes)

                # Scale down the output from Ghostscript
                w, h = page_image.size
                page_image = page_image.resize((w * gs_dpi // hr_dpi,
                                                h * gs_dpi // hr_dpi),
                                               resample=PIL.Image.BICUBIC)

                # Put the processed image data in the queue
                self.queue.put(page_image)

            else:
                # Put the raw PPM data from Ghostscript in the queue
                self.queue.put(page_data)

    def _render_pdf(self, input_path=None):
        """Render the specified PDF file."""

        if not input_path:
            input_path = self.path

        self.gs = GhostscriptBackend(input_path)

        try:
            # Identify which pages to display
            display_pages = self._parse_page_list()

            # Render pages
            self._render_pages(display_pages)

            # Signal we are done rendering this file
            self.queue.put(None)

        except (Exception) as err:
            # Forward the error message to the UI thread
            self._push_error(err)

    def _render_ps(self):
        """Render the specified Postscript file."""

        # tempfile.TemporaryDirectory() provides a nicer interface,
        # but is only available on Python 3.
        temp_dir = tempfile.mkdtemp()

        try:
            # We can't render individual pages from a Postscript file, so
            # we have to convert it to PDF first. This is both inefficient
            # and, given Ghostscript's intended purpose, deeply ironic.
            pdf_output_path = os.path.join(temp_dir, "render.pdf")

            try:
                # Convert the original file to a PDF
                gs = GhostscriptBackend(self.path)
                gs.render_to_pdf(pdf_output_path)

                # Render the converted PDF file
                self._render_pdf(pdf_output_path)

            except (Exception) as err:
                self._push_error(err)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
