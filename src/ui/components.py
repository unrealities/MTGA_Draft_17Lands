"""
src/ui/components.py
Atomic UI Widgets for the MTGA Draft Tool.
"""

import tkinter
from tkinter import ttk
import requests
import io
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageTk

from src import constants
from src.card_logic import field_process_sort
from src.ui.styles import Theme


def identify_safe_coordinates(
    root: tkinter.Tk | tkinter.Toplevel,
    window_width: int,
    window_height: int,
    offset_x: int,
    offset_y: int,
) -> Tuple[int, int]:
    """Calculates x, y coordinates ensuring popups stay within screen bounds."""
    try:
        pointer_x = root.winfo_pointerx()
        pointer_y = root.winfo_pointery()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        if pointer_x + offset_x + window_width > screen_width:
            location_x = max(pointer_x - offset_x - window_width, 0)
        else:
            location_x = max(pointer_x + offset_x, 0)

        if pointer_y + offset_y + window_height > screen_height:
            location_y = max(pointer_y - offset_y - window_height, 0)
        else:
            location_y = max(pointer_y + offset_y, 0)
    except Exception:
        location_x, location_y = offset_x, offset_y

    return location_x, location_y


class AutocompleteEntry(tkinter.Entry):
    """Entry widget with IDE-style inline suggestions."""

    def __init__(self, master, completion_list: List[str], **kwargs):
        super().__init__(master, **kwargs)
        self.completion_list = sorted(completion_list)
        self.hits = []
        self.hit_index = 0

        self.configure(
            bg=Theme.BG_TERTIARY,
            fg=Theme.TEXT_MAIN,
            insertbackground=Theme.TEXT_MAIN,
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=Theme.BG_SECONDARY,
            highlightcolor=Theme.ACCENT,
        )

        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", lambda e: self.selection_clear())

    def set_completion_list(self, new_list: List[str]):
        self.completion_list = sorted(new_list)

    def _on_key_release(self, event):
        if event.keysym in ("BackSpace", "Delete", "Left", "Control_L", "Control_R"):
            return
        if event.keysym in ("Return", "Tab", "Right"):
            self.icursor(tkinter.END)
            self.selection_clear()
            return
        if event.keysym in ("Up", "Down"):
            if not self.hits:
                return
            direction = 1 if event.keysym == "Down" else -1
            self.hit_index = (self.hit_index + direction) % len(self.hits)
            self._display_suggestion()
            return "break"

        typed_text = self.get()
        if self.selection_present():
            typed_text = self.get()[0 : self.index(tkinter.SEL_FIRST)]

        if not typed_text:
            self.hits = []
            return

        self.hits = [
            item
            for item in self.completion_list
            if item.lower().startswith(typed_text.lower())
        ]
        if self.hits:
            self.hit_index = 0
            self._display_suggestion(typed_text)

    def _display_suggestion(self, typed_prefix=None):
        if not self.hits:
            return
        if typed_prefix is None:
            typed_prefix = (
                self.get()[0 : self.index(tkinter.SEL_FIRST)]
                if self.selection_present()
                else self.get()
            )
        suggestion = self.hits[self.hit_index]
        self.delete(0, tkinter.END)
        self.insert(0, suggestion)
        self.select_range(len(typed_prefix), tkinter.END)
        self.icursor(len(typed_prefix))


class CardToolTip(tkinter.Toplevel):
    """Data-dense popup for MTG cards."""

    def __init__(
        self,
        parent_widget,
        card_name: str,
        stats: Dict[str, Dict[str, Any]],
        image_urls: List[str],
        images_enabled: bool,
        scale: float,
        archetypes: Optional[List[List]] = None,
    ):
        super().__init__(parent_widget)
        self.wm_overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(
            bg=Theme.BG_PRIMARY, highlightthickness=1, highlightbackground=Theme.ACCENT
        )

        header = tkinter.Frame(self, bg=Theme.BG_SECONDARY)
        header.pack(fill="x")
        tkinter.Label(
            header,
            text=card_name,
            bg=Theme.BG_SECONDARY,
            fg=Theme.TEXT_MAIN,
            font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            padx=10,
            pady=5,
        ).pack(side="left")

        body = tkinter.Frame(self, bg=Theme.BG_PRIMARY, padx=10, pady=10)
        body.pack(fill="both", expand=True)

        if images_enabled and image_urls:
            try:
                raw = requests.get(image_urls[0], timeout=2).content
                img = Image.open(io.BytesIO(raw))
                img.thumbnail(
                    (int(200 * scale), int(280 * scale)), Image.Resampling.LANCZOS
                )
                self.tk_img = ImageTk.PhotoImage(img)
                tkinter.Label(body, image=self.tk_img, bg=Theme.BG_PRIMARY).pack(
                    side="left", padx=(0, 10)
                )
            except:
                pass

        stats_f = tkinter.Frame(body, bg=Theme.BG_PRIMARY)
        stats_f.pack(side="left", fill="y")
        best = ["All Decks"] + [
            k
            for k in stats.keys()
            if k != "All Decks" and stats[k].get(constants.DATA_FIELD_GIHWR, 0) > 0
        ]

        for k in best[:3]:
            data = stats.get(k, {})
            tkinter.Label(
                stats_f,
                text=k.upper(),
                fg=Theme.ACCENT,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, int(8 * scale), "bold"),
            ).pack(anchor="w")
            grid = tkinter.Frame(stats_f, bg=Theme.BG_PRIMARY)
            grid.pack(anchor="w", pady=(0, 8))
            rows = [
                ("GIH WR", constants.DATA_FIELD_GIHWR, "%"),
                ("ALSA", constants.DATA_FIELD_ALSA, ""),
            ]
            for i, (lbl, fld, sfx) in enumerate(rows):
                val = data.get(fld, 0.0)
                txt = f"{val}{sfx}" if val > 0 else "-"
                tkinter.Label(
                    grid,
                    text=lbl,
                    fg=Theme.TEXT_MUTED,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, 8),
                ).grid(row=i, column=0, sticky="w")
                tkinter.Label(
                    grid,
                    text=txt,
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, 8, "bold"),
                    padx=10,
                ).grid(row=i, column=1, sticky="e")

        if archetypes:
            tkinter.Label(
                stats_f,
                text="ARCHETYPES",
                fg=Theme.SUCCESS,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, int(7 * scale), "bold"),
            ).pack(anchor="w", pady=(5, 0))
            for arch in archetypes[:2]:
                tkinter.Label(
                    stats_f,
                    text=f"• {arch[0]}: {arch[2]}%",
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, 8),
                ).pack(anchor="w")

        self.update_idletasks()
        tx, ty = identify_safe_coordinates(
            parent_widget, self.winfo_width(), self.winfo_height(), 25, 25
        )
        self.geometry(f"+{tx}+{ty}")
        parent_widget.bind("<Leave>", lambda e: self.destroy(), add="+")
        self.bind("<Button-1>", lambda e: self.destroy())


class ModernTreeview(ttk.Treeview):
    """Treeview optimized for MTG analytics."""

    def __init__(
        self, parent, columns: List[str], headers_config: Dict[str, Dict], **kwargs
    ):
        super().__init__(
            parent, columns=columns, show="headings", style="Treeview", **kwargs
        )
        self.column_sort_state = {col: False for col in columns}

        for col in columns:
            cfg = headers_config.get(col, {})
            anchor = cfg.get("anchor", tkinter.CENTER)
            width = cfg.get("width", 65)
            is_id = col in ("Card", "Name", "Set", "Full Pool")
            self.column(
                col,
                anchor=anchor,
                width=width,
                minwidth=150 if is_id else width,
                stretch=is_id,
            )
            self.heading(
                col, text=col.upper(), command=lambda c=col: self._handle_sort(c)
            )
        self._configure_tags()

    def _configure_tags(self):
        for tag, vals in constants.ROW_TAGS_COLORS_DICT.items():
            self.tag_configure(tag, background=vals[1], foreground=vals[2])
        self.tag_configure("bw_odd", background=Theme.BG_PRIMARY)
        self.tag_configure("bw_even", background=Theme.BG_SECONDARY)

    def _handle_sort(self, col):
        self.column_sort_state[col] = not self.column_sort_state[col]
        rev = self.column_sort_state[col]
        items = []
        for k in self.get_children(""):
            items.append((self.item(k)["values"], k))

        idx = self["columns"].index(col)

        def _key(t):
            p = field_process_sort(t[0][idx])
            try:
                return (1, float(p), str(t[0][0]))
            except:
                return (0, str(p), str(t[0][0]))

        items.sort(key=_key, reverse=rev)
        for i, (v, k) in enumerate(items):
            self.move(k, "", i)
            tags = [t for t in self.item(k, "tags") if t not in ("bw_odd", "bw_even")]
            tags.append("bw_odd" if i % 2 == 0 else "bw_even")
            self.item(k, tags=tuple(tags))
