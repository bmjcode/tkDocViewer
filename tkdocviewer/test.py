"""Test cases for the DocViewer widget.

This module contains various test cases for the DocViewer widget.
At the moment these are mainly focused on testing file format support.

Note: The file format tests assume you have all dependencies installed.
"""

import os
import sys
import unittest

try:
    # Python 3
    import tkinter as tk
except (ImportError):
    # Python 2
    import Tkinter as tk

from . import DocViewer


# Absolute path to this file
TEST_PY_PATH = os.path.realpath(__file__)

# Directory containing sample data
SAMPLE_DATA_DIR = os.path.join(os.path.dirname(TEST_PY_PATH), "sample_data")


def get_sample_file(basename):
    """Return the full path to the specified sample file."""

    return os.path.join(SAMPLE_DATA_DIR, os.path.basename(basename))


class DocViewerTest(unittest.TestCase):
    """Test case for the DocViewer widget."""

    def setUp(self):
        """Set up the test case."""

        self.root = tk.Tk()

        status_frame = tk.Frame(self.root)
        status_frame.pack(side="top", fill="x", padx=2, pady=2)

        self.status = tk.Label(status_frame,
                               anchor="e",
                               justify="right")
        self.status.pack(side="right")

        self.path_display = tk.Label(status_frame,
                                     anchor="w",
                                     justify="l")
        self.path_display.pack(side="left")

        self.viewer = DocViewer(self.root)
        self.viewer.pack(side="top", expand=1, fill="both")

        # Update the page count after each page is finished
        self.viewer.bind("<<DocumentStarted>>", self._handle_document_started)
        self.viewer.bind("<<PageFinished>>", self._handle_page_finished)

        # Most of the test files are letter-size pages
        self.viewer.fit_page(8.5, 11 * 3 / 5)

        def close_window():
            self.viewer.cancel_rendering()
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", close_window)

    def tearDown(self):
        """Clean up the test case."""

        self.viewer.cancel_rendering()
        self.root.destroy()

    #
    # Support functions
    #

    def run_rendering_test(self, format_name, sample_file, page_count):
        """Run a standardized rendering test."""

        self.root.wm_title("{0} Rendering Test".format(format_name))
        self.path_display.configure(text=sample_file)

        path = get_sample_file(sample_file)
        self.viewer.display_file(path)

        # Wait for the rendering process to finish
        self.wait_for_render()

        # Confirm the page count is correct
        self.assertEqual(self.viewer.page_count, page_count)

        # Confirm that all pages were successfully rendered
        self.assertEqual(self.viewer.page_count,
                         self.viewer.rendered_page_count)

    def wait_for_render(self):
        """Wait for a file to be rendered."""

        rendering = self.viewer.rendering
        if rendering.get():
            self.root.wait_variable(rendering)

    def wait_for_window(self):
        """Wait for the root window to be closed."""

        self.root.wait_window(self.root)

    #
    # Formats with built-in support
    # List plain text first, then alphabetically by most common extension
    #

    def test_text_rendering(self):
        """Test plain text rendering."""

        self.run_rendering_test("Plain Text", "29888.txt", 1)

    def test_bmp_rendering(self):
        """Test bitmap image rendering."""

        self.run_rendering_test("Bitmap Image", "cover.bmp", 1)

    def test_jpeg_rendering(self):
        """Test JPEG image rendering."""

        self.run_rendering_test("JPEG", "cover.jpg", 1)

    def test_pbm_rendering(self):
        """Test PBM image rendering."""

        self.run_rendering_test("PBM", "cover.pbm", 1)

    def test_pgm_rendering(self):
        """Test PGM image rendering."""

        self.run_rendering_test("PGM", "cover.pgm", 1)

    def test_png_rendering(self):
        """Test PNG image rendering."""

        self.run_rendering_test("PNG", "cover.png", 1)

    def test_pnm_rendering(self):
        """Test PNM image rendering."""

        self.run_rendering_test("PNM", "cover.pnm", 1)

    def test_ppm_rendering(self):
        """Test PPM image rendering."""

        self.run_rendering_test("PPM", "cover.ppm", 1)

    def test_tga_rendering(self):
        """Test TGA image rendering."""

        self.run_rendering_test("TGA", "cover.tga", 1)

    def test_xbm_rendering(self):
        """Test XBM image rendering."""

        self.run_rendering_test("XBM", "cover.xbm", 1)

    #
    # Formats implemented via backends
    # List alphabetically by most common extension
    #

    def test_gif_rendering(self):
        """Test GIF rendering."""

        self.run_rendering_test("GIF", "Rotating_earth_(large).gif", 44)

    def test_pdf_rendering(self):
        """Test PDF rendering."""

        self.run_rendering_test("PDF", "backends.ghostscript.pdf", 6)

    def test_ps_rendering(self):
        """Test Postscript rendering."""

        self.run_rendering_test("Postscript", "backends.ghostscript.ps", 6)

    def test_tiff_rendering(self):
        """Test TIFF rendering."""

        self.run_rendering_test("TIFF", "backends.ghostscript.tiff", 6)

    def test_xps_rendering(self):
        """Test XPS rendering."""

        self.run_rendering_test("XPS", "colorcirc.xps", 1)

    #
    # Internal functions
    #

    def _handle_document_started(self, event):
        """Callback when a document has started rendering."""

        status_text = "Rendering started"
        self.status.configure(text=status_text)

    def _handle_page_finished(self, event):
        """Callback when a page has finished rendering."""

        status_text = "Rendered {0} of {1} page{2}".format(
            self.viewer.rendered_page_count,
            self.viewer.page_count,
            "" if self.viewer.page_count == 1 else "s"
        )
        self.status.configure(text=status_text)
