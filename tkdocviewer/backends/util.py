"""Utility functions for internal use.

This is an internal API and subject to change at any time.
"""

import os
import sys


def find_executable(basenames, search_dirs=None):
    """Find the specified executable.

    The basenames argument can be a single name or a list. If
    multiple basenames are specified, then the search order will
    be by directory first, then by basename within each directory.

    On Microsoft Windows systems, the ".exe" extension will be
    appended automatically to basenames with no extension specified.

    If no search_dirs are specified, the default is to search all
    directories in the system's $PATH.

    Returns the full path to the executable if found, None otherwise.
    """

    if isinstance(basenames, str):
        # Convert a single basename to a one-element list
        basenames = [basenames]

    if not search_dirs:
        # Search the system $PATH
        search_dirs = os.getenv("PATH").split(os.pathsep)

    for search_dir in search_dirs:
        for basename in basenames:
            # Ensure this is, in fact, a basename
            basename = os.path.basename(basename)

            # Append a file extension if necessary
            if sys.platform.startswith("win"):
                base, ext = os.path.splitext(basename)
                if not ext:
                    basename = "{0}.exe".format(basename)

            # Check if the candidate executable exists
            candidate = os.path.join(search_dir, basename)
            if os.path.isfile(candidate):
                return candidate
