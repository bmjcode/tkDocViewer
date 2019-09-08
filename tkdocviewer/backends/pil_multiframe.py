"""Backend for rendering multi-frame images using PIL.

These are internal APIs and subject to change at any time.
"""

try:
    import PIL
except (ImportError):
    PIL = None

from .shared import Backend, BackendError, check_output


class PILMultiframeBackend(Backend):
    """Backend for rendering multi-frame images.

    This backend is used to render image formats supporting multiple
    frames in a single file, such as GIF and TIFF.

    Note: For performance reasons, support for rendering single-frame
    images is built into the DocViewer widget.

    This backend requires the PIL module.
    """

    __slots__ = ["im"]

    def __init__(self, input_path, **kw):
        """Return a new rendering backend."""

        Backend.__init__(self, input_path, **kw)

        if PIL:
            self.im = PIL.Image.open(input_path)

        else:
            raise BackendError(
                "Could not render {0} because PIL is not available "
                "on your system."
                .format(input_path)
            )

    def page_count(self):
        """Return the number of pages in the input file."""

        if hasattr(self.im, "num_frames"):
            # This attribute is available for some formats, like TIFF
            return self.im.num_frames

        else:
            # Count the number of pages manually
            pc = 1
            self.im.seek(0)

            try:
                while True:
                    self.im.seek(self.im.tell() + 1)
                    pc += 1

            except (EOFError):
                # We've seen every frame in the image
                return pc

    def render_page(self, page_num):
        """Render the specified page of the input file."""

        self.im.seek(page_num - 1)
        return self.im.copy()
