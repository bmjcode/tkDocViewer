"""Backend for rendering PDF documents using Ghostscript.

This is an internal API and subject to change at any time.
"""

import os
import sys

from .shared import Backend, BackendError, bytes_to_str, check_output

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
