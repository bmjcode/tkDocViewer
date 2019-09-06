"""Backend for rendering PDF documents using Ghostscript.

This is an internal API and subject to change at any time.
"""

import os
import sys
import subprocess
import io

# Downscaling support requires PIL
try:
    import PIL
except (ImportError):
    PIL = None

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
gs_dpi = 96

# Resolution used internally when downscaling is enabled
hr_dpi = 2 * gs_dpi


__all__ = ["GhostscriptBackend", "GhostscriptNotAvailable", "gs_dpi"]


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
        return int(self._check_output(gs_args))

    def render_page(self, page_num, **kw):
        """Render the specified page of the input file.

        This function only directly supports PDF files; other file
        types supported by Ghostscript must be converted first.

        Supported keyword arguments:
        enable_downscaling -- whether to enable downscaling using PIL.
        """

        base, ext = os.path.splitext(self.input_path)
        if ext.lower() != ".pdf":
            raise BackendError("Only PDF files are supported.")

        # Whether to enable downscaling
        # This has no effect if PIL is not available on your system.
        if "enable_downscaling" in kw:
            enable_downscaling = kw["enable_downscaling"]
        else:
            enable_downscaling = False

        # Resolution for Ghostscript rendering
        if PIL and enable_downscaling:
            gs_res = hr_dpi
        else:
            gs_res = gs_dpi

        # Ghostscript command line
        gs_args = [gs_exe,
                   "-q",
                   "-r{0}".format(gs_res),
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

        # Call Ghostscript to render the PDF
        image_data = self._check_output(gs_args)

        if PIL and enable_downscaling:
            page_bytes = io.BytesIO(image_data)
            page_image = PIL.Image.open(page_bytes)

            # Scale down the output from Ghostscript
            w, h = page_image.size
            return page_image.resize((w * gs_dpi // hr_dpi,
                                      h * gs_dpi // hr_dpi),
                                     resample=PIL.Image.BICUBIC)

        else:
            # Return the image data from Ghostscript directly
            return image_data

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
        self._check_output(gs_args)

    # ------------------------------------------------------------------------

    def _check_output(self, args):
        """Wrapper for check_output() to handle error conditions."""

        try:
            return check_output(args)

        except (OSError):
            # The Ghostscript executable could not be found
            search_names = ", ".join(gs_names)
            search_dirs = "\n".join(gs_dirs)

            raise BackendError(
                "Could not render {0}.\n"
                "Please make sure you have Ghostscript ({1}) "
                "installed somewhere on your system.\n"
                "\n"
                "Searched for Ghostscript in these locations:\n"
                "{2}"
                .format(self.input_path, search_names, search_dirs)
            )

        except (subprocess.CalledProcessError) as err:
            # Something went wrong with the call to Ghostscript
            if err.output:
                # Save the output from Ghostscript
                gs_output = bytes_to_str(err.output)[:-1]

                # Quote command line arguments containing spaces
                args = []
                for arg in err.cmd:
                    if " " in arg:
                        args.append('"{0}"'.format(arg))
                    else:
                        args.append(arg)

                # Raise a more informative exception
                raise BackendError(
                    "{0}\n"
                    "\n"
                    "Ghostscript command line (return code = {1}):\n"
                    "{2}"
                    .format(gs_output, err.returncode, " ".join(args))
                )

            else:
                # Raise the exception as-is
                raise

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
