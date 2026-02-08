import tkinter
from tkinter import ttk
import sys
import os
from src.logger import create_logger

logger = create_logger()


class Theme:
    # Default Color Variables
    BG_PRIMARY = "#1e1e1e"
    BG_SECONDARY = "#252526"
    BG_TERTIARY = "#333333"

    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#858585"

    ACCENT = "#007acc"
    ACCENT_HOVER = "#0098ff"

    ERROR = "#f14c4c"
    SUCCESS = "#4ec9b0"

    FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "San Francisco"
    FONT_SIZE_MAIN = 10
    FONT_SIZE_HEADER = 11

    # Defined Palettes
    PALETTES = {
        "Dark": {
            "file": "dark_mode.tcl",
            "BG_PRIMARY": "#333333",
            "BG_SECONDARY": "#3d3d3d",
            "BG_TERTIARY": "#3d3d3d",
            "TEXT_MAIN": "#ffffff",
            "TEXT_MUTED": "#858585",
            "ACCENT": "#007fff",
            "ACCENT_HOVER": "#0098ff",
            "ERROR": "#f14c4c",
            "SUCCESS": "#4ec9b0",
        },
        "Light": {
            "file": "light_mode.tcl",
            "BG_PRIMARY": "#ffffff",
            "BG_SECONDARY": "#f0f0f0",
            "BG_TERTIARY": "#e5e5e5",
            "TEXT_MAIN": "#000000",
            "TEXT_MUTED": "#666666",
            "ACCENT": "#007fff",
            "ACCENT_HOVER": "#0098ff",
            "ERROR": "#d32f2f",
            "SUCCESS": "#388e3c",
        },
        "Plains": {
            "file": "plains.tcl",
            "BG_PRIMARY": "#f8f6f1",
            "BG_SECONDARY": "#fcfbf9",
            "BG_TERTIARY": "#fcfbf9",
            "TEXT_MAIN": "#2c2825",
            "TEXT_MUTED": "#8a8580",
            "ACCENT": "#f0e6bc",
            "ACCENT_HOVER": "#d4af37",
            "ERROR": "#c0392b",
            "SUCCESS": "#27ae60",
        },
        "Island": {
            "file": "island.tcl",
            "BG_PRIMARY": "#c1d7e9",
            "BG_SECONDARY": "#dcf0f8",
            "BG_TERTIARY": "#dcf0f8",
            "TEXT_MAIN": "#0d1b2a",
            "TEXT_MUTED": "#415a77",
            "ACCENT": "#64a7d9",
            "ACCENT_HOVER": "#38bdf8",
            "ERROR": "#ef4444",
            "SUCCESS": "#10b981",
        },
        "Swamp": {
            "file": "swamp.tcl",
            "BG_PRIMARY": "#2a272a",
            "BG_SECONDARY": "#3e3b3e",
            "BG_TERTIARY": "#3e3b3e",
            "TEXT_MAIN": "#e0d8e0",
            "TEXT_MUTED": "#a090a0",
            "ACCENT": "#89718b",
            "ACCENT_HOVER": "#c084fc",
            "ERROR": "#cf6679",
            "SUCCESS": "#03dac6",
        },
        "Mountain": {
            "file": "mountain.tcl",
            "BG_PRIMARY": "#f4d6cf",
            "BG_SECONDARY": "#f9e8e3",
            "BG_TERTIARY": "#f9e8e3",
            "TEXT_MAIN": "#3b1612",
            "TEXT_MUTED": "#8a504a",
            "ACCENT": "#e79c91",
            "ACCENT_HOVER": "#ff8a65",
            "ERROR": "#ff5252",
            "SUCCESS": "#69f0ae",
        },
        "Forest": {
            "file": "forest.tcl",
            "BG_PRIMARY": "#cbd9c7",
            "BG_SECONDARY": "#e3ebe1",
            "BG_TERTIARY": "#e3ebe1",
            "TEXT_MAIN": "#1a2f1c",
            "TEXT_MUTED": "#5a7a5e",
            "ACCENT": "#90b589",
            "ACCENT_HOVER": "#4ade80",
            "ERROR": "#ff6b6b",
            "SUCCESS": "#a3e635",
        },
        "Wastes": {
            "file": "wastes.tcl",
            "BG_PRIMARY": "#d6d4d4",
            "BG_SECONDARY": "#e8e8e8",
            "BG_TERTIARY": "#e8e8e8",
            "TEXT_MAIN": "#2b2b2b",
            "TEXT_MUTED": "#757575",
            "ACCENT": "#a9a7a7",
            "ACCENT_HOVER": "#5eead4",
            "ERROR": "#f87171",
            "SUCCESS": "#34d399",
        },
    }

    @classmethod
    def apply(cls, root, theme_name="Dark"):
        """Applies the selected theme to the application."""
        palette = cls.PALETTES.get(theme_name, cls.PALETTES["Dark"])

        # Update Python Color Constants
        for key, value in palette.items():
            if key != "file":
                setattr(cls, key, value)

        # Configure Tkinter Styles
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

        # Configure Frames
        style.configure("TFrame", background=cls.BG_PRIMARY)
        style.configure("Card.TFrame", background=cls.BG_SECONDARY, relief="flat")

        # Configure Buttons
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

        # Treeview (Tables)
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

        # Mapping to prevent color shift on focus loss
        # We explicitly set selected background for !focus to match selected
        style.map(
            "Treeview",
            background=[("selected", cls.ACCENT)],
            foreground=[("selected", cls.TEXT_MAIN)],
        )

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

        # Text Entries
        style.configure(
            "TEntry",
            fieldbackground=cls.BG_TERTIARY,
            foreground=cls.TEXT_MAIN,
            insertcolor=cls.TEXT_MAIN,
            borderwidth=0,
            padding=5,
        )

        # Checkboxes
        style.configure(
            "TCheckbutton", background=cls.BG_PRIMARY, foreground=cls.TEXT_MAIN
        )
        style.map("TCheckbutton", background=[("active", cls.BG_PRIMARY)])

        # Load TCL File (if exists, to override specific OS behaviors)
        filename = palette.get("file", "dark_mode.tcl")
        paths_to_check = [filename, os.path.join("themes", filename)]
        if hasattr(sys, "_MEIPASS"):
            paths_to_check.append(os.path.join(sys._MEIPASS, "themes", filename))

        for tcl_file in paths_to_check:
            if os.path.exists(tcl_file):
                try:
                    root.tk.call("source", tcl_file)
                    break
                except Exception as e:
                    logger.error(f"Failed to load theme {tcl_file}: {e}")

        # Force Root Background Update
        root.configure(bg=cls.BG_PRIMARY)

        # Update Toplevels recursively
        for widget in root.winfo_children():
            if isinstance(widget, tkinter.Toplevel):
                widget.configure(bg=cls.BG_PRIMARY)
                # Force redraw of child widgets
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Frame):
                        # Re-applying the style name forces a refresh
                        current_style = child.cget("style") or "TFrame"
                        child.configure(style=current_style)

    @staticmethod
    def _recursive_configure(widget, **kwargs):
        try:
            if isinstance(widget, (tkinter.Toplevel, tkinter.Tk)):
                widget.configure(**kwargs)
        except Exception:
            pass
