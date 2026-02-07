import tkinter
from tkinter import ttk
import sys


class Theme:
    # Default Color Variables (will be overwritten by apply)
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
            "BG_PRIMARY": "#1e1e1e",
            "BG_SECONDARY": "#252526",
            "BG_TERTIARY": "#333333",
            "TEXT_MAIN": "#ffffff",
            "TEXT_MUTED": "#858585",
            "ACCENT": "#007acc",
            "ACCENT_HOVER": "#0098ff",
            "ERROR": "#f14c4c",
            "SUCCESS": "#4ec9b0",
        },
        "Light": {
            "BG_PRIMARY": "#f0f0f0",
            "BG_SECONDARY": "#ffffff",
            "BG_TERTIARY": "#e5e5e5",
            "TEXT_MAIN": "#202020",
            "TEXT_MUTED": "#666666",
            "ACCENT": "#007acc",
            "ACCENT_HOVER": "#0098ff",
            "ERROR": "#d32f2f",
            "SUCCESS": "#388e3c",
        },
        "Plains": {
            "BG_PRIMARY": "#fdfbf7",
            "BG_SECONDARY": "#f2efe9",
            "BG_TERTIARY": "#e6e2d8",
            "TEXT_MAIN": "#2c2825",
            "TEXT_MUTED": "#8a8580",
            "ACCENT": "#d4af37",
            "ACCENT_HOVER": "#b8952b",
            "ERROR": "#c0392b",
            "SUCCESS": "#27ae60",
        },
        "Island": {
            "BG_PRIMARY": "#0f172a",
            "BG_SECONDARY": "#1e293b",
            "BG_TERTIARY": "#334155",
            "TEXT_MAIN": "#e2e8f0",
            "TEXT_MUTED": "#94a3b8",
            "ACCENT": "#0ea5e9",
            "ACCENT_HOVER": "#38bdf8",
            "ERROR": "#ef4444",
            "SUCCESS": "#10b981",
        },
        "Swamp": {
            "BG_PRIMARY": "#1a161f",
            "BG_SECONDARY": "#26202e",
            "BG_TERTIARY": "#3b3247",
            "TEXT_MAIN": "#eaddf0",
            "TEXT_MUTED": "#8e8696",
            "ACCENT": "#a855f7",
            "ACCENT_HOVER": "#c084fc",
            "ERROR": "#cf6679",
            "SUCCESS": "#03dac6",
        },
        "Mountain": {
            "BG_PRIMARY": "#261212",
            "BG_SECONDARY": "#381818",
            "BG_TERTIARY": "#4f2121",
            "TEXT_MAIN": "#ffe5e5",
            "TEXT_MUTED": "#bfa3a3",
            "ACCENT": "#ff5722",
            "ACCENT_HOVER": "#ff8a65",
            "ERROR": "#ff5252",
            "SUCCESS": "#69f0ae",
        },
        "Forest": {
            "BG_PRIMARY": "#0b1f11",
            "BG_SECONDARY": "#122e1b",
            "BG_TERTIARY": "#1b4228",
            "TEXT_MAIN": "#e8f5e9",
            "TEXT_MUTED": "#81c784",
            "ACCENT": "#2ecc71",
            "ACCENT_HOVER": "#4ade80",
            "ERROR": "#ff6b6b",
            "SUCCESS": "#a3e635",
        },
        "Wastes": {
            "BG_PRIMARY": "#27272a",
            "BG_SECONDARY": "#3f3f46",
            "BG_TERTIARY": "#52525b",
            "TEXT_MAIN": "#f4f4f5",
            "TEXT_MUTED": "#a1a1aa",
            "ACCENT": "#2dd4bf",
            "ACCENT_HOVER": "#5eead4",
            "ERROR": "#f87171",
            "SUCCESS": "#34d399",
        },
    }

    @classmethod
    def apply(cls, root, theme_name="Dark"):
        """Applies the selected theme to the application."""
        palette = cls.PALETTES.get(theme_name, cls.PALETTES["Dark"])

        for key, value in palette.items():
            setattr(cls, key, value)

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

        # Apply background to root window
        root.configure(bg=cls.BG_PRIMARY)
