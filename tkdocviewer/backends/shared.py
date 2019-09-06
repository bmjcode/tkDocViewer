"""Shared code for rendering backends.

This is an internal API and subject to change at any time.
"""

import sys
import subprocess


class Backend(object):
    """Base class for tkDocViewer backends."""

    __slots__ = ["input_path"]

    def __init__(self, input_path):
        """Return a new rendering backend."""

        self.input_path = input_path

    def page_count(self):
        """Return the number of pages in the input file.

        Override this in your subclass.
        """

        raise NotImplementedError

    def render_page(self, page_num, **kw):
        """Render the specified page of the input file.

        This should return image data that the UI code can process.
        Supported keyword arguments are defined by each backend.

        Override this in your subclass.
        """

        raise NotImplementedError


class BackendError(Exception):
    """Exception representing an error in one of the rendering backends."""
    pass


def bytes_to_str(value):
    """Convert bytes to str."""

    if isinstance(value, bytes) and not isinstance(value, str):
        # Clumsy way to convert bytes to str on Python 3
        return "".join(map(chr, value))

    else:
        return value

def check_output(args):
    """Run command with arguments and return its output.

    This is a wrapper for subprocess.check_output() that hides the
    console window when running on Microsoft Windows.
    """

    # Standard keyword arguments for subprocess.check_output()
    subprocess_kw = {
        "stdin": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }

    if sys.platform.startswith("win"):
        # Hide the console window when running under pythonw.exe.
        # Note that a new STARTUPINFO object has to be created for
        # each call to subprocess.check_output().
        gs_si = subprocess.STARTUPINFO()
        gs_si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        gs_si.wShowWindow = subprocess.SW_HIDE

        subprocess_kw["startupinfo"] = gs_si

    return subprocess.check_output(args, **subprocess_kw)
