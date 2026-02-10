import tkinter
from tkinter import ttk
import sys
import os


class Theme:
    """
    Unified Styling Engine.
    Supports 100% live theme switching by avoiding hardcoded background
    parameters in UI code and using named ttk Styles instead.
    """

    BG_PRIMARY = "#1e1e1e"
    BG_SECONDARY = "#252526"
    BG_TERTIARY = "#333333"
    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#888888"
    ACCENT = "#4dabff"
    SUCCESS = "#00e676"
    ERROR = "#ff5f5f"
    WARNING = "#ffcc00"

    FONT_FAMILY = "Verdana" if sys.platform == "darwin" else "Segoe UI"
    FONT_SIZE_SMALL = 8
    FONT_SIZE_MAIN = 9

    PALETTES = {
        "Dark": {
            "file": "dark_mode.tcl",
            "bg": "#1e1e1e",
            "sec": "#252526",
            "ter": "#333333",
            "txt": "#ffffff",
            "mut": "#888888",
            "acc": "#4dabff",
            "err": "#ff5f5f",
            "suc": "#00e676",
        },
        "Light": {
            "file": "light_mode.tcl",
            "bg": "#ffffff",
            "sec": "#f0f0f0",
            "ter": "#e5e5e5",
            "txt": "#000000",
            "mut": "#757575",
            "acc": "#007acc",
            "err": "#d32f2f",
            "suc": "#388e3c",
        },
        "Forest": {
            "file": "forest.tcl",
            "bg": "#cbd9c7",
            "sec": "#e3ebe1",
            "ter": "#90b589",
            "txt": "#1a2f1c",
            "mut": "#5a7a5e",
            "acc": "#2e7d32",
            "err": "#c0392b",
            "suc": "#2e7d32",
        },
        "Island": {
            "file": "island.tcl",
            "bg": "#c1d7e9",
            "sec": "#dcf0f8",
            "ter": "#64a7d9",
            "txt": "#0d1b2a",
            "mut": "#415a77",
            "acc": "#0077b6",
            "err": "#ef4444",
            "suc": "#10b981",
        },
        "Plains": {
            "file": "plains.tcl",
            "bg": "#f8f6f1",
            "sec": "#fcfbf9",
            "ter": "#f0e6bc",
            "txt": "#2c2825",
            "mut": "#8a8580",
            "acc": "#d4af37",
            "err": "#c0392b",
            "suc": "#27ae60",
        },
        "Swamp": {
            "file": "swamp.tcl",
            "bg": "#2a272a",
            "sec": "#3e3b3e",
            "ter": "#5d405d",
            "txt": "#e0d8e0",
            "mut": "#a090a0",
            "acc": "#c084fc",
            "err": "#cf6679",
            "suc": "#03dac6",
        },
        "Mountain": {
            "file": "mountain.tcl",
            "bg": "#f4d6cf",
            "sec": "#f9e8e3",
            "ter": "#e79c91",
            "txt": "#3b1612",
            "mut": "#8a504a",
            "acc": "#d35400",
            "err": "#ff1744",
            "suc": "#69f0ae",
        },
        "Wastes": {
            "file": "wastes.tcl",
            "bg": "#d6d4d4",
            "sec": "#e8e8e8",
            "ter": "#a9a7a7",
            "txt": "#2b2b2b",
            "mut": "#757575",
            "acc": "#607d8b",
            "err": "#f87171",
            "suc": "#34d399",
        },
    }

    @classmethod
    def apply(cls, root, theme_name="Dark"):
        p = cls.PALETTES.get(theme_name, cls.PALETTES["Dark"])
        cls.BG_PRIMARY, cls.BG_SECONDARY, cls.BG_TERTIARY = p["bg"], p["sec"], p["ter"]
        cls.TEXT_MAIN, cls.TEXT_MUTED, cls.ACCENT = p["txt"], p["mut"], p["acc"]
        cls.ERROR, cls.SUCCESS = p["err"], p["suc"]

        style = ttk.Style(root)
        style.theme_use("clam")

        tcl_file = p["file"]
        paths = [tcl_file, os.path.join("themes", tcl_file)]
        if hasattr(sys, "_MEIPASS"):
            paths.append(os.path.join(sys._MEIPASS, "themes", tcl_file))
        for path in paths:
            if os.path.exists(path):
                try:
                    root.tk.call("source", path)
                    break
                except:
                    pass

        # --- High-Density ttk Style Overrides ---
        style.configure(
            ".",
            background=cls.BG_PRIMARY,
            foreground=cls.TEXT_MAIN,
            font=(cls.FONT_FAMILY, cls.FONT_SIZE_MAIN),
            borderwidth=0,
        )
        style.configure("TFrame", background=cls.BG_PRIMARY)

        # Dashboard Panels (Cards)
        style.configure("Card.TFrame", background=cls.BG_SECONDARY)
        style.configure(
            "Dashboard.TLabel", background=cls.BG_SECONDARY, foreground=cls.TEXT_MAIN
        )
        style.configure(
            "Dashboard.Muted.TLabel",
            background=cls.BG_SECONDARY,
            foreground=cls.TEXT_MUTED,
            font=(cls.FONT_FAMILY, 8),
        )
        style.configure(
            "Status.TLabel",
            background=cls.BG_SECONDARY,
            foreground=cls.ACCENT,
            font=(cls.FONT_FAMILY, 9, "bold"),
        )

        style.configure(
            "Treeview",
            background=cls.BG_SECONDARY,
            fieldbackground=cls.BG_SECONDARY,
            foreground=cls.TEXT_MAIN,
            borderwidth=0,
            rowheight=22,
        )
        style.configure(
            "Treeview.Heading",
            background=cls.BG_TERTIARY,
            foreground=cls.TEXT_MAIN,
            font=(cls.FONT_FAMILY, cls.FONT_SIZE_SMALL, "bold"),
            padding=(5, 2),
        )
        style.map(
            "Treeview",
            background=[("selected", cls.ACCENT)],
            foreground=[("selected", cls.BG_PRIMARY)],
        )

        style.configure("TNotebook", background=cls.BG_PRIMARY, borderwidth=0)
        style.configure("TNotebook.Tab", background=cls.BG_TERTIARY, padding=[12, 3])
        style.map(
            "TNotebook.Tab",
            background=[("selected", cls.BG_SECONDARY)],
            foreground=[("selected", cls.ACCENT)],
        )

        # Force background on standard Tkinter elements
        cls._force_recursive_update(root)
        root.event_generate("<<ThemeChanged>>")

    @classmethod
    def _force_recursive_update(cls, widget):
        """Standardizes non-ttk containers and forces refresh on custom ttk styles."""
        try:
            tk_class = widget.winfo_class()

            # 1. Update standard Tkinter widgets
            if tk_class in ("Tk", "Toplevel", "Frame", "Canvas", "Label"):
                widget.configure(bg=cls.BG_PRIMARY)

            # 2. Force refresh on ttk widgets using custom Dashboard styles
            if hasattr(widget, "cget"):
                current_style = widget.cget("style")
                if current_style:
                    widget.configure(style=current_style)

            for child in widget.winfo_children():
                cls._force_recursive_update(child)
        except:
            pass
