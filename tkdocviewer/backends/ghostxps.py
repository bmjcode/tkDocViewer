"""Backend for rendering XPS documents using GhostXPS.

This is an internal API and subject to change at any time.
"""

import os
import sys
import subprocess

# Used for conversion of XPS to PDF
import tempfile

from .ghostscript import GhostscriptBackend
from .shared import Backend, BackendError, check_output
from .util import find_executable

# -------------------------------------------------------------------------

# Path to the GhostXPS executable
if sys.platform.startswith("win"):
    from glob import glob

    # Possible names for the GhostXPS executable
    if sys.maxsize > 2**32 or os.getenv("ProgramW6432"):
        gxps_names = "gxpswin64.exe", "gxpswin32.exe"
    else:
        gxps_names = "gxpswin32.exe",

    # Possible locations to look for GhostXPS...
    gxps_dirs = []

    # GhostXPS doesn't include an installer as of version 9.27,
    # so if it's available, it's probably under your application directory
    app_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    for dirpath, dirnames, filenames in os.walk(app_dir):
        for dirname in dirnames:
            gxps_dir = os.path.join(dirpath, dirname)
            if glob(os.path.join(gxps_dir, "gxpswin??.exe")):
                # Directory appears to contain a GhostXPS executable
                gxps_dirs.append(gxps_dir)

    # Now find the executable
    gxps_exe = find_executable(gxps_names, gxps_dirs)

else:
    # Assume anything else is some kind of Unix system
    # If GhostXPS is available, chances are it's somewhere in $PATH
    gxps_names = "gxps",
    gxps_dirs = os.getenv("PATH").split(os.pathsep)
    gxps_exe = find_executable(gxps_names, gxps_dirs)


__all__ = ["GhostXPSBackend"]


class GhostXPSBackend(Backend):
    """Backend to render a document using GhostXPS.

    Documents are internally converted to PDF, then rendered using
    the Ghostscript backend. Temporary files created by this process
    are cleaned up when the backend object is destroyed.

    This backend requires an external GhostXPS binary.
    """

    __slots__ = ["page_count", "render_page"]

    def __init__(self, input_path, **kw):
        """Return a new GhostXPS rendering backend."""

        Backend.__init__(self, input_path, **kw)

        # Make sure we have a GhostXPS binary available
        if not gxps_exe:
            # Identify possible executable names and search dirs
            search_names = ", ".join(gxps_names)
            search_dirs = "\n".join(gxps_dirs)
            if not search_dirs:
                search_dirs = "<no GhostXPS installations found>"

            raise BackendError(
                "Could not render {0}.\n"
                "Please make sure you have GhostXPS installed.\n"
                "\n"
                "Searched for {1} in these locations:\n"
                "{2}"
                .format(self.input_path, search_names, search_dirs)
            )

        fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        # GhostXPS command line
        # Note: Not all Ghostscript arguments are supported or required.
        gxps_args = [gxps_exe,
                     "-dNOPAUSE",
                     "-sDEVICE=pdfwrite",
                     "-sOutputFile={0}".format(pdf_path),
                     self.input_path]

        # Convert the input file to PDF
        check_output(gxps_args)
        self.temp_files.append(pdf_path)

        # Create a Ghostscript backend, and forward method calls to it
        gs = GhostscriptBackend(pdf_path, **kw)
        self.page_count = gs.page_count
        self.render_page = gs.render_page
