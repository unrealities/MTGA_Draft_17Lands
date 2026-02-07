"""
src/ui/components.py

This module contains reusable UI components for the MTGA Draft Tool.
"""

import tkinter
from tkinter import ttk
import requests
import io
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageTk

from src import constants
from src.card_logic import row_color_tag, field_process_sort
from src.ui.styles import Theme


# --- Utility Functions ---
def identify_safe_coordinates(
    root: tkinter.Tk | tkinter.Toplevel,
    window_width: int,
    window_height: int,
    offset_x: int,
    offset_y: int,
) -> Tuple[int, int]:
    """Calculates x, y coordinates to ensure a popup window stays within screen bounds."""
    location_x = 0
    location_y = 0

    try:
        pointer_x = root.winfo_pointerx()
        pointer_y = root.winfo_pointery()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        if pointer_x + offset_x + window_width > screen_width:
            location_x = max(pointer_x - offset_x - window_width, 0)
        else:
            location_x = pointer_x + offset_x

        if pointer_y + offset_y + window_height > screen_height:
            location_y = max(pointer_y - offset_y - window_height, 0)
        else:
            location_y = pointer_y + offset_y

    except Exception:
        location_x = offset_x
        location_y = offset_y

    return location_x, location_y


# --- Components ---


class AutocompleteEntry(tkinter.Entry):
    """A Tkinter Entry widget that provides autocomplete functionality."""

    def __init__(self, master, completion_list: List[str], **kwargs):
        super().__init__(master, **kwargs)
        self.completion_list = sorted(completion_list)
        self.hits_index = -1
        self.hits = []
        self.autocompleted = False
        self.current_text = ""

        self.configure(
            bg=Theme.BG_TERTIARY,
            fg=Theme.TEXT_MAIN,
            insertbackground=Theme.TEXT_MAIN,
            relief="flat",
            highlightthickness=1,
            highlightbackground=Theme.BG_SECONDARY,
            highlightcolor=Theme.ACCENT,
        )

        self.bind("<KeyRelease>", self._act_on_release)
        self.bind("<KeyPress>", self._act_on_press)

    def set_completion_list(self, new_list: List[str]):
        self.completion_list = sorted(new_list)

    def _autocomplete(self):
        self.current_text = self.get().lower()
        if not self.current_text:
            self.hits = []
            self.hits_index = -1
            return

        self.hits = [
            item
            for item in self.completion_list
            if item.lower().startswith(self.current_text)
        ]

        if self.hits:
            self.hits_index = 0
            self._display_autocompletion()
        else:
            self.hits_index = -1
            self.autocompleted = False

    def _display_autocompletion(self):
        if self.hits_index == -1:
            return
        if self.hits:
            cursor_pos = self.index(tkinter.INSERT)
            self.delete(0, tkinter.END)
            self.insert(0, self.hits[self.hits_index])
            self.select_range(cursor_pos, tkinter.END)
            self.icursor(cursor_pos)
            self.autocompleted = True
        else:
            self.autocompleted = False

    def _act_on_release(self, event):
        if event.keysym in ("BackSpace", "Delete"):
            self.autocompleted = False
            return
        if event.keysym not in ("Down", "Up", "Tab", "Right", "Left", "Return"):
            self._autocomplete()

    def _act_on_press(self, event):
        if event.keysym == "Left":
            if self.autocompleted:
                self.autocompleted = False
                return "break"
        if event.keysym in ("Down", "Up", "Tab"):
            if self._selection_present():
                cursor_pos = self.index(tkinter.SEL_FIRST)
                if self.hits and self.current_text == self.get().lower()[0:cursor_pos]:
                    if event.keysym == "Up":
                        self.hits_index = (self.hits_index - 1) % len(self.hits)
                    else:
                        self.hits_index = (self.hits_index + 1) % len(self.hits)
                    self._display_autocompletion()
            else:
                self._autocomplete()
            return "break"
        if event.keysym == "Right":
            if self._selection_present():
                self.selection_clear()
                self.icursor(tkinter.END)
                return "break"
        if event.keysym in ("BackSpace", "Delete"):
            if self.autocompleted:
                self.autocompleted = False

    def _selection_present(self):
        try:
            return self.selection_present()
        except tkinter.TclError:
            return False


class CardToolTip(tkinter.Toplevel):
    """A tooltip window that displays card details, statistics, and images."""

    def __init__(
        self,
        parent_widget,
        card_name: str,
        stats: Dict[str, Dict[str, Any]],
        image_urls: List[str],
        images_enabled: bool,
        scale_factor: float,
        tier_info: Optional[Dict[str, str]] = None,
        archetypes: Optional[List[List]] = None,
        show_colors: Optional[List[str]] = None,
    ):
        super().__init__(parent_widget)
        self.scale_factor = scale_factor
        self.transient(parent_widget.winfo_toplevel())
        self.wm_overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(
            bg=Theme.BG_PRIMARY, highlightthickness=1, highlightbackground=Theme.ACCENT
        )

        def _s(val):
            return int(val * self.scale_factor)

        header_frame = tkinter.Frame(self, bg=Theme.BG_SECONDARY)
        header_frame.pack(fill="x")

        tkinter.Label(
            header_frame,
            text=card_name,
            fg=Theme.TEXT_MAIN,
            bg=Theme.BG_SECONDARY,
            font=(Theme.FONT_FAMILY, _s(11), "bold"),
            padx=_s(10),
            pady=_s(5),
        ).pack(anchor="w")

        content_frame = tkinter.Frame(
            self, bg=Theme.BG_PRIMARY, padx=_s(10), pady=_s(10)
        )
        content_frame.pack(fill="both", expand=True)

        if images_enabled and image_urls:
            try:
                response = requests.get(image_urls[0], timeout=3)
                if response.status_code == 200:
                    img_data = response.content
                    image = Image.open(io.BytesIO(img_data))
                    target_width = _s(220)
                    target_height = _s(307)
                    image.thumbnail(
                        (target_width, target_height), Image.Resampling.LANCZOS
                    )
                    self.tk_image = ImageTk.PhotoImage(image)
                    tkinter.Label(
                        content_frame, image=self.tk_image, bg=Theme.BG_PRIMARY, bd=0
                    ).pack(side="left", padx=(0, _s(15)), anchor="n")
            except Exception:
                pass

        stats_frame = tkinter.Frame(content_frame, bg=Theme.BG_PRIMARY)
        stats_frame.pack(side="left", fill="y", anchor="n")

        available_keys = list(stats.keys())
        keys_to_display = []

        if show_colors:
            priority = ["All Decks"] + show_colors
            seen = set()
            for k in priority:
                if k in available_keys and k not in seen:
                    keys_to_display.append(k)
                    seen.add(k)
        else:
            if "All Decks" in available_keys:
                keys_to_display.append("All Decks")
            for k in available_keys:
                if k == "All Decks":
                    continue
                gihwr = stats[k].get(constants.DATA_FIELD_GIHWR, 0)
                if isinstance(gihwr, (int, float)) and gihwr > 0:
                    keys_to_display.append(k)

        if not keys_to_display:
            keys_to_display = ["All Decks"] if "All Decks" in available_keys else []

        for color_key in keys_to_display:
            data = stats.get(color_key, {})
            tkinter.Label(
                stats_frame,
                text=f"FILTER: {color_key.upper()}",
                fg=Theme.ACCENT,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, _s(10), "bold"),
            ).pack(anchor="w", pady=(0, _s(2)))
            grid_frame = tkinter.Frame(stats_frame, bg=Theme.BG_PRIMARY)
            grid_frame.pack(anchor="w", pady=(0, _s(10)))

            rows = [
                ("GIH WR", constants.DATA_FIELD_GIHWR, "%"),
                ("OH WR", constants.DATA_FIELD_OHWR, "%"),
                ("GP WR", constants.DATA_FIELD_GPWR, "%"),
                ("IWD", constants.DATA_FIELD_IWD, "pp"),
                ("ALSA", constants.DATA_FIELD_ALSA, ""),
                ("ATA", constants.DATA_FIELD_ATA, ""),
            ]

            for i, (label, field_key, suffix) in enumerate(rows):
                val = data.get(field_key, 0)
                val_str = "-" if val == 0 else f"{val}{suffix}"
                tkinter.Label(
                    grid_frame,
                    text=label,
                    fg=Theme.TEXT_MUTED,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, _s(9)),
                ).grid(row=i, column=0, sticky="w", padx=(0, _s(10)))
                tkinter.Label(
                    grid_frame,
                    text=val_str,
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, _s(9), "bold"),
                ).grid(row=i, column=1, sticky="e")

        if archetypes:
            tkinter.Label(
                stats_frame,
                text="TOP ARCHETYPES (GIH WR)",
                fg=Theme.ACCENT,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, _s(10), "bold"),
            ).pack(anchor="w", pady=(_s(5), _s(2)))
            arch_frame = tkinter.Frame(stats_frame, bg=Theme.BG_PRIMARY)
            arch_frame.pack(anchor="w")
            for i, arch in enumerate(archetypes[:3]):
                name = arch[1] if len(arch) > 1 else "??"
                wr = arch[2] if len(arch) > 2 else 0.0
                tkinter.Label(
                    arch_frame,
                    text=f"{name}:",
                    fg=Theme.TEXT_MUTED,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, _s(9)),
                ).grid(row=i, column=0, sticky="w", padx=(0, 5))
                tkinter.Label(
                    arch_frame,
                    text=f"{wr}%",
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, _s(9), "bold"),
                ).grid(row=i, column=1, sticky="e")

        if tier_info:
            comment_frame = tkinter.Frame(
                self, bg=Theme.BG_SECONDARY, padx=_s(5), pady=_s(5)
            )
            comment_frame.pack(fill="x")
            for source, comment in tier_info.items():
                if comment:
                    tkinter.Label(
                        comment_frame,
                        text=f"{source}: {comment}",
                        fg=Theme.TEXT_MAIN,
                        bg=Theme.BG_SECONDARY,
                        wraplength=_s(400),
                        justify="left",
                        font=(Theme.FONT_FAMILY, _s(9), "italic"),
                    ).pack(anchor="w")

        self._position_window(parent_widget)
        parent_widget.bind("<Leave>", self._close)
        self.bind("<Button-1>", self._close)

    def _position_window(self, parent):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(
            parent, w, h, int(25 * self.scale_factor), int(25 * self.scale_factor)
        )
        self.wm_geometry(f"+{x}+{y}")

    def _close(self, event=None):
        self.destroy()


class ModernTreeview(ttk.Treeview):
    """
    A configured Treeview with built-in sorting and coloring support.
    """

    def __init__(
        self,
        parent,
        columns: List[str],
        headers_config: Dict[str, Dict],
        stretch_all: bool = False,
        **kwargs,
    ):
        super().__init__(
            parent, columns=columns, show="headings", style="Treeview", **kwargs
        )

        self.headers_config = headers_config
        self.sort_reverse = {}

        # Initialize Columns
        for col in columns:
            config = headers_config.get(col, {})
            default_anchor = tkinter.CENTER

            if stretch_all:
                # Fill space evenly
                self.column(
                    col,
                    anchor=config.get("anchor", default_anchor),
                    minwidth=50,
                    stretch=True,
                )
            elif col in ["Name", "Card", "Column1", "Set"]:
                default_anchor = tkinter.W
                # Main Name Column: Expand
                self.column(
                    col,
                    anchor=config.get("anchor", default_anchor),
                    minwidth=150,
                    stretch=True,
                    width=200,
                )
            else:
                # Numeric Columns: Compact
                # Use specified width or default to 60
                width = config.get("width", 60)
                self.column(
                    col,
                    anchor=config.get("anchor", default_anchor),
                    minwidth=40,
                    stretch=False,
                    width=width,
                )

            self.heading(col, text=col, command=lambda c=col: self._sort_column(c))

        self._configure_tags()

    def _configure_tags(self):
        for tag, values in constants.ROW_TAGS_COLORS_DICT.items():
            self.tag_configure(tag, background=values[1], foreground=values[2])
        self.tag_configure(
            "bw_odd", background=Theme.BG_PRIMARY, foreground=Theme.TEXT_MAIN
        )
        self.tag_configure(
            "bw_even", background=Theme.BG_SECONDARY, foreground=Theme.TEXT_MAIN
        )

    def _sort_column(self, col: str):
        reverse = self.sort_reverse.get(col, False)
        self.sort_reverse[col] = not reverse
        l = [(self.set(k, col), k) for k in self.get_children("")]

        def sort_key(val_tuple):
            return field_process_sort(val_tuple[0])

        l.sort(key=sort_key, reverse=reverse)
        for index, (val, k) in enumerate(l):
            self.move(k, "", index)
            current_tags = self.item(k)["tags"]
            if not current_tags or (current_tags[0] in ["bw_odd", "bw_even"]):
                new_tag = "bw_odd" if index % 2 == 0 else "bw_even"
                self.item(k, tags=(new_tag,))
