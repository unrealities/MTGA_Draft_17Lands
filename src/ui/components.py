"""
src/ui/components.py
Atomic UI Widgets for the MTGA Draft Tool.
"""

import tkinter
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import requests
import io
import math
import re
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageTk
import threading
import hashlib
import os

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
            location_x = max(pointer_x - offset_x - window_width - 10, 0)
        else:
            location_x = max(pointer_x + offset_x, 0)

        if pointer_y + offset_y + window_height > screen_height:
            location_y = max(pointer_y - offset_y - window_height - 10, 0)
        else:
            location_y = max(pointer_y + offset_y, 0)
    except Exception:
        location_x, location_y = offset_x, offset_y

    return location_x, location_y


class CollapsibleFrame(ttk.Frame):
    """
    A custom frame that allows its contents to be collapsed and expanded vertically.
    """

    def __init__(self, parent, title="", expanded=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.expanded = expanded

        # Header container
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill="x", expand=False)

        # Toggle Icon
        self.toggle_label = ttk.Label(
            self.header_frame,
            text="▼" if expanded else "▶",
            width=2,
            font=(Theme.FONT_FAMILY, 10),
            foreground=Theme.ACCENT,
            cursor="hand2",
        )
        self.toggle_label.pack(side="left", padx=(5, 5), pady=(5, 5))

        # Title Label
        self.title_label = ttk.Label(
            self.header_frame,
            text=title.upper(),
            cursor="hand2",
            font=(Theme.FONT_FAMILY, 10, "bold"),
            foreground=Theme.TEXT_MAIN,
        )
        self.title_label.pack(side="left", pady=(5, 5))

        self.content_frame = ttk.Frame(self)
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))

        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.toggle_label.configure(foreground=Theme.ACCENT)
            self.title_label.configure(foreground=Theme.TEXT_MAIN)

        # Bind clicks to the toggle method
        self.header_frame.bind("<Button-1>", self.toggle)
        self.toggle_label.bind("<Button-1>", self.toggle)
        self.title_label.bind("<Button-1>", self.toggle)

    def toggle(self, event=None):
        self.expanded = not self.expanded
        if self.expanded:
            self.toggle_label.config(text="▼")
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
        else:
            self.toggle_label.config(text="▶")
            self.content_frame.pack_forget()


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
    """Data-dense popup for MTG cards with async, cached image loading."""

    # Set up a local cache directory for images
    IMAGE_CACHE_DIR = os.path.join(os.getcwd(), "Temp", "Images")

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

        # Ensure cache directory exists
        if not os.path.exists(self.IMAGE_CACHE_DIR):
            os.makedirs(self.IMAGE_CACHE_DIR)

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

        # Placeholder for the image label (packed immediately)
        self.img_label = tkinter.Label(body, bg=Theme.BG_PRIMARY)
        if images_enabled and image_urls:
            self.img_label.pack(side="left", padx=(0, 10))
            # Fetch image asynchronously so we don't freeze the UI
            self._load_image_async(image_urls[0], scale)

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

    def _load_image_async(self, url: str, scale: float):
        """Fetches the image on a background thread to prevent UI freezing."""

        def fetch_and_resize():
            try:
                # 1. Create a safe filename using a hash of the URL
                safe_name = hashlib.md5(url.encode("utf-8")).hexdigest() + ".jpg"
                cache_path = os.path.join(self.IMAGE_CACHE_DIR, safe_name)

                # 2. Check local disk cache first
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as f:
                        raw = f.read()
                else:
                    # 3. Download and cache if missing
                    raw = requests.get(url, timeout=2).content
                    with open(cache_path, "wb") as f:
                        f.write(raw)

                # 4. Process Image
                img = Image.open(io.BytesIO(raw))
                img.thumbnail(
                    (int(200 * scale), int(280 * scale)), Image.Resampling.LANCZOS
                )

                # 5. Push UI update back to the main thread
                self.after(0, lambda: self._apply_image(img))
            except Exception as e:
                # Fail silently, the tooltip just won't show the image
                pass

        # Start the background thread
        threading.Thread(target=fetch_and_resize, daemon=True).start()

    def _apply_image(self, img):
        """Safely applies the image to the widget on the main thread."""
        if self.winfo_exists():
            self.tk_img = ImageTk.PhotoImage(img)
            self.img_label.configure(image=self.tk_img)


class ModernTreeview(ttk.Treeview):
    """A high-density Treeview with built-in sorting logic."""

    def __init__(self, parent, columns, **kwargs):
        super().__init__(
            parent, columns=columns, show="headings", style="Treeview", **kwargs
        )
        self.column_sort_state = {col: False for col in columns}
        self.active_fields = []  # Injected by Manager
        self.base_labels = {}  # Store original names for arrows
        self._setup_headers(columns)
        self._setup_row_colors()

    def _setup_headers(self, columns):
        from src.constants import COLUMN_FIELD_LABELS

        for col in columns:
            if col == "add_btn":
                self.heading(col, text="+")
                self.column(col, width=30, stretch=False, anchor=tkinter.CENTER)
                continue

            if "TIER" in col:
                label = col
            else:
                label = COLUMN_FIELD_LABELS.get(col, str(col).upper()).split(":")[0]

            self.base_labels[col] = label
            width = 200 if col == "name" else 65
            self.heading(col, text=label, command=lambda c=col: self._handle_sort(c))
            self.column(
                col, width=width, anchor=tkinter.W if col == "name" else tkinter.CENTER
            )

    def _setup_row_colors(self):
        """Premium tailored row tags for the tables."""
        self.tag_configure("white_card", background="#f4f4f5", foreground="#18181b")
        self.tag_configure("blue_card", background="#e0f2fe", foreground="#0c4a6e")
        self.tag_configure("black_card", background="#3f3f46", foreground="#f4f4f5")
        self.tag_configure("red_card", background="#fee2e2", foreground="#7f1d1d")
        self.tag_configure("green_card", background="#dcfce7", foreground="#14532d")
        self.tag_configure("gold_card", background="#fef3c7", foreground="#78350f")
        self.tag_configure("colorless_card", background="#e4e4e7", foreground="#27272a")

        # Elite tags
        self.tag_configure("elite_bomb", background="#78350f", foreground="#fde047")
        self.tag_configure("high_fit", background="#0c4a6e", foreground="#7dd3fc")

    def _handle_sort(self, col):
        from src.card_logic import field_process_sort

        self.column_sort_state[col] = not self.column_sort_state[col]
        rev = self.column_sort_state[col]

        # Apply the visual arrow to the active column, reset the others
        for c in self["columns"]:
            if c in self.base_labels:
                if c == col:
                    arrow = "▼" if rev else "▲"
                    self.heading(c, text=f"{self.base_labels[c]} {arrow}")
                else:
                    self.heading(c, text=self.base_labels[c])

        items = [(self.item(k)["values"], k) for k in self.get_children("")]

        try:
            col_idx = list(self["columns"]).index(col)
        except ValueError:
            return

        def _key(t):
            p = field_process_sort(t[0][col_idx])
            if isinstance(p, tuple):
                return (p[0], p[1], str(t[0][0]).lower())

            try:
                return (1, float(p), str(t[0][0]).lower())
            except:
                return (0, str(p), str(t[0][0]).lower())

        # Sort the items and re-insert them with fresh zebra striping
        items.sort(key=_key, reverse=rev)
        for i, (v, k) in enumerate(items):
            self.move(k, "", i)
            tags = [t for t in self.item(k, "tags") if t not in ("bw_odd", "bw_even")]
            tags.append("bw_odd" if i % 2 == 0 else "bw_even")
            self.item(k, tags=tuple(tags))


class DynamicTreeviewManager(ttk.Frame):
    """
    Wrapper that manages a ModernTreeview.
    Handles column persistence and dynamic reconfiguration.
    """

    def __init__(
        self,
        parent,
        view_id,
        configuration,
        on_update_callback,
        static_columns=None,
        **kwargs,
    ):
        super().__init__(parent)
        self.view_id = view_id
        self.config = configuration
        self.on_update = on_update_callback
        self.static_columns = static_columns
        self.tree = None
        self.kwargs = kwargs

        self.rebuild(trigger_callback=False)

    def rebuild(self, trigger_callback=True):
        if self.tree:
            self.tree.destroy()

        if self.static_columns:
            self.active_fields = list(self.static_columns)
        else:
            self.active_fields = self.config.settings.column_configs.get(
                self.view_id, ["name", "value", "gihwr"]
            )

        display_cols = (
            self.active_fields
            if self.static_columns
            else self.active_fields + ["add_btn"]
        )

        self.tree = ModernTreeview(self, columns=display_cols, **self.kwargs)
        self.tree.active_fields = (
            self.active_fields
        )  # Inject into widget for dashboard access
        self.tree.pack(fill="both", expand=True)

        if not self.static_columns:
            # Bind both standard right-click and Mac Ctrl-click
            self.tree.bind("<Button-3>", self._show_context_menu)
            self.tree.bind("<Control-Button-1>", self._show_context_menu)
            self.tree.bind("<Button-1>", self._handle_click)

        if trigger_callback:
            self.on_update()

    def _show_context_menu(self, event):
        """Header context menu for removing or adding columns."""
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        col_id = self.tree.identify_column(event.x)
        try:
            idx = int(col_id.replace("#", "")) - 1
        except:
            return

        if idx >= len(self.active_fields):
            return

        field = self.active_fields[idx]
        menu = tkinter.Menu(self, tearoff=0)

        # 1. Removal Logic
        if field != "name":
            menu.add_command(
                label=f"Remove '{field.upper()}'",
                command=lambda i=idx: self._remove_column(i),
            )
            menu.add_separator()

        # 2. Add Column Submenu
        add_m = tkinter.Menu(menu, tearoff=0)
        menu.add_cascade(label="Add Column", menu=add_m)
        from src.constants import COLUMN_FIELD_LABELS

        for f, label in COLUMN_FIELD_LABELS.items():
            if f not in self.active_fields:
                add_m.add_command(
                    label=label, command=lambda new_f=f: self._add_column(new_f)
                )

        # Tier lists
        from src.tier_list import TierList

        tier_files = TierList.retrieve_files()
        if tier_files:
            add_m.add_separator()
            for idx, (set_code, lbl, _, _) in enumerate(tier_files):
                f = f"TIER{idx}"
                if f not in self.active_fields:
                    label = f"TIER: {lbl} ({set_code})"
                    add_m.add_command(
                        label=label, command=lambda new_f=f: self._add_column(new_f)
                    )

        # 3. Utility Options
        menu.add_separator()
        menu.add_command(label="Reset to Defaults", command=self._reset_defaults)

        menu.post(event.x_root, event.y_root)

    def _handle_click(self, event):
        """Handles the '+' button left-click."""
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return
        col_id = self.tree.identify_column(event.x)
        try:
            idx = int(col_id.replace("#", "")) - 1
        except:
            return
        if idx == len(self.active_fields):
            self._show_add_menu(event)

    def _show_add_menu(self, event):
        menu = tkinter.Menu(self, tearoff=0)
        from src.constants import COLUMN_FIELD_LABELS

        added = False
        for f, label in COLUMN_FIELD_LABELS.items():
            if f not in self.active_fields:
                menu.add_command(
                    label=label, command=lambda new_f=f: self._add_column(new_f)
                )
                added = True

        # Tier lists
        from src.tier_list import TierList

        tier_files = TierList.retrieve_files()
        if tier_files:
            menu.add_separator()
            for idx, (set_code, lbl, _, _) in enumerate(tier_files):
                f = f"TIER{idx}"
                if f not in self.active_fields:
                    label = f"TIER: {lbl} ({set_code})"
                    menu.add_command(
                        label=label, command=lambda new_f=f: self._add_column(new_f)
                    )
                    added = True

        if added:
            menu.post(event.x_root, event.y_root)

    def _add_column(self, field):
        if len(self.active_fields) >= 15:
            return
        self.active_fields.append(field)
        self._persist()

    def _remove_column(self, idx):
        if len(self.active_fields) <= 1:
            return  # Must keep one column
        self.active_fields.pop(idx)
        self._persist()

    def _reset_defaults(self):
        """Restores the standard pro-level column set."""
        self.active_fields = ["name", "value", "gihwr"]
        self._persist()

    def _persist(self):
        """Saves configuration and triggers a visual rebuild."""
        from src.configuration import write_configuration

        self.config.settings.column_configs[self.view_id] = self.active_fields
        write_configuration(self.config)
        self.rebuild(trigger_callback=True)


class SignalMeter(tb.Frame):
    """
    Compact Signal Visualizer.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas_height = 100
        self.bar_width = 20
        self.gap = 4
        self.scores = {}

        self.canvas = tb.Canvas(
            self, height=self.canvas_height, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if not self.winfo_exists():
            return
        self.canvas.configure(bg=Theme.BG_PRIMARY)
        self.color_map = {
            "W": (Theme.WARNING, "White"),
            "U": (Theme.ACCENT, "Blue"),
            "B": (Theme.BG_TERTIARY, "Black"),
            "R": (Theme.ERROR, "Red"),
            "G": (Theme.SUCCESS, "Green"),
        }
        self.redraw()

        self.color_map = {
            "W": (Theme.WARNING, "White"),
            "U": (Theme.ACCENT, "Blue"),
            "B": (Theme.BG_TERTIARY, "Black"),
            "R": (Theme.ERROR, "Red"),
            "G": (Theme.SUCCESS, "Green"),
        }

    def update_values(self, scores: Dict[str, float]):
        self.scores = scores
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10:
            return

        colors = ["W", "U", "B", "R", "G"]
        total_content_width = (len(colors) * self.bar_width) + (
            (len(colors) - 1) * self.gap
        )
        start_x = (w - total_content_width) / 2

        max_val = max(max(self.scores.values(), default=1), 20)
        scale = (self.canvas_height - 18) / max_val

        for i, code in enumerate(colors):
            val = self.scores.get(code, 0.0)
            x = start_x + (i * (self.bar_width + self.gap))
            bar_h = val * scale

            color = self.color_map[code][0]
            if code == "B" and color == Theme.BG_TERTIARY:
                color = "#555555"

            # Draw Bar
            self.canvas.create_rectangle(
                x,
                self.canvas_height - bar_h - 12,
                x + self.bar_width,
                self.canvas_height - 12,
                fill=color,
                outline="",
            )

            # Label below
            self.canvas.create_text(
                x + self.bar_width / 2,
                self.canvas_height - 5,
                text=code,
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_FAMILY, 9, "bold"),
            )


class ManaCurvePlot(tb.Frame):
    """
    Compact Curve Plot.
    """

    def __init__(self, parent, ideal_distribution: List[int], **kwargs):
        super().__init__(parent, **kwargs)
        self.ideal = ideal_distribution
        self.current = [0] * 7

        self.canvas_height = 100  # Reduced height
        self.canvas = tb.Canvas(
            self, height=self.canvas_height, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if not self.winfo_exists():
            return
        self.canvas.configure(bg=Theme.BG_PRIMARY)
        self.redraw()

        self.bar_width = 14
        self.gap = 2

    def update_curve(self, current_distribution: List[int]):
        self.current = current_distribution
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10:
            return

        total_bars = len(self.current)
        total_content_width = (total_bars * self.bar_width) + (
            (total_bars - 1) * self.gap
        )
        start_x = (w - total_content_width) / 2

        max_val = max(max(self.current), max(self.ideal), 5)
        scale = (self.canvas_height - 25) / max_val

        for i, count in enumerate(self.current):
            x = start_x + (i * (self.bar_width + self.gap))

            # Ideal (Ghost)
            target = self.ideal[i] if i < len(self.ideal) else 0
            if target > 0:
                t_h = target * scale
                self.canvas.create_rectangle(
                    x,
                    self.canvas_height - t_h - 10,
                    x + self.bar_width,
                    self.canvas_height - 10,
                    outline=Theme.TEXT_MUTED,
                    width=1,
                    dash=(2, 2),
                )

            # Actual
            bar_h = count * scale
            color = Theme.ACCENT
            if count > target + 1:
                color = Theme.ERROR
            elif count < target and target > 0:
                color = Theme.WARNING
            elif count >= target:
                color = Theme.SUCCESS

            self.canvas.create_rectangle(
                x,
                self.canvas_height - bar_h - 10,
                x + self.bar_width,
                self.canvas_height - 10,
                fill=color,
                outline="",
            )

            if count > 0:
                self.canvas.create_text(
                    x + self.bar_width / 2,
                    self.canvas_height - bar_h - 17,
                    text=str(count),
                    fill=Theme.TEXT_MAIN,
                    font=(Theme.FONT_FAMILY, 9, "bold"),
                )

            # Axis Label
            lbl = str(i) if i < 6 else "6+"
            self.canvas.create_text(
                x + self.bar_width / 2,
                self.canvas_height - 4,
                text=lbl,
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_FAMILY, 8),
            )


class TypePieChart(tb.Frame):
    """
    Compact Donut chart.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas_size = 100
        self.canvas = tb.Canvas(
            self,
            height=self.canvas_size,
            width=self.canvas_size,
            bg=Theme.BG_PRIMARY,
            highlightthickness=0,
        )
        self.canvas.pack(side=LEFT, padx=10)
        self.legend_frame = tb.Frame(self)
        self.legend_frame.pack(side=LEFT, fill=Y, padx=5)

        self.counts = {"Creatures": 0, "Non-Creatures": 0, "Lands": 0}
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if not self.winfo_exists():
            return
        self.canvas.configure(bg=Theme.BG_PRIMARY)
        self.redraw()

    def update_counts(self, creatures, non_creatures, lands):
        self.counts["Creatures"] = creatures
        self.counts["Non-Creatures"] = non_creatures
        self.counts["Lands"] = lands
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        # Update Legend
        for w in self.legend_frame.winfo_children():
            w.destroy()

        # Legend Logic
        items = [
            ("Crea", self.counts["Creatures"], Theme.SUCCESS),
            ("Spell", self.counts["Non-Creatures"], Theme.ACCENT),
            ("Land", self.counts["Lands"], Theme.BG_TERTIARY),
        ]

        for lbl, count, col in items:
            row = tb.Frame(self.legend_frame)
            row.pack(anchor="w")
            tb.Label(row, text="●", foreground=col, font=(None, 6)).pack(side=LEFT)
            tb.Label(row, text=f"{lbl}: {count}", font=(Theme.FONT_FAMILY, 10)).pack(
                side=LEFT, padx=2
            )

        # Chart Logic
        total = sum(self.counts.values())
        if total == 0:
            return

        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        radius = (self.canvas_size / 2) - 2
        current_angle = 90

        data = [
            (self.counts["Creatures"], Theme.SUCCESS),
            (self.counts["Non-Creatures"], Theme.ACCENT),
            (self.counts["Lands"], Theme.BG_TERTIARY),
        ]

        for count, color in data:
            if count == 0:
                continue
            extent = (count / total) * 360
            self.canvas.create_arc(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                start=current_angle,
                extent=-extent,
                fill=color,
                outline="",
                style="pieslice",
            )
            current_angle -= extent

        self.canvas.create_oval(
            cx - radius / 2,
            cy - radius / 2,
            cx + radius / 2,
            cy + radius / 2,
            fill=Theme.BG_PRIMARY,
            outline="",
        )
        self.canvas.create_text(
            cx,
            cy,
            text=str(total),
            fill=Theme.TEXT_MAIN,
            font=(Theme.FONT_FAMILY, 9, "bold"),
        )


class ScrolledFrame(tb.Frame):
    """
    A horizontally scrollable container.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # 1. Scrollbar at bottom
        self.scrollbar = tb.Scrollbar(
            self, orient="horizontal", bootstyle="secondary-round"
        )
        self.scrollbar.pack(side="bottom", fill="x")

        # 2. Canvas
        self.canvas = tb.Canvas(self, bg=Theme.BG_PRIMARY, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)

        # 3. Link Scrollbar
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.canvas.xview)

        # 4. The Inner Frame (Holds the content)
        self.scrollable_frame = tb.Frame(self.canvas)

        # 5. Create Window in Canvas
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        # 6. Bind Events
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, height=event.height)


class CardPile(tb.Frame):
    """
    Vertical column for cards.
    """

    def __init__(self, parent, title, app_instance, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app_instance

        tb.Label(
            self,
            text=title,
            font=(Theme.FONT_FAMILY, 10, "bold"),
            bootstyle="inverse-secondary",
            anchor="center",
            padding=5,
        ).pack(fill=X, pady=(0, 2))

        self.container = tb.Frame(self)
        self.container.pack(fill=BOTH, expand=True)

    def add_card(self, card_data):
        name = card_data[constants.DATA_FIELD_NAME]
        mana_cost = card_data.get(constants.DATA_FIELD_MANA_COST, "")
        count = card_data.get(constants.DATA_FIELD_COUNT, 1)

        found_colors = set(re.findall(r"[WUBRG]", mana_cost or ""))

        pip_order = ["W", "U", "B", "R", "G"]
        sorted_colors = sorted(
            list(found_colors),
            key=lambda x: pip_order.index(x) if x in pip_order else 99,
        )

        is_gold = len(sorted_colors) > 1
        is_colorless = len(sorted_colors) == 0

        hex_map = {
            "W": "#f8f6f1",
            "U": "#3498db",
            "B": "#2c3e50",
            "R": "#e74c3c",
            "G": "#00bc8c",
        }
        style_map = {
            "W": "warning",
            "U": "info",
            "B": "dark",
            "R": "danger",
            "G": "success",
        }

        chip_frame = tb.Frame(self.container)
        chip_frame.pack(fill=X, pady=1, padx=2)

        display_text = f"{count}x {name}" if count > 1 else name

        if is_gold:
            gold_bg = "#d4af37"

            lbl = tb.Label(
                chip_frame,
                text=display_text,
                font=(Theme.FONT_FAMILY, 10),
                foreground="#000000",
                background=gold_bg,
                anchor="w",
                padding=(5, 2),
            )
            lbl.pack(side=LEFT, fill=BOTH, expand=True)

            cv = tb.Canvas(
                chip_frame, width=12, height=20, bg=gold_bg, highlightthickness=0
            )
            cv.pack(side=RIGHT, fill=Y)

            num_colors = len(sorted_colors)
            if num_colors > 0:
                stripe_h = 20 / num_colors
                for i, code in enumerate(sorted_colors):
                    fill_col = hex_map.get(code, "#000")
                    cv.create_rectangle(
                        0,
                        i * stripe_h,
                        12,
                        (i + 1) * stripe_h,
                        fill=fill_col,
                        outline="",
                    )

            self._bind_tooltip(lbl, card_data)
            self._bind_tooltip(cv, card_data)

        elif is_colorless:
            lbl = tb.Label(
                chip_frame,
                text=display_text,
                bootstyle="inverse-secondary",
                font=(Theme.FONT_FAMILY, 10),
                anchor="w",
                padding=(5, 2),
            )
            lbl.pack(fill=X)
            self._bind_tooltip(lbl, card_data)

        else:
            c = sorted_colors[0]
            s = style_map.get(c, "secondary")

            if c == "W":
                lbl = tb.Label(
                    chip_frame,
                    text=display_text,
                    foreground="#000000",
                    background="#f0f0f0",
                    font=(Theme.FONT_FAMILY, 10),
                    anchor="w",
                    padding=(5, 2),
                )
            else:
                lbl = tb.Label(
                    chip_frame,
                    text=display_text,
                    bootstyle=f"inverse-{s}",
                    font=(Theme.FONT_FAMILY, 10),
                    anchor="w",
                    padding=(5, 2),
                )
            lbl.pack(fill=X)
            self._bind_tooltip(lbl, card_data)

    def _bind_tooltip(self, widget, card_data):
        widget.bind("<Enter>", lambda e: self._show_tooltip(widget, card_data))

    def _show_tooltip(self, widget, card_data):
        stats = card_data.get(constants.DATA_FIELD_DECK_COLORS, {})
        CardToolTip(
            widget,
            card_data[constants.DATA_FIELD_NAME],
            stats,
            card_data.get(constants.DATA_SECTION_IMAGES, []),
            self.app.configuration.features.images_enabled,
            constants.UI_SIZE_DICT.get(self.app.configuration.settings.ui_size, 1.0),
        )
