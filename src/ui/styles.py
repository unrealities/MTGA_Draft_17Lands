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
from typing import Any, Optional
from tkinter import font as tkfont
from src.constants import RESOURCE_DIR

logger = logging.getLogger(__name__)

import tkinter.ttk as tk_ttk

# --- MONKEY PATCH TKINTER.TTK TO PREVENT TTKBOOTSTRAP NATIVE THEME CRASH ---
_orig_element_create = tk_ttk.Style.element_create


def _safe_element_create(self, elementname, etype, *args, **kw):
    try:
        _orig_element_create(self, elementname, etype, *args, **kw)
    except tkinter.TclError as e:
        if "Duplicate element" in str(e):
            pass
        else:
            raise


tk_ttk.Style.element_create = _safe_element_create


class Theme:
    FONT_FAMILY = (
        "Helvetica Neue"
        if sys.platform == "darwin"
        else ("Ubuntu" if sys.platform == "linux" else "Segoe UI")
    )
    FONT_SIZE_MAIN = 10
    FONT_SIZE_SMALL = 9
    current_scale: float = 1.0
    _last_scale = None

    @classmethod
    def scaled_font(
        cls, size: int, weight: Optional[str] = None, family: Optional[str] = None
    ) -> tuple:
        """Returns a scaled font tuple."""
        f_family = family if family else cls.FONT_FAMILY
        f_size = max(4, int(size * cls.current_scale))
        if weight:
            return (f_family, f_size, weight)
        return (f_family, f_size)

    @classmethod
    def scaled_val(cls, val: Any) -> Any:
        """Returns a scaled integer value or sequence of values."""
        if isinstance(val, (list, tuple)):
            return type(val)(int(v * cls.current_scale) for v in val)
        try:
            return int(val * cls.current_scale)
        except (TypeError, ValueError):
            return val

    # --- BRIDGE VARIABLES ---
    BG_PRIMARY = "#0f172a"
    BG_SECONDARY = "#1e293b"
    BG_TERTIARY = "#334155"

    TEXT_MAIN = "#f8fafc"
    TEXT_MUTED = "#94a3b8"

    ACCENT = "#3b82f6"
    SUCCESS = "#10b981"
    ERROR = "#ef4444"
    WARNING = "#f59e0b"

    # Mapping Palette Names -> ttkbootstrap Themes OR 'native'
    THEME_MAPPING = {
        "System": "native",
        "Neutral": "superhero",
        "Dark": "cyborg",
        "Light": "flatly",
        "Forest": "solar",
        "Island": "morph",
        "Swamp": "darkly",
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
        theme_dir = os.path.join(RESOURCE_DIR, "themes")
        if os.path.exists(theme_dir):
            for f in os.listdir(theme_dir):
                if f.endswith(".tcl"):
                    label = f.replace(".tcl", "").replace("_", " ").capitalize()
                    custom_themes[label] = os.path.join(theme_dir, f)
        return custom_themes

    @classmethod
    def apply(cls, root, palette="Neutral", engine=None, custom_path="", scale=1.0):
        scale_changed = cls._last_scale != scale
        cls._last_scale = scale
        cls.current_scale = scale
        style = ttk.Style()
        is_custom_loaded = False

        # 1. Custom TCL Loading
        if custom_path and os.path.exists(custom_path):
            try:
                root.tk.call("source", custom_path)
                is_custom_loaded = True
            except Exception as e:
                error_msg = str(e)
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
            target_theme = cls.THEME_MAPPING.get(palette, "cyborg")

            if target_theme == "native":
                # --- NATIVE OS MODE ---
                native_engine = (
                    "aqua"
                    if sys.platform == "darwin"
                    else "vista" if sys.platform == "win32" else "clam"
                )
                try:
                    current = root.tk.call("ttk::style", "theme", "use")
                    if current != native_engine or scale_changed:
                        root.tk.call("ttk::style", "theme", "use", native_engine)
                except tkinter.TclError:
                    try:
                        root.tk.call("ttk::style", "theme", "use", "clam")
                    except:
                        pass

                # Extract True Native Colors (Dynamic Light/Dark mode support)
                if sys.platform == "darwin":
                    cls.BG_PRIMARY = "systemTextBackgroundColor"
                    cls.BG_SECONDARY = "systemAlternatingContentBackgroundColor"
                    cls.BG_TERTIARY = "systemWindowBackgroundColor"
                    cls.TEXT_MAIN = "systemTextColor"
                    cls.TEXT_MUTED = "systemPlaceholderTextColor"
                    cls.ACCENT = "systemControlAccentColor"
                elif sys.platform == "win32":
                    cls.BG_PRIMARY = "SystemWindow"
                    cls.BG_SECONDARY = "#f0f0f0"  # Subtle grey for windows
                    cls.BG_TERTIARY = "SystemButtonFace"
                    cls.TEXT_MAIN = "SystemWindowText"
                    cls.TEXT_MUTED = "SystemGrayText"
                    cls.ACCENT = "SystemHighlight"
                else:
                    cls.BG_PRIMARY = style.lookup("TFrame", "background") or "#ffffff"
                    cls.BG_SECONDARY = "#f5f5f5"  # Subtle grey fallback
                    cls.BG_TERTIARY = "#e0e0e0"
                    cls.TEXT_MAIN = style.lookup("TLabel", "foreground") or "#000000"
                    cls.TEXT_MUTED = "gray"
                    cls.ACCENT = (
                        style.lookup("Treeview", "background", ["selected"])
                        or "#0078d7"
                    )

                cls.SUCCESS = "#10b981"
                cls.ERROR = "#ef4444"
                cls.WARNING = "#f59e0b"

            else:
                # --- BOOTSTRAP MODE ---
                current_theme = (
                    style.theme.name if hasattr(style, "theme") and style.theme else ""
                )
                if current_theme != target_theme or scale_changed:
                    try:
                        style.theme_use(target_theme)
                    except:
                        style.theme_use("cyborg")

                sys_bg = style.lookup("TFrame", "background")
                colors = style.colors

                cls.BG_PRIMARY = sys_bg if sys_bg else colors.bg

                # Ensure zebra striping uses a highly subtle background tint
                if getattr(style.theme, "type", "dark") == "light":
                    cls.BG_SECONDARY = colors.light
                else:
                    cls.BG_SECONDARY = colors.dark

                cls.BG_TERTIARY = colors.inputbg

                cls.TEXT_MAIN = colors.fg
                cls.TEXT_MUTED = colors.secondary

                cls.ACCENT = colors.primary
                cls.SUCCESS = colors.success
                cls.ERROR = colors.danger
                cls.WARNING = colors.warning

        # 3. Global Configuration
        main_font_size = max(5, int(cls.FONT_SIZE_MAIN * scale))

        try:
            test_font = tkfont.Font(
                root=root, family=cls.FONT_FAMILY, size=main_font_size
            )
            linespace = test_font.metrics("linespace")
            padding = 8 if sys.platform == "darwin" else 14
            row_height = linespace + int(padding * scale)
        except Exception as e:
            base_row_height = 26 if sys.platform == "darwin" else 32
            row_height = max(10, int(base_row_height * scale))

        style.configure("Treeview", rowheight=row_height, borderwidth=0, relief="flat")
        style.configure("TNotebook", borderwidth=0)

        # Make splitters invisible but thick enough to grab easily
        try:
            import tkinter.ttk as tk_ttk

            safe_style = tk_ttk.Style(root)

            if not is_custom_loaded:
                safe_style.configure(
                    "TPanedwindow", background=cls.BG_PRIMARY, borderwidth=0
                )

                if sys.platform == "darwin" and target_theme == "native":
                    try:
                        safe_style.element_create("Sash", "from", "default")
                    except Exception:
                        pass

                if target_theme != "native":
                    try:
                        safe_style.element_create(
                            "Horizontal.Sash.hsash", "from", "clam"
                        )
                        safe_style.element_create("Vertical.Sash.vsash", "from", "clam")
                    except Exception:
                        pass

                for sash in ["Sash", "Horizontal.Sash", "Vertical.Sash"]:
                    safe_style.configure(
                        sash,
                        sashthickness=8,
                        sashrelief="flat",
                        gripcount=0,
                        borderwidth=0,
                        background=cls.BG_PRIMARY,
                        bordercolor=cls.BG_PRIMARY,
                        lightcolor=cls.BG_PRIMARY,
                        darkcolor=cls.BG_PRIMARY,
                    )
                    safe_style.map(
                        sash,
                        background=[("active", cls.ACCENT)],
                        bordercolor=[("active", cls.ACCENT)],
                        lightcolor=[("active", cls.ACCENT)],
                        darkcolor=[("active", cls.ACCENT)],
                    )

                safe_style.configure("TSeparator", background=cls.BG_PRIMARY)

        except Exception as e:
            logger.error(f"Failed to configure sash: {e}")

        if not is_custom_loaded:
            style.configure(".", font=(cls.FONT_FAMILY, main_font_size))
            style.configure(
                "Treeview.Heading", font=(cls.FONT_FAMILY, main_font_size, "bold")
            )

            style.configure(
                "TNotebook.Tab",
                padding=cls.scaled_val([12, 6]),
                font=(cls.FONT_FAMILY, main_font_size, "bold"),
            )
            style.map(
                "TNotebook.Tab",
                foreground=[("selected", cls.ACCENT), ("!selected", cls.TEXT_MAIN)],
                background=[("selected", cls.BG_PRIMARY)],
            )

        style.configure(
            "Card.TFrame", background=cls.BG_PRIMARY, relief="flat", borderwidth=0
        )
        root.configure(bg=cls.BG_PRIMARY)
        root.event_generate("<<ThemeChanged>>")
