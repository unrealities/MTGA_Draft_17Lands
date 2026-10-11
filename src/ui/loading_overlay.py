"""
src/ui/loading_overlay.py
Provides a blocking, visually appealing loading screen for heavy background operations.
"""

from tkinter import ttk
from src.ui.styles import Theme


class LoadingOverlay(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(style="TFrame")

        self.center_box = ttk.Frame(
            self, padding=Theme.scaled_val(40), style="Card.TFrame"
        )
        self.center_box.place(relx=0.5, rely=0.45, anchor="center")

        self.title_lbl = ttk.Label(
            self.center_box,
            text="Loading Draft",
            font=Theme.scaled_font(16, "bold"),
            bootstyle="primary",
        )
        self.title_lbl.pack(pady=(0, Theme.scaled_val(10)))

        self.status_lbl = ttk.Label(
            self.center_box, text="Initializing...", font=Theme.scaled_font(11)
        )
        self.status_lbl.pack(pady=(0, Theme.scaled_val(20)))

        self.progress = ttk.Progressbar(
            self.center_box, mode="indeterminate", length=Theme.scaled_val(300)
        )
        self.progress.pack()

    def show(self, title):
        """Displays the overlay over the parent window."""
        self.title_lbl.config(text=title)
        self.progress.start(15)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def hide(self):
        """Hides the overlay and stops animations."""
        self.progress.stop()
        self.place_forget()

    def update_status(self, text):
        """Updates the sub-text of the loading screen."""
        self.status_lbl.config(text=text)
        # A forced synchronous redraw only matters while the overlay is on
        # screen. The deck builder also reports progress during a draft, when
        # this is hidden, and each forced redraw stalled the UI 0.3-0.5 s.
        if self.winfo_ismapped():
            self.update_idletasks()
