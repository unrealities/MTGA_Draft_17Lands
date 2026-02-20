"""
src/ui/styles.py
Layered Styling Engine for the MTGA Draft Tool.
Refactored to cleanly handle ttkbootstrap, native OS themes, and custom TCL files
without cross-polluting the state.
"""

import tkinter
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import sys
import os
import re
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
        "System": "native",
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
    def apply(cls, root, palette="Neutral", engine=None, custom_path="", scale=1.0):
        style = ttk.Style()
        is_custom_loaded = False

        # 1. Custom TCL Loading
        if custom_path and os.path.exists(custom_path):
            try:
                root.tk.call("source", custom_path)
                is_custom_loaded = True
            except Exception as e:
                error_msg = str(e)
                # If the script failed because the theme is already in memory, catch it and activate it!
                if "already exists" in error_msg:
                    match = re.search(r"Theme (\w+) already exists", error_msg)
                    theme_name = (
                        match.group(1)
                        if match
                        else os.path.basename(custom_path).replace(".tcl", "")
                    )
                    try:
                        style.theme_use(theme_name)
                        is_custom_loaded = True
                    except Exception as inner_e:
                        logger.error(
                            f"Failed to activate existing custom theme {theme_name}: {inner_e}"
                        )
                else:
                    logger.error(f"Failed to load custom theme {custom_path}: {e}")

        # 2. Extract Colors & Set Engine
        if is_custom_loaded:
            # Dynamically scrape the colors that the TCL file applied to the style engine
            sys_bg = style.lookup("TFrame", "background") or "#2b2b2b"
            sys_fg = style.lookup("TLabel", "foreground") or "#ffffff"
            sys_input = style.lookup("TEntry", "fieldbackground") or "#404040"
            sys_select_bg = (
                style.lookup("Treeview", "background", ["selected"]) or "#d4af37"
            )

            cls.BG_PRIMARY = sys_bg
            cls.BG_SECONDARY = sys_bg
            cls.BG_TERTIARY = sys_input

            cls.TEXT_MAIN = sys_fg
            cls.TEXT_MUTED = "gray"

            cls.ACCENT = sys_select_bg
            cls.SUCCESS = "#00bc8c"
            cls.ERROR = "#e74c3c"
            cls.WARNING = "#f39c12"

        else:
            target_theme = cls.THEME_MAPPING.get(palette, "darkly")

            if target_theme == "native":
                # NATIVE MODE
                native_engine = (
                    "aqua"
                    if sys.platform == "darwin"
                    else "vista" if sys.platform == "win32" else "clam"
                )
                try:
                    root.tk.call("ttk::style", "theme", "use", native_engine)
                except tkinter.TclError:
                    try:
                        root.tk.call("ttk::style", "theme", "use", "clam")
                    except:
                        pass

                sys_bg = style.lookup("TFrame", "background") or "#f0f0f0"
                sys_fg = style.lookup("TLabel", "foreground") or "#000000"
                sys_select_bg = (
                    style.lookup("Treeview", "background", ["selected"]) or "#0078d7"
                )

                cls.BG_PRIMARY = sys_bg
                cls.BG_SECONDARY = sys_bg
                cls.BG_TERTIARY = "#ffffff"
                cls.TEXT_MAIN = sys_fg
                cls.TEXT_MUTED = "gray"
                cls.ACCENT = sys_select_bg
                cls.SUCCESS = "#008000"
                cls.ERROR = "#ff0000"
                cls.WARNING = "#ffcc00"

            else:
                # BOOTSTRAP MODE
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

        # 3. Global Configuration (Applies regardless of theme engine)
        row_height = max(22, int(22 * scale))
        style.configure("Treeview", rowheight=row_height)
        style.configure("TNotebook", borderwidth=0)

        # Increase PanedWindow Sash (Draggable Splitter) visibility and grab area globally
        # We use direct tk calls to bypass ttkbootstrap's Style parsing bug for internal elements
        try:
            root.tk.call(
                "ttk::style",
                "configure",
                "Sash",
                "-sashthickness",
                8,
                "-relief",
                "flat",
            )
            if not is_custom_loaded:
                root.tk.call(
                    "ttk::style", "configure", "Sash", "-background", cls.BG_TERTIARY
                )
        except Exception as e:
            logger.error(f"Failed to configure sash: {e}")

        # Only override the header font if the custom theme didn't explicitly set one
        if not is_custom_loaded:
            main_font_size = max(8, int(cls.FONT_SIZE_MAIN * scale))
            style.configure(".", font=(cls.FONT_FAMILY, main_font_size))
            style.configure(
                "Treeview.Heading", font=(cls.FONT_FAMILY, main_font_size, "bold")
            )

        # 4. Patch Standard Native OS Widgets to match the theme colors
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
