"""
src/ui/components.py
Atomic UI Widgets for the MTGA Draft Tool.
"""

import tkinter
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import requests, io, math, re, threading, hashlib, os
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor
from src import constants
from src.card_logic import field_process_sort
from src.ui.styles import Theme


def identify_safe_coordinates(root, window_width, window_height, offset_x, offset_y):
    try:
        pointer_x, pointer_y = root.winfo_pointerx(), root.winfo_pointery()
        screen_width, screen_height = (
            root.winfo_screenwidth(),
            root.winfo_screenheight(),
        )
        if pointer_x + offset_x + window_width > screen_width:
            location_x = max(pointer_x - offset_x - window_width - 10, 0)
        else:
            location_x = max(pointer_x + offset_x, 0)
        if pointer_y + offset_y + window_height > screen_height:
            location_y = max(pointer_y - offset_y - window_height - 10, 0)
        else:
            location_y = max(pointer_y + offset_y, 0)
        return location_x, location_y
    except:
        return offset_x, offset_y


class AutoScrollbar(ttk.Scrollbar):
    """A scrollbar that hides itself if it's not needed. Only works within the grid geometry manager."""

    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(lo, hi)

    def pack(self, **kw):
        raise tkinter.TclError("AutoScrollbar cannot use pack. Use grid instead.")

    def place(self, **kw):
        raise tkinter.TclError("AutoScrollbar cannot use place. Use grid instead.")


class CollapsibleFrame(ttk.Frame):
    def __init__(
        self,
        parent,
        title="",
        expanded=True,
        configuration=None,
        setting_key=None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.configuration, self.setting_key = configuration, setting_key
        if self.configuration and self.setting_key:
            self.expanded = self.configuration.settings.collapsible_states.get(
                self.setting_key, expanded
            )
        else:
            self.expanded = expanded
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill="x", expand=False)
        self.toggle_label = ttk.Label(
            self.header_frame,
            text="▼" if self.expanded else "▶",
            width=2,
            font=(Theme.FONT_FAMILY, 10),
            bootstyle="primary",
            cursor="hand2",
        )
        self.toggle_label.pack(side="left", padx=(5, 5), pady=(5, 5))
        self.title_label = ttk.Label(
            self.header_frame,
            text=title.upper(),
            cursor="hand2",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        )
        self.title_label.pack(side="left", pady=(5, 5))
        self.content_frame = ttk.Frame(self)
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
        self._apply_bindings()
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _apply_bindings(self):
        try:
            if self.winfo_exists():
                for w in [self.header_frame, self.toggle_label, self.title_label]:
                    w.bind("<Button-1>", self.toggle)
        except:
            pass

    def _on_theme_change(self, event=None):
        try:
            if self.winfo_exists():
                self._apply_bindings()
        except:
            pass

    def toggle(self, event=None):
        if not self.winfo_exists():
            return
        self.expanded = not self.expanded
        if self.expanded:
            self.toggle_label.config(text="▼")
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
        else:
            self.toggle_label.config(text="▶")
            self.content_frame.pack_forget()
        if self.configuration and self.setting_key:
            self.configuration.settings.collapsible_states[self.setting_key] = (
                self.expanded
            )
            from src.configuration import write_configuration

            write_configuration(self.configuration)


class AutocompleteEntry(tb.Entry):
    def __init__(self, master, completion_list, **kwargs):
        super().__init__(master, **kwargs)
        self.completion_list = sorted(completion_list)
        self.hits, self.hit_index = [], 0
        self.configure(bootstyle="primary")
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", lambda e: self.selection_clear())

    def set_completion_list(self, new_list):
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
            self.hit_index = (
                self.hit_index + (1 if event.keysym == "Down" else -1)
            ) % len(self.hits)
            self._display_suggestion()
            return "break"
        typed = (
            self.get()[0 : self.index(tkinter.SEL_FIRST)]
            if self.selection_present()
            else self.get()
        )
        if not typed:
            self.hits = []
            return
        self.hits = [
            i for i in self.completion_list if i.lower().startswith(typed.lower())
        ]
        if self.hits:
            self.hit_index = 0
            self._display_suggestion(typed)

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
    IMAGE_CACHE_DIR = os.path.join(constants.TEMP_FOLDER, "Images")
    _active_tooltip = None
    _image_executor = ThreadPoolExecutor(max_workers=4)

    @classmethod
    def create(cls, parent, card, images_enabled, scale):
        """Factory method ensures only one tooltip exists globally and avoids flickering loops."""
        if cls._active_tooltip and cls._active_tooltip.winfo_exists():
            cls._active_tooltip.destroy()
            cls._active_tooltip = None
        cls._active_tooltip = cls(parent, card, images_enabled, scale)

    def __init__(self, parent, card, images_enabled, scale):
        super().__init__(parent)
        # --- 1. Basic Land Filter ---
        # Prevent tooltips from appearing for Basic Lands to reduce clutter
        card_types = card.get("types", [])
        card_name = card.get("name", "")
        if (
            "Land" in card_types and "Basic" in card_types
        ) or card_name in constants.BASIC_LANDS:
            self.withdraw()
            self.destroy()
            return

        self.wm_overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(
            bg=Theme.BG_PRIMARY, highlightthickness=1, highlightbackground=Theme.ACCENT
        )

        try:
            if not os.path.exists(self.IMAGE_CACHE_DIR):
                os.makedirs(self.IMAGE_CACHE_DIR)
        except Exception:
            pass

        name, stats, urls, tags, rarity = (
            card.get("name", "Unknown"),
            card.get("deck_colors", {}),
            card.get("image", []),
            card.get("tags", []),
            card.get("rarity", "common").capitalize(),
        )
        h = tb.Frame(self, bootstyle="secondary")
        h.pack(fill="x")
        rc = (
            "#f97316"
            if rarity == "Mythic"
            else (
                "#eab308"
                if rarity == "Rare"
                else "#38bdf8" if rarity == "Uncommon" else None
            )
        )
        tb.Label(
            h,
            text=name,
            bootstyle="inverse-secondary",
            font=(Theme.FONT_FAMILY, int(13 * scale), "bold"),
            padding=(10, 6),
        ).pack(side="left")

        lbl_rarity = tb.Label(
            h,
            text=rarity,
            bootstyle="inverse-secondary",
            font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            padding=(10, 0),
        )
        if rc:
            lbl_rarity.configure(foreground=rc)
        lbl_rarity.pack(side="right")

        b = tb.Frame(self, padding=12)
        b.pack(fill="both", expand=True)

        # --- 2. Image Container ---
        # Reserves space immediately so the tooltip doesn't expand/jump when the image loads
        if images_enabled:
            img_w = int(240 * scale)
            img_h = int(335 * scale)

            self.img_frame = tb.Frame(b, width=img_w, height=img_h)
            self.img_frame.pack_propagate(False)
            self.img_frame.pack(side="left", padx=(0, 15), anchor="n")

            self.img_label = tb.Label(self.img_frame)
            self.img_label.pack(fill="both", expand=True)

            if urls:
                self._load_image_async(urls[0], scale)

        sf = tb.Frame(b)
        sf.pack(side="left", fill="both", expand=True, anchor="n")
        gs = stats.get("All Decks", {})
        wr, iwd, smp = gs.get("gihwr", 0.0), gs.get("iwd", 0.0), gs.get("samples", 0)
        tb.Label(
            sf,
            text="GLOBAL PERFORMANCE",
            bootstyle="primary",
            font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
        ).pack(anchor="w")
        gf = tb.Frame(sf)
        gf.pack(anchor="w", fill="x", pady=(4, 12))

        def fp(v, i=False):
            return "-" if not v else (f"{v:+.1f}%" if i else f"{v:.1f}%")

        def fn(v):
            return "-" if not v else (f"{v:.2f}" if isinstance(v, float) else f"{v:,}")

        mt = [
            [
                ("GIH WR:", fp(wr), Theme.SUCCESS if wr >= 55.0 else Theme.TEXT_MAIN),
                (
                    "IWD:",
                    fp(iwd, True),
                    Theme.ACCENT if iwd >= 3.0 else Theme.TEXT_MAIN,
                ),
            ],
            [
                ("ALSA:", fn(gs.get("alsa", 0.0)), Theme.TEXT_MAIN),
                ("ATA:", fn(gs.get("ata", 0.0)), Theme.TEXT_MAIN),
            ],
            [("Games:", f"{fn(smp)}", Theme.TEXT_MAIN), ("", "", "")],
        ]
        for ri, row in enumerate(mt):
            for ci, (lbl, val, col) in enumerate(row):
                if not lbl:
                    continue
                tb.Label(
                    gf,
                    text=lbl,
                    font=(Theme.FONT_FAMILY, int(9 * scale)),
                ).grid(row=ri, column=ci * 2, sticky="w", padx=(0, 6))
                tb.Label(
                    gf,
                    text=val,
                    foreground=col,
                    font=(Theme.FONT_FAMILY, int(9 * scale), "bold"),
                ).grid(row=ri, column=ci * 2 + 1, sticky="w", padx=(0, 20))
        va = sorted(
            [
                k
                for k in stats.keys()
                if k != "All Decks" and stats[k].get("gihwr", 0) > 0
            ],
            key=lambda k: stats[k].get("samples", 0),
            reverse=True,
        )
        if va:
            tb.Label(
                sf,
                text="ARCHETYPE PLAY SHARE",
                bootstyle="success",
                font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            ).pack(anchor="w")
            for k in va[:10]:
                rf = tb.Frame(sf)
                rf.pack(anchor="w", fill="x", pady=(2, 0))
                tb.Label(
                    rf,
                    text=f"• {constants.COLOR_NAMES_DICT.get(k, k)} ({k}):",
                    font=(Theme.FONT_FAMILY, int(9 * scale)),
                ).pack(side="left")
                tb.Label(
                    rf,
                    text=f" {stats[k].get('gihwr', 0.0):.1f}% WR",
                    foreground=(
                        None if stats[k].get("gihwr", 0.0) < 55.0 else Theme.SUCCESS
                    ),
                    font=(Theme.FONT_FAMILY, int(9 * scale), "bold"),
                ).pack(side="left")
        if tags:
            tb.Label(
                sf,
                text="CARD ROLES",
                bootstyle="warning",
                font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            ).pack(anchor="w", pady=(12, 4))
            tb.Label(
                sf,
                text="   ".join(
                    [constants.TAG_VISUALS.get(t, t.capitalize()) for t in tags]
                ),
                font=(Theme.FONT_FAMILY, int(9 * scale), "bold"),
                wraplength=int(280 * scale),
                justify="left",
            ).pack(anchor="w")

        # Anchor to the mouse position AT THE TIME OF CREATION
        self._mouse_x = parent.winfo_pointerx()
        self._mouse_y = parent.winfo_pointery()
        self._reposition()

        # Bind closing interactions securely
        parent.bind("<Leave>", self._close, add="+")
        self.bind("<Button-1>", self._close)
        self.bind("<Leave>", self._close)

    def _close(self, event=None):
        if self.winfo_exists():
            self.destroy()

    def _reposition(self):
        """Calculates bounds using the static initial mouse position so the tooltip doesn't teleport."""
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return

        try:
            self.update_idletasks()

            # Re-verify existence after idle tasks in case a <Leave> event instantly destroyed it
            if not self.winfo_exists():
                return

            ww = self.winfo_width()
            wh = self.winfo_height()

            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()

            # Offset aggressively to prevent cursor hovering over the tooltip immediately, causing a rapid <Leave> flicker
            offset_x, offset_y = 35, 25

            if self._mouse_x + offset_x + ww > sw:
                tx = max(self._mouse_x - offset_x - ww - 10, 0)
            else:
                tx = max(self._mouse_x + offset_x, 0)

            if self._mouse_y + offset_y + wh > sh:
                ty = max(self._mouse_y - offset_y - wh - 10, 0)
            else:
                ty = max(self._mouse_y + offset_y, 0)

            self.geometry(f"+{tx}+{ty}")
        except tkinter.TclError:
            pass

    def _load_image_async(self, u, s):
        if "scryfall" in u:
            u = u.replace("/small/", "/large/").replace("/normal/", "/large/")
        self._image_executor.submit(self._fetch_and_apply_image, u, s)

    def _fetch_and_apply_image(self, u, s):
        """Moved the core logic into a clean worker method"""
        try:
            sn = hashlib.md5(u.encode("utf-8")).hexdigest() + ".jpg"
            cp = os.path.join(self.IMAGE_CACHE_DIR, sn)
            if os.path.exists(cp):
                with open(cp, "rb") as fi:
                    r = fi.read()
            else:
                r = requests.get(u, timeout=5).content
                with open(cp, "wb") as fi:
                    fi.write(r)

            im = Image.open(io.BytesIO(r))
            im.thumbnail((int(240 * s), int(335 * s)), Image.Resampling.LANCZOS)

            # Safely route back to Tkinter Main Thread
            if hasattr(self, "winfo_exists"):
                try:
                    self.after(
                        0,
                        lambda: self._apply_image(im) if self.winfo_exists() else None,
                    )
                except RuntimeError:
                    pass
        except Exception:
            pass

    def _apply_image(self, im):
        if hasattr(self, "winfo_exists") and self.winfo_exists():
            self.tk_img = ImageTk.PhotoImage(im)
            self.img_label.configure(image=self.tk_img)
            # The window height just expanded; recalculate safe bounds to flip it upward if needed
            self._reposition()


class ModernTreeview(ttk.Treeview):
    def __init__(self, parent, columns, view_id=None, config=None, **kwargs):
        super().__init__(
            parent, columns=columns, show="headings", style="Treeview", **kwargs
        )
        self.view_id = view_id
        self.config = config
        self.sort_group = self._get_sort_group(view_id)

        self.active_fields = []
        self.base_labels = {}
        self.column_sort_state = {i: False for i in columns}
        self.active_sort_column = None

        # Load saved sort state from the global configuration
        if self.config and self.view_id:
            if not hasattr(self.config.settings, "table_sort_states"):
                setattr(self.config.settings, "table_sort_states", {})

            saved_state = self.config.settings.table_sort_states.get(
                self.sort_group, {}
            )
            if saved_state:
                self.active_sort_column = saved_state.get("column")
                # Dynamic index handling means we just map the name ("gihwr"), regardless of where it is
                if self.active_sort_column in self.column_sort_state:
                    self.column_sort_state[self.active_sort_column] = saved_state.get(
                        "reverse", False
                    )
                else:
                    self.active_sort_column = None

        self._drag_col = None
        self._drag_start_x = 0
        self._dragging = False
        self._setup_headers(columns)
        self._setup_row_colors()
        self._setup_column_drag()

        self._pulse_step = 0
        self._last_picked_items = set()
        self._animate_picked_row()

    def _animate_picked_row(self):
        if not self.winfo_exists():
            return

        current_picked = set(
            item
            for item in self.get_children("")
            if "picked" in self.item(item, "tags")
        )

        # Reset animation if new items are picked (e.g. data refreshed)
        if current_picked != self._last_picked_items:
            self._pulse_step = 0
            self._last_picked_items = current_picked

        if current_picked:
            # Sequence for ~1 second (15 frames @ 65ms)
            bg_colors = [
                "#14532d",
                "#166534",
                "#15803d",
                "#16a34a",
                "#22c55e",
                "#4ade80",
                "#22c55e",
                "#16a34a",
                "#15803d",
                "#166534",
                "#15803d",
                "#15803d",
                "#15803d",
                "#15803d",
                "#15803d",
            ]
            fg_colors = [
                "#f8fafc",
                "#f8fafc",
                "#f8fafc",
                "#f8fafc",
                "#0f172a",
                "#0f172a",
                "#0f172a",
                "#f8fafc",
                "#f8fafc",
                "#f8fafc",
                "#ffffff",
                "#ffffff",
                "#ffffff",
                "#ffffff",
                "#ffffff",
            ]

            if self._pulse_step < len(bg_colors):
                idx = self._pulse_step
                self.tag_configure(
                    "picked", background=bg_colors[idx], foreground=fg_colors[idx]
                )
                self._pulse_step += 1
            else:
                # Settle on final solid color after animation ends
                self.tag_configure("picked", background="#15803d", foreground="#ffffff")
        else:
            self._pulse_step = 0
            self.tag_configure("picked", background="#15803d", foreground="#ffffff")

        # Loop roughly at 15 FPS
        self.after(65, self._animate_picked_row)

    def _get_sort_group(self, view_id):
        """Links shared tables (e.g. Main Pack and Mini Pack) so they inherit sorting from each other."""
        if not view_id:
            return "default"
        if view_id in ["pack_table", "overlay_table"]:
            return "pack"
        if view_id in ["taken_table", "overlay_pool_table"]:
            return "pool"
        return view_id

    def _setup_headers(self, columns):
        from src.constants import COLUMN_FIELD_LABELS

        for i in columns:
            if i == "add_btn":
                self.heading(i, text="+")
                self.column(
                    i, width=20, minwidth=20, stretch=False, anchor=tkinter.CENTER
                )
                continue
            l = (
                i
                if "TIER" in i
                else COLUMN_FIELD_LABELS.get(i, str(i).upper()).split(":")[0]
            )
            self.base_labels[i] = l

            # Immediately draw the sort indicator (arrow) if a sort state was inherited
            if i == self.active_sort_column:
                rev = self.column_sort_state.get(i, False)
                display_text = f"{l} {'▼' if rev else '▲'}"
            else:
                display_text = l

            self.heading(i, text=display_text)
            self.column(
                i,
                width=140 if i == "name" else 50,
                minwidth=70 if i == "name" else 30,
                stretch=True,
                anchor=tkinter.W if i == "name" else tkinter.CENTER,
            )

    def _setup_column_drag(self):
        self.bind("<Button-1>", self._on_header_press, add="+")
        self.bind("<B1-Motion>", self._on_header_motion, add="+")
        self.bind("<ButtonRelease-1>", self._on_header_release, add="+")

    def _get_display_order(self):
        """Returns current column display order (excluding add_btn)."""
        dc = self["displaycolumns"]
        if isinstance(dc, str) or (isinstance(dc, tuple) and dc and dc[0] == "#all"):
            return [c for c in self["columns"] if c != "add_btn"]
        return [c for c in dc if c != "add_btn"]

    def _on_header_press(self, event):
        if self.identify_region(event.x, event.y) != "heading":
            self._drag_col = None
            return
        try:
            idx = int(self.identify_column(event.x).replace("#", "")) - 1
        except (ValueError, AttributeError):
            self._drag_col = None
            return
        display_order = self._get_display_order()
        if idx < 0 or idx >= len(display_order):
            self._drag_col = None
            return
        self._drag_col = display_order[idx]
        self._drag_start_x = event.x
        self._dragging = False

    def _on_header_motion(self, event):
        if self._drag_col and abs(event.x - self._drag_start_x) > 8:
            self._dragging = True
            self.configure(cursor="fleur")

    def _on_header_release(self, event):
        self.configure(cursor="")
        if self._drag_col is None:
            return
        if not self._dragging:
            # It was a click — sort
            col = self._drag_col
            self._drag_col = None
            self._handle_sort(col)
            return
        # It was a drag — reorder display only (do NOT touch active_fields,
        # which must stay in self["columns"] order for correct value insertion)
        try:
            target_idx = int(self.identify_column(event.x).replace("#", "")) - 1
        except (ValueError, AttributeError):
            self._drag_col = None
            self._dragging = False
            return
        display_order = self._get_display_order()
        src_idx = (
            display_order.index(self._drag_col)
            if self._drag_col in display_order
            else -1
        )
        if (
            src_idx >= 0
            and 0 <= target_idx < len(display_order)
            and src_idx != target_idx
        ):
            display_order.insert(target_idx, display_order.pop(src_idx))
            has_add_btn = "add_btn" in self["columns"]
            self["displaycolumns"] = display_order + (
                ["add_btn"] if has_add_btn else []
            )
            if self.config and self.view_id:
                if not hasattr(self.config.settings, "column_display_orders"):
                    self.config.settings.column_display_orders = {}
                self.config.settings.column_display_orders[self.view_id] = display_order
                from src.configuration import write_configuration

                write_configuration(self.config)
        self._drag_col = None
        self._dragging = False

    def _setup_row_colors(self):
        # Bind theme updates so zebra striping changes seamlessly
        self.bind(
            "<<ThemeChanged>>", lambda e: self._apply_dynamic_row_colors(), add="+"
        )
        self._apply_dynamic_row_colors()

    def _apply_dynamic_row_colors(self):
        from src.ui.styles import Theme

        # Standard Zebra Striping
        self.tag_configure(
            "bw_even", background=Theme.BG_SECONDARY, foreground=Theme.TEXT_MAIN
        )
        self.tag_configure(
            "bw_odd", background=Theme.BG_PRIMARY, foreground=Theme.TEXT_MAIN
        )

        # Colored Highlights (Preserved for "Highlight Row by Mana Cost" setting)
        for t, b, f in [
            ("white", "#f8fafc", "#0f172a"),
            ("blue", "#e0f2fe", "#0369a1"),
            ("black", "#cbd5e1", "#0f172a"),
            ("red", "#fee2e2", "#991b1b"),
            ("green", "#dcfce7", "#166534"),
            ("gold", "#fef3c7", "#92400e"),
            ("colorless", "#e2e8f0", "#1e293b"),
            ("elite_bomb", "#78350f", "#fde047"),
            ("high_fit", "#0c4a6e", "#e0f2fe"),
            ("picked", "#15803d", "#ffffff"),
        ]:
            self.tag_configure(
                (
                    f"{t}_card"
                    if "elite" not in t and "high" not in t and "picked" not in t
                    else t
                ),
                background=b,
                foreground=f,
            )

    def _handle_sort(self, column, force_reverse=None):
        from src.card_logic import field_process_sort

        if force_reverse is not None:
            self.column_sort_state[column] = force_reverse
        else:
            self.column_sort_state[column] = not self.column_sort_state.get(
                column, False
            )

        rev = self.column_sort_state[column]
        self.active_sort_column = column

        # Persist the sort state centrally so it survives windows swaps
        if self.config and self.view_id:
            if not hasattr(self.config.settings, "table_sort_states"):
                self.config.settings.table_sort_states = {}

            self.config.settings.table_sort_states[self.sort_group] = {
                "column": column,
                "reverse": rev,
            }
            # Commit to disk (safely handles atomic locking behind the scenes)
            from src.configuration import write_configuration

            write_configuration(self.config)

        for i in self["columns"]:
            if i in self.base_labels:
                self.heading(
                    i,
                    text=(
                        f"{self.base_labels[i]} {'▼' if rev else '▲'}"
                        if i == column
                        else self.base_labels[i]
                    ),
                )

        it = [(self.item(k)["values"], k) for k in self.get_children("")]
        try:
            # Sort relies entirely on the physical index to be agnostic of column order!
            ci = list(self["columns"]).index(column)
        except ValueError:
            return

        def _k(t):
            p = field_process_sort(t[0][ci])
            return (
                (p[0], p[1], str(t[0][0]).lower())
                if isinstance(p, tuple)
                else (
                    (1, float(p), str(t[0][0]).lower())
                    if str(p).replace(".", "").isdigit()
                    else (0, str(p), str(t[0][0]).lower())
                )
            )

        it.sort(key=_k, reverse=rev)
        for i, (v, k) in enumerate(it):
            self.move(k, "", i)
            ts = [t for t in self.item(k, "tags") if t not in ("bw_odd", "bw_even")]
            has_special = any(
                t in ("elite_bomb", "high_fit") or str(t).endswith("_card") for t in ts
            )
            if not has_special:
                ts.append("bw_odd" if i % 2 == 0 else "bw_even")

            self.item(k, tags=tuple(ts))

    def reapply_sort(self):
        """Forces the tree to re-apply the user's active sort settings after external data injection."""
        # Always pull the freshest state from config in case another window modified it!
        if self.config and self.view_id:
            saved_state = self.config.settings.table_sort_states.get(
                self.sort_group, {}
            )
            if saved_state:
                saved_col = saved_state.get("column")
                saved_rev = saved_state.get("reverse", False)
                # Ensure the inherited sort actually exists in this specific table's columns
                if saved_col in self["columns"]:
                    self.active_sort_column = saved_col
                    self.column_sort_state[saved_col] = saved_rev

        if self.active_sort_column and self.active_sort_column in self["columns"]:
            self._handle_sort(
                self.active_sort_column,
                force_reverse=self.column_sort_state.get(
                    self.active_sort_column, False
                ),
            )
            return True
        return False


class DynamicTreeviewManager(ttk.Frame):
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
        self.view_id, self.config, self.on_update, self.static_columns, self.kwargs = (
            view_id,
            configuration,
            on_update_callback,
            static_columns,
            kwargs,
        )
        self.tree = None
        self.rebuild(False)

    def rebuild(self, trigger_callback=True):
        if self.tree:
            self.tree.destroy()
        if hasattr(self, "_scrollbar") and self._scrollbar:
            self._scrollbar.destroy()

        self.active_fields = (
            list(self.static_columns)
            if self.static_columns
            else self.config.settings.column_configs.get(
                self.view_id, ["name", "value", "gihwr"]
            )
        )
        self.tree = ModernTreeview(
            self,
            (
                self.active_fields
                if self.static_columns
                else self.active_fields + ["add_btn"]
            ),
            view_id=self.view_id,
            config=self.config,
            **self.kwargs,
        )
        self.tree.active_fields = self.active_fields

        # Restore saved display order if present, while gracefully appending NEW columns
        saved_display = getattr(self.config.settings, "column_display_orders", {}).get(
            self.view_id
        )
        if saved_display:
            valid = [f for f in saved_display if f in self.tree["columns"]]
            new_fields = [
                f for f in self.tree["columns"] if f not in valid and f != "add_btn"
            ]

            combined_display = valid + new_fields
            if combined_display:
                has_add_btn = "add_btn" in self.tree["columns"]
                self.tree["displaycolumns"] = combined_display + (
                    ["add_btn"] if has_add_btn else []
                )

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._scrollbar = AutoScrollbar(
            self, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=self._scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")

        if not self.static_columns:
            self.tree.bind("<Button-3>", self._show_context_menu)
            self.tree.bind("<Control-Button-1>", self._show_context_menu)
            self.tree.bind("<Button-1>", self._handle_click, add="+")

        if trigger_callback:
            self.on_update()

    def _show_context_menu(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return
        try:
            i = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        except:
            return
        if i >= len(self.active_fields):
            return

        # We must use display order to figure out which column they actually clicked on
        display_order = self.tree._get_display_order()
        if i >= len(display_order):
            return

        field = display_order[i]
        menu = tkinter.Menu(self, tearoff=0)

        if field != "name":
            menu.add_command(
                label=f"Remove '{field.upper()}'",
                command=lambda f=field: self._remove_column_by_name(f),
            )
            menu.add_separator()

        am = tkinter.Menu(menu, tearoff=0)
        menu.add_cascade(label="Add Column", menu=am)
        from src.constants import COLUMN_FIELD_LABELS

        for fi, lb in COLUMN_FIELD_LABELS.items():
            if fi not in self.active_fields:
                am.add_command(label=lb, command=lambda x=fi: self._add_column(x))
        from src.tier_list import TierList

        latest_dataset = getattr(self.config.card_data, "latest_dataset", "")
        set_code = latest_dataset.split("_")[0] if latest_dataset else ""

        _, tier_options = TierList.retrieve_data(set_code)
        if tier_options:
            am.add_separator()
            for display_name, internal_id in tier_options.items():
                if internal_id not in self.active_fields:
                    am.add_command(
                        label=display_name,
                        command=lambda x=internal_id: self._add_column(x),
                    )
        menu.add_separator()
        menu.add_command(label="Reset to Defaults", command=self._reset_defaults)
        menu.post(event.x_root, event.y_root)

    def _handle_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "heading" and int(
            self.tree.identify_column(event.x).replace("#", "")
        ) - 1 == len(self.active_fields):
            self._show_add_menu(event)

    def _show_add_menu(self, event):
        menu = tkinter.Menu(self, tearoff=0)
        from src.constants import COLUMN_FIELD_LABELS

        for f, lb in COLUMN_FIELD_LABELS.items():
            if f not in self.active_fields:
                menu.add_command(label=lb, command=lambda x=f: self._add_column(x))

        from src.tier_list import TierList

        tf = TierList.retrieve_files()
        if tf:
            menu.add_separator()
            for idx, (sc, lb, _, _) in enumerate(tf):
                tn = f"TIER{idx}"
                if tn not in self.active_fields:
                    menu.add_command(
                        label=f"TIER: {lb} ({sc})",
                        command=lambda x=tn: self._add_column(x),
                    )

        menu.post(event.x_root, event.y_root)

    def _add_column(self, field):
        if len(self.active_fields) >= 15:
            return
        self.active_fields.append(field)
        try:
            t = self.winfo_toplevel()
            cw = t.winfo_width()
            rw = 140 + (len(self.active_fields) * 40) + 40
            if cw < rw:
                t.geometry(f"{rw}x{t.winfo_height()}")
        except:
            pass
        self._persist()

    def _remove_column_by_name(self, field):
        if len(self.active_fields) > 1 and field in self.active_fields:
            self.active_fields.remove(field)
            self._persist()

    def _reset_defaults(self):
        self.active_fields = ["name", "value", "gihwr"]

        if hasattr(self.config.settings, "column_display_orders"):
            if self.view_id in self.config.settings.column_display_orders:
                del self.config.settings.column_display_orders[self.view_id]

        self._persist()

    def _persist(self):
        from src.configuration import write_configuration

        self.config.settings.column_configs[self.view_id] = self.active_fields
        write_configuration(self.config)
        self.rebuild(True)


class SignalMeter(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas_height, self.bar_width, self.gap, self.scores = 80, 20, 4, {}
        self.canvas = tb.Canvas(
            self, height=self.canvas_height, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.canvas.configure(bg=Theme.BG_PRIMARY)
            self.redraw()

    def update_values(self, scores):
        self.scores = scores
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10:
            return
        cl, cm = ["W", "U", "B", "R", "G"], {
            "W": Theme.WARNING,
            "U": Theme.ACCENT,
            "B": "#555555",
            "R": Theme.ERROR,
            "G": Theme.SUCCESS,
        }
        tw = (len(cl) * self.bar_width) + ((len(cl) - 1) * self.gap)
        sx, sc = (w - tw) / 2, (self.canvas_height - 18) / max(
            max(self.scores.values(), default=1), 20
        )
        for i, c in enumerate(cl):
            v = self.scores.get(c, 0.0)
            x, bh = sx + (i * (self.bar_width + self.gap)), v * sc
            self.canvas.create_rectangle(
                x,
                self.canvas_height - bh - 12,
                x + self.bar_width,
                self.canvas_height - 12,
                fill=cm[c],
                outline="",
            )
            self.canvas.create_text(
                x + self.bar_width / 2,
                self.canvas_height - 5,
                text=c,
                fill=Theme.TEXT_MAIN,
                font=(Theme.FONT_FAMILY, 9, "bold"),
            )


class ManaCurvePlot(tb.Frame):
    def __init__(self, parent, ideal_distribution, **kwargs):
        super().__init__(parent, **kwargs)
        self.ideal, self.current, self.canvas_height = ideal_distribution, [0] * 7, 80
        self.canvas = tb.Canvas(
            self, height=self.canvas_height, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.canvas.configure(bg=Theme.BG_PRIMARY)
            self.redraw()

    def update_curve(self, counts):
        self.current = counts[:6] + [sum(counts[6:])] if len(counts) > 6 else counts
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10:
            return
        bw, gp = 14, 2
        tw = (len(self.current) * bw) + ((len(self.current) - 1) * gp)
        sx, sc = (w - tw) / 2, (self.canvas_height - 25) / max(
            max(self.current), max(self.ideal), 5
        )
        for i, c in enumerate(self.current):
            x, t = sx + (i * (bw + gp)), self.ideal[i] if i < len(self.ideal) else 0
            if t > 0:
                self.canvas.create_rectangle(
                    x,
                    self.canvas_height - (t * sc) - 10,
                    x + bw,
                    self.canvas_height - 10,
                    outline=Theme.TEXT_MAIN,
                    width=1,
                    dash=(2, 2),
                )
            cl = (
                Theme.ERROR
                if c > t + 1
                else (
                    Theme.WARNING
                    if c < t and t > 0
                    else Theme.SUCCESS if c >= t else Theme.ACCENT
                )
            )
            self.canvas.create_rectangle(
                x,
                self.canvas_height - (c * sc) - 10,
                x + bw,
                self.canvas_height - 10,
                fill=cl,
                outline="",
            )
            if c > 0:
                self.canvas.create_text(
                    x + bw / 2,
                    self.canvas_height - (c * sc) - 17,
                    text=str(c),
                    fill=Theme.TEXT_MAIN,
                    font=(Theme.FONT_FAMILY, 9, "bold"),
                )
            self.canvas.create_text(
                x + bw / 2,
                self.canvas_height - 4,
                text=str(i) if i < 6 else "6+",
                fill=Theme.TEXT_MAIN,
                font=(Theme.FONT_FAMILY, 8),
            )


class TypePieChart(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.counts = {"Creatures": 0, "Non-Creatures": 0, "Lands": 0}
        self.canvas_height = 80
        self.pie_size = 76  # Slightly smaller to fit bounds cleanly

        self.canvas = tb.Canvas(
            self, height=self.canvas_height, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.canvas.configure(bg=Theme.BG_PRIMARY)
            self.redraw()

    def update_counts(self, c, n, l):
        self.counts["Creatures"] = c
        self.counts["Non-Creatures"] = n
        self.counts["Lands"] = l
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10:
            return

        c_col = Theme.SUCCESS
        n_col = Theme.ACCENT
        l_col = Theme.BG_TERTIARY

        items = [
            ("Crea", self.counts["Creatures"], c_col),
            ("Spell", self.counts["Non-Creatures"], n_col),
            ("Land", self.counts["Lands"], l_col),
        ]

        # Geometry Math to center both elements dynamically
        legend_w = 60
        gap = 20
        pie_r = self.pie_size / 2
        total_w = legend_w + gap + self.pie_size

        sx = max(0, (w - total_w) / 2)

        # 1. Draw Legend on the Left
        ly = (self.canvas_height - (3 * 18)) / 2 + 9
        for lb, count, cl in items:
            self.canvas.create_text(
                sx, ly, text="●", fill=cl, font=(None, 10), anchor="w"
            )
            self.canvas.create_text(
                sx + 12,
                ly,
                text=f"{lb}: {count}",
                fill=Theme.TEXT_MAIN,
                font=(Theme.FONT_FAMILY, 10),
                anchor="w",
            )
            ly += 18

        # 2. Draw Pie Chart on the Right
        cx = sx + legend_w + gap + pie_r
        cy = self.canvas_height / 2
        tl = sum(self.counts.values())

        if tl == 0:
            self.canvas.create_oval(
                cx - pie_r,
                cy - pie_r,
                cx + pie_r,
                cy + pie_r,
                fill=Theme.BG_SECONDARY,
                outline="",
            )
            return

        a = 90
        for c, cl in [
            (self.counts["Creatures"], c_col),
            (self.counts["Non-Creatures"], n_col),
            (self.counts["Lands"], l_col),
        ]:
            if c == 0:
                continue
            ex = (c / tl) * 360
            self.canvas.create_arc(
                cx - pie_r,
                cy - pie_r,
                cx + pie_r,
                cy + pie_r,
                start=a,
                extent=-ex,
                fill=cl,
                outline="",
                style="pieslice",
            )
            a -= ex

        # Donut Hole
        inner_r = pie_r - 12
        self.canvas.create_oval(
            cx - inner_r,
            cy - inner_r,
            cx + inner_r,
            cy + inner_r,
            fill=Theme.BG_PRIMARY,
            outline="",
        )

        # Total text in center
        self.canvas.create_text(
            cx,
            cy,
            text=str(tl),
            fill=Theme.TEXT_MAIN,
            font=(Theme.FONT_FAMILY, 9, "bold"),
        )


class ScrolledFrame(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.scrollbar = AutoScrollbar(
            self, orient="horizontal", bootstyle="secondary-round"
        )
        self.canvas = tb.Canvas(self, bg=Theme.BG_PRIMARY, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.canvas.xview)

        self.scrollable_frame = tb.Frame(self.canvas)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.window_id, height=e.height),
        )


class CardPile(tb.Frame):
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
        nm = card_data.get("name", "Unknown")
        ct = card_data.get("mana_cost", "")
        cn = card_data.get("count", 1)

        cl = sorted(
            list(set(re.findall(r"[WUBRG]", ct or ""))),
            key=lambda x: ["W", "U", "B", "R", "G"].index(x) if x in "WUBRG" else 99,
        )
        if not cl:
            cl = ["NC"]

        # We explicitly use a standard tk.Frame here to completely override bootstyle limitations
        # Use a sleek dark background for all cards in the visual view to guarantee readability
        bg_col = "#1e293b"
        fg_col = "#f8fafc"

        ch = tkinter.Frame(self.container, bg=bg_col, cursor="hand2")
        ch.pack(fill=X, pady=1, padx=2)

        tx = f"{cn}x {nm}" if cn > 1 else nm

        # Left color strip accent (width 6 is half the old massive block size)
        cv = tkinter.Canvas(
            ch, width=6, height=24, bg=bg_col, highlightthickness=0, cursor="hand2"
        )
        cv.pack(side=LEFT, fill=Y)

        h = 24 / len(cl)
        color_map = {
            "W": "#f8f6f1",
            "U": "#3498db",
            "B": "#8b8b93",  # Lightened gray so black mana clearly shows up against dark background
            "R": "#e74c3c",
            "G": "#00bc8c",
            "NC": "#8e9eae",
        }

        for i, c in enumerate(cl):
            cv.create_rectangle(
                0,
                i * h,
                6,
                (i + 1) * h,
                fill=color_map.get(c, "#8e9eae"),
                outline="",
            )

        # Card Name Label
        lb = tkinter.Label(
            ch,
            text=tx,
            bg=bg_col,
            fg=fg_col,
            font=(Theme.FONT_FAMILY, 10),
            anchor="w",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        lb.pack(side=LEFT, fill=BOTH, expand=True)

        def _trigger_tooltip(e):
            CardToolTip.create(
                ch,  # Anchor safely to the row container
                card_data,
                self.app.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(
                    self.app.configuration.settings.ui_size, 1.0
                ),
            )

        # Require an explicit click to view the tooltip to stop erratic hovering/flashing
        ch.bind("<Button-1>", _trigger_tooltip)
        cv.bind("<Button-1>", _trigger_tooltip)
        lb.bind("<Button-1>", _trigger_tooltip)
