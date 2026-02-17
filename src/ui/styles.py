"""
src/ui/styles.py
Layered Styling Engine for the MTGA Draft Tool.
Refactored to use ttkbootstrap for modern theming while supporting
a 'System' fallback for native OS look-and-feel.
"""

import tkinter
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import sys
import os
import logging

logger = logging.getLogger(__name__)


class Theme:
    FONT_FAMILY = "Verdana" if sys.platform == "darwin" else "Segoe UI"
    FONT_SIZE_MAIN = 9
    FONT_SIZE_SMALL = 8

    # --- BRIDGE VARIABLES ---
    BG_PRIMARY = "#2b2b2b"
    BG_SECONDARY = "#323232"
    BG_TERTIARY = "#404040"

    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#a0a0a0"

    ACCENT = "#375a7f"
    SUCCESS = "#00bc8c"
    ERROR = "#e74c3c"
    WARNING = "#f39c12"

    # Mapping Palette Names -> ttkbootstrap Themes OR 'native'
    THEME_MAPPING = {
        "System": "native",  # <--- NEW: Uses OS default look
        "Neutral": "darkly",
        "Dark": "darkly",
        "Light": "flatly",
        "Forest": "solar",
        "Island": "superhero",
        "Swamp": "cyborg",
        "Mountain": "united",
        "Plains": "sandstone",
        "Wastes": "vapor",
    }

    # Legacy Registry
    PALETTES = {k: {} for k in THEME_MAPPING.keys()}

    @classmethod
    def get_engine_label(cls, name):
        return name.capitalize()

    @classmethod
    def discover_custom_themes(cls):
        custom_themes = {}
        theme_dir = os.path.join(os.getcwd(), "themes")
        if os.path.exists(theme_dir):
            for f in os.listdir(theme_dir):
                if f.endswith(".tcl"):
                    label = f.replace(".tcl", "").replace("_", " ").capitalize()
                    custom_themes[label] = os.path.join(theme_dir, f)
        return custom_themes

    @classmethod
    def apply(cls, root, palette="Neutral", engine=None, custom_path=""):
        style = ttk.Style()

        # 1. Custom TCL (Legacy)
        if custom_path and os.path.exists(custom_path):
            try:
                root.tk.call("source", custom_path)
                cls._force_recursive_update(root)
                return
            except Exception as e:
                logger.error(f"Failed to load custom theme {custom_path}: {e}")

        # 2. Determine Theme Mode
        target_theme = cls.THEME_MAPPING.get(palette, "darkly")

        if target_theme == "native":
            # --- NATIVE MODE ---
            # Switch to OS native engine using direct TK call to bypass ttkbootstrap wrapper
            # ttkbootstrap's style.theme_use() crashes if passed a non-bootstrap theme name
            native_engine = (
                "aqua"
                if sys.platform == "darwin"
                else "vista" if sys.platform == "win32" else "clam"
            )
            try:
                # Direct Tcl call: package require Tk -> ttk::style theme use "aqua"
                root.tk.call("ttk::style", "theme", "use", native_engine)
            except tkinter.TclError:
                try:
                    root.tk.call("ttk::style", "theme", "use", "clam")
                except:
                    pass

            # Scrape System Colors so the app doesn't break
            # We look up what the OS thinks a Frame background is
            sys_bg = style.lookup("TFrame", "background")
            sys_fg = style.lookup("TLabel", "foreground")
            sys_select_bg = style.lookup("Treeview", "background", ["selected"])

            # Default fallbacks if lookup fails (common on some Linux distros)
            if not sys_bg:
                sys_bg = "#f0f0f0"
            if not sys_fg:
                sys_fg = "#000000"

            cls.BG_PRIMARY = sys_bg
            # Make secondary slightly darker/lighter depending on mode
            # For simplicity in native mode, we often keep them uniform or rely on OS contrast
            cls.BG_SECONDARY = sys_bg
            cls.BG_TERTIARY = "#ffffff"  # Input fields usually white in native

            cls.TEXT_MAIN = sys_fg
            cls.TEXT_MUTED = "gray"

            # Native accents are hard to query, default to standard blue/green
            cls.ACCENT = sys_select_bg if sys_select_bg else "#0078d7"
            cls.SUCCESS = "#008000"
            cls.ERROR = "#ff0000"
            cls.WARNING = "#ffcc00"

        else:
            # --- BOOTSTRAP MODE ---
            try:
                style.theme_use(target_theme)
            except:
                style.theme_use("darkly")

            colors = style.colors
            cls.BG_PRIMARY = colors.bg
            cls.BG_SECONDARY = colors.secondary
            cls.BG_TERTIARY = colors.inputbg

            cls.TEXT_MAIN = colors.fg
            cls.TEXT_MUTED = colors.secondary

            cls.ACCENT = colors.primary
            cls.SUCCESS = colors.success
            cls.ERROR = colors.danger
            cls.WARNING = colors.warning

        # 4. Global Configuration
        style.configure("Treeview", rowheight=22)
        style.configure("TNotebook", borderwidth=0)
        style.configure(".", font=(cls.FONT_FAMILY, cls.FONT_SIZE_MAIN))
        style.configure(
            "Treeview.Heading", font=(cls.FONT_FAMILY, cls.FONT_SIZE_MAIN, "bold")
        )

        # 5. Patch Standard Widgets
        cls._force_recursive_update(root)

        root.event_generate("<<ThemeChanged>>")

    @classmethod
    def _force_recursive_update(cls, widget):
        try:
            tk_class = widget.winfo_class()
            # Standard widgets need manual background updates to match the theme
            if tk_class in ("Tk", "Toplevel", "Frame", "Canvas", "Label", "Labelframe"):
                try:
                    widget.configure(bg=cls.BG_PRIMARY)
                except:
                    pass
            for child in widget.winfo_children():
                cls._force_recursive_update(child)
        except Exception:
            pass
