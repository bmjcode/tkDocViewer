"""Shared code for rendering backends.

This is an internal API and subject to change at any time.
"""

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

# On Python 2, basestring is the superclass for ASCII and Unicode strings.
# On Python 3, all strings are Unicode and basestring is not defined.
try: string_type = basestring
except (NameError): string_type = str
