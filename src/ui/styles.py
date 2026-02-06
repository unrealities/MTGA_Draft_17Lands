import tkinter
from tkinter import ttk
import sys


class Theme:
    # Modern Dark Palette
    BG_PRIMARY = "#1e1e1e"  # Deep dark background
    BG_SECONDARY = "#252526"  # Slightly lighter for panels/headers
    BG_TERTIARY = "#333333"  # Input fields / Hovers

    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#858585"

    ACCENT = "#007acc"  # VS Code Blue style accent
    ACCENT_HOVER = "#0098ff"

    ERROR = "#f14c4c"
    SUCCESS = "#4ec9b0"

    FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "San Francisco"
    FONT_SIZE_MAIN = 10
    FONT_SIZE_HEADER = 11

    @classmethod
    def apply(cls, root):
        style = ttk.Style(root)
        style.theme_use("clam")

        # Configure General Views
        style.configure(
            ".",
            background=cls.BG_PRIMARY,
            foreground=cls.TEXT_MAIN,
            font=(cls.FONT_FAMILY, cls.FONT_SIZE_MAIN),
            borderwidth=0,
        )

        # Configure Frames (Flat, no borders)
        style.configure("TFrame", background=cls.BG_PRIMARY)
        style.configure("Card.TFrame", background=cls.BG_SECONDARY, relief="flat")

        # Configure Buttons (Modern Flat)
        style.configure(
            "TButton",
            background=cls.BG_TERTIARY,
            foreground=cls.TEXT_MAIN,
            borderwidth=0,
            focusthickness=3,
            focuscolor=cls.ACCENT,
            padding=(10, 5),
        )
        style.map(
            "TButton",
            background=[("active", cls.ACCENT), ("disabled", cls.BG_PRIMARY)],
            foreground=[("disabled", cls.TEXT_MUTED)],
        )

        # Primary Action Button Style
        style.configure(
            "Accent.TButton", background=cls.ACCENT, foreground=cls.TEXT_MAIN
        )
        style.map("Accent.TButton", background=[("active", cls.ACCENT_HOVER)])

        # Treeview (The Tables)
        style.configure(
            "Treeview",
            background=cls.BG_PRIMARY,
            fieldbackground=cls.BG_PRIMARY,
            foreground=cls.TEXT_MAIN,
            borderwidth=0,
            rowheight=30,
            font=(cls.FONT_FAMILY, cls.FONT_SIZE_MAIN),
        )
        style.configure(
            "Treeview.Heading",
            background=cls.BG_SECONDARY,
            foreground=cls.TEXT_MAIN,
            relief="flat",
            font=(cls.FONT_FAMILY, cls.FONT_SIZE_HEADER, "bold"),
            padding=(5, 8),
        )
        style.map("Treeview.Heading", background=[("active", cls.BG_TERTIARY)])

        # Labels
        style.configure("TLabel", background=cls.BG_PRIMARY, foreground=cls.TEXT_MAIN)
        style.configure(
            "Header.TLabel", font=(cls.FONT_FAMILY, 14, "bold"), foreground=cls.ACCENT
        )
        style.configure(
            "SubHeader.TLabel",
            font=(cls.FONT_FAMILY, 12, "bold"),
            foreground=cls.TEXT_MAIN,
        )
        style.configure("Muted.TLabel", foreground=cls.TEXT_MUTED)
        style.configure("Status.TLabel", background=cls.BG_SECONDARY, padding=5)

        # Inputs/OptionMenus
        style.configure(
            "TMenubutton",
            background=cls.BG_TERTIARY,
            foreground=cls.TEXT_MAIN,
            borderwidth=0,
            padding=(5, 2),
        )

        root.configure(bg=cls.BG_PRIMARY)
