"""Backend for rendering PDF documents using Ghostscript.

This is an internal API and subject to change at any time.
"""

import os
import sys
import subprocess
import threading
import io

# Used for conversion of Postscript to PDF
import tempfile
import shutil

# Downscaling support requires PIL
try:
    import PIL
except (ImportError):
    PIL = None

from .shared import (Backend, BackendError,
                     bytes_to_str, check_output, string_type)

# ------------------------------------------------------------------------

# Path to the Ghostscript executable
if sys.platform.startswith("win"):
    found_ghostscript = False

    # Possible names for the Ghostscript executable and Program Files
    # Only the console version of Ghostscript (gswin??c.exe) will work
    # because we need to check its output on stdout.
    if sys.maxsize > 2**32 or os.getenv("ProgramW6432"):
        # Favor 64-bit Ghostscript where supported
        gs_names = "gswin64c.exe", "gswin32c.exe"
        pf_vars = "ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"
    else:
        gs_names = "gswin32c.exe",
        pf_vars = "ProgramFiles",

    # Possible locations to look for Ghostscript...
    # (This is a list, not a set, to ensure we preserve our search order)
    gs_dirs = []

    # 1. A dedicated Ghostscript installation
    #    This likely has the most features and highest-quality rendering.
    for program_files in map(os.getenv, pf_vars):
        if program_files:
            gs_dir = os.path.join(program_files, "gs")
            if os.path.isdir(gs_dir) and not gs_dir in gs_dirs:
                gs_dirs.append(gs_dir)

    # 2. The directory containing the running executable
    #    This lets your application distribute its own Ghostscript binary
    #    as a fallback in case it's not installed elsewhere on the system.
    gs_dirs.append(os.path.dirname(os.path.realpath(sys.argv[0])))

    # That's enough search paths -- now start looking
    for gs_dir in gs_dirs:
        for dirpath, dirname, filenames in os.walk(gs_dir):
            for gs_name in gs_names:
                if gs_name in map(str.lower, filenames):
                    # We've found a match
                    gs_exe = os.path.join(dirpath, gs_name)

                    found_ghostscript = True
                    break

            if found_ghostscript:
                break

        if found_ghostscript:
            break

    if not found_ghostscript:
        # Maybe it's somewhere in $PATH -- unlikely, but what else can you do?
        gs_exe = gs_names[-1]

else:
    # On other platforms, assume Ghostscript is somewhere in $PATH
    gs_exe = "gs"
    gs_names = gs_exe,
    gs_dirs = os.getenv("PATH").split(os.pathsep)

# ------------------------------------------------------------------------

# Resolution for Ghostscript rendering (in dots per inch)
# TODO: This should not be hard-coded, but queried at runtime.
gs_dpi = 96             # resolution for the actual displayed preview
hr_dpi = 2 * gs_dpi     # resolution used internally for high quality


__all__ = ["GhostscriptThread", "gs_dpi"]


class GhostscriptBackend(Backend):
    """Backend to render a document using Ghostscript."""

    __slots__ = []

    def page_count(self):
        """Return the number of pages in the input file.

        This function only directly supports PDF files; other file
        types supported by Ghostscript must be converted first.
        """

        base, ext = os.path.splitext(self.input_path)
        if ext.lower() != ".pdf":
            raise BackendError("Only PDF files are supported.")

        # The Ghostscript interpreter expects forward slashes in file paths
        gs_input_path = self.input_path.replace(os.sep, "/")

        # Ghostscript command to return the page count of a PDF file
        gs_pc_command = "({0}) (r) file runpdfbegin pdfpagecount = quit"

        # Ghostscript command line
        gs_args = [gs_exe,
                   "-q",
                   "-dNODISPLAY",
                   "-c",
                   gs_pc_command.format(gs_input_path)]

        # Return the page count if it's a valid PDF, or None otherwise
        return int(check_output(gs_args))

    def render_page(self, page_num, **kw):
        """Render the specified page of the input file.

        This function only directly supports PDF files; other file
        types supported by Ghostscript must be converted first.

        Supported keyword arguments:
        res -- the resolution for rendering the file.
        """

        base, ext = os.path.splitext(self.input_path)
        if ext.lower() != ".pdf":
            raise BackendError("Only PDF files are supported.")

        # Ghostscript command line
        gs_args = [gs_exe,
                   "-q",
                   "-dBATCH",
                   "-dNOPAUSE",
                   "-dSAFER",
                   "-dPDFSettings=/SCREEN",
                   "-dPrinted=false",
                   "-dTextAlphaBits=4",
                   "-dGraphicsAlphaBits=4",
                   "-dCOLORSCREEN",
                   "-dDOINTERPOLATE",

                   # Newer versions of Ghostscript support the -sPageList
                   # option, but our user's version might not have it.
                   # This approach is clumsier, but backwards-compatible.
                   "-dFirstPage={0}".format(page_num),
                   "-dLastPage={0}".format(page_num),

                   # Raw PPM is the only full-color image format that all
                   # versions of Tk are guaranteed to support.
                   "-sDEVICE=ppmraw",
                   "-sOutputFile=-",
                   self.input_path]

        # Resolution for rendering the file
        if "res" in kw:
            gs_args.insert(2, "-r{0}".format(kw["res"]))

        # Call Ghostscript to render the PDF
        return check_output(gs_args)

    def render_to_pdf(self, output_path):
        """Render the input file to PDF."""

        # Sanity checks
        if output_path == self.input_path:
            raise BackendError("Input and output must be separate files.")
        elif output_path == "-":
            raise BackendError("Rendering to stdout is not supported.")
        elif not output_path:
            raise BackendError("You must provide an output path.")

        # Ghostscript command line
        gs_args = [gs_exe,
                   "-q",
                   "-dBATCH",
                   "-dNOPAUSE",
                   "-dSAFER",
                   "-sDEVICE=pdfwrite",
                   "-sOutputFile={0}".format(output_path),
                   self.input_path]

        # Call Ghostscript to convert the file
        check_output(gs_args)

    # ------------------------------------------------------------------------

    @staticmethod
    def gs_executable():
        """Return the path to the Ghostscript executable."""

        return gs_exe

    @staticmethod
    def gs_search_path():
        """Return the search path for the Ghostscript executable."""

        return gs_dirs

    @staticmethod
    def gs_version():
        """Return the version of the Ghostscript executable."""

        try:
            # Return the version number, minus the trailing newline
            gs_ver = check_output([gs_exe, "--version"])[:-1]
            return bytes_to_str(gs_ver)

        except (OSError):
            # No Ghostscript executable was found
            return None


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
