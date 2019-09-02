"""Demonstration of the viewer widget."""

import os
import sys

try:
    # Python 3
    from tkinter import *
    from tkinter.filedialog import askopenfilename
except (ImportError):
    # Python 2
    from Tkinter import *
    from tkFileDialog import askopenfilename

from .widget import DocViewer


class DocViewerDemo(Frame):
    """A demonstration of the DocViewer widget."""

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master

        button_frame = Frame(self)
        button_frame.pack(side="top", fill="x")

        b_browse = Button(button_frame,
                          text="Open File...",
                          takefocus=0,
                          command=self.browse)
        b_browse.pack(side="left")

        b_close = Button(button_frame,
                         text="Close",
                         takefocus=0,
                         command=self.close)
        b_close.pack(side="left")

        # Create a DocViewer widget
        v = self.doc_viewer = DocViewer(self,
                                        relief="flat",
                                        use_ttk=True)
        v.pack(side="top", expand=1, fill="both")

        # These bind directly to the DocViewer's attributes and methods
        b_wrap = Checkbutton(button_frame,
                             text="Wrap long lines in plain text files",
                             takefocus=0,
                             variable=v.wrap_text,
                             command=v.refresh)
        b_wrap.pack(side="left", padx=(16, 0))

        b_downscale = Checkbutton(button_frame,
                                  text="Downscale PDF files",
                                  takefocus=0,
                                  variable=v.enable_downscaling,
                                  command=v.reload)
        b_downscale.pack(side="left", padx=(8, 0))

        b_force = Checkbutton(button_frame,
                              text="Force display of unrecognized files",
                              takefocus=0,
                              variable=v.force_text_display,
                              command=v.reload)
        b_force.pack(side="left", padx=(8, 0))

        # This comfortably fits most of an 8.5x11" page on a 1366x768 monitor
        v.fit_page(8.5, 11.0 * 3/5)

        # Provide plenty of ways to close the viewer window
        for seq in "<Control-w>", "<Control-q>":
            self.master.bind(seq, self.close)

        # Browse for a file when Ctrl+O is pressed
        self.master.bind("<Control-o>", self.browse)

        # Reload the document when Ctrl+R or F5 is pressed
        for seq in "<Control-r>", "<F5>":
            self.master.bind(seq, v.reload)

        # Cancel rendering when Esc is pressed
        self.master.bind("<Escape>", v.cancel_rendering)

        v.display_text("Press Ctrl+O to browse for a file to display.")
        v.focus_set()

    def browse(self, event=None):
        """Browse for a file to display."""

        path = askopenfilename(parent=self,
                               title="Open File")

        if path:
            self.display_file(os.path.normpath(path))

    def close(self, event=None):
        """Close the window."""

        # Destroy the window
        self.master.destroy()

    def display_file(self, path, pages=None):
        """Display the specified file."""

        self.master.title("tkDocViewer: " + path)
        self.doc_viewer.display_file(path, pages)


def demo():
    """Display a demonstration of the DocViewer widget."""

    root = Tk()
    root.title("tkDocViewer")

    d = DocViewerDemo(root)
    d.pack(side="top", expand=1, fill="both")

    # If a PDF file was named on the command line, display it
    if len(sys.argv) >= 2:
        # First command line argument is the file path
        path = sys.argv[1]

        # Second command line argument (optional) is a list of pages
        if len(sys.argv) >= 3:
            pages = sys.argv[2]
        else:
            pages = None

        d.display_file(path, pages)

    else:
        # Browse for a file to display after the main loop has started
        root.after(500, d.browse)

    root.mainloop()


if __name__ == "__main__":
    demo()
