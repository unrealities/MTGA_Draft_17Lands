"""
src/ui/components.py
Atomic UI Widgets for the MTGA Draft Tool.
Restored full parameter names for keyword argument compatibility.
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
            foreground=Theme.ACCENT,
            cursor="hand2",
        )
        self.toggle_label.pack(side="left", padx=(5, 5), pady=(5, 5))
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
                self.toggle_label.configure(foreground=Theme.ACCENT)
                self.title_label.configure(foreground=Theme.TEXT_MAIN)
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


class AutocompleteEntry(tkinter.Entry):
    def __init__(self, master, completion_list, **kwargs):
        super().__init__(master, **kwargs)
        self.completion_list = sorted(completion_list)
        self.hits, self.hit_index = [], 0
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
    IMAGE_CACHE_DIR = os.path.join(os.getcwd(), "Temp", "Images")
    _active_tooltip = None
    _image_executor = ThreadPoolExecutor(max_workers=4)

    def __init__(self, parent, card, images_enabled, scale):
        # --- 1. Basic Land Filter ---
        # Prevent tooltips from appearing for Basic Lands to reduce clutter
        card_types = card.get("types", [])
        if "Land" in card_types and "Basic" in card_types:
            # We must initialize the Toplevel class to avoid recursion errors in Python,
            # but we immediately hide and destroy it.
            super().__init__(parent)
            self.withdraw()
            self.destroy()
            return

        if CardToolTip._active_tooltip and CardToolTip._active_tooltip.winfo_exists():
            CardToolTip._active_tooltip.destroy()
        CardToolTip._active_tooltip = self
        super().__init__(parent)
        self.wm_overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(
            bg=Theme.BG_PRIMARY, highlightthickness=1, highlightbackground=Theme.ACCENT
        )
        if not os.path.exists(self.IMAGE_CACHE_DIR):
            os.makedirs(self.IMAGE_CACHE_DIR)
        name, stats, urls, tags, rarity = (
            card.get("name", "Unknown"),
            card.get("deck_colors", {}),
            card.get("image", []),
            card.get("tags", []),
            card.get("rarity", "common").capitalize(),
        )
        h = tkinter.Frame(self, bg=Theme.BG_SECONDARY)
        h.pack(fill="x")
        rc = (
            "#f97316"
            if rarity == "Mythic"
            else (
                "#eab308"
                if rarity == "Rare"
                else "#94a3b8" if rarity == "Uncommon" else Theme.TEXT_MAIN
            )
        )
        tkinter.Label(
            h,
            text=name,
            bg=Theme.BG_SECONDARY,
            fg=Theme.TEXT_MAIN,
            font=(Theme.FONT_FAMILY, int(13 * scale), "bold"),
            padx=10,
            pady=6,
        ).pack(side="left")
        tkinter.Label(
            h,
            text=rarity,
            bg=Theme.BG_SECONDARY,
            fg=rc,
            font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            padx=10,
        ).pack(side="right")
        b = tkinter.Frame(self, bg=Theme.BG_PRIMARY, padx=12, pady=12)
        b.pack(fill="both", expand=True)

        # --- 2. Image Container ---
        # Reserves space immediately so the tooltip doesn't expand/jump when the image loads
        if images_enabled:
            img_w = int(240 * scale)
            img_h = int(335 * scale)

            # Create a fixed-size container frame
            self.img_frame = tkinter.Frame(
                b, width=img_w, height=img_h, bg=Theme.BG_PRIMARY
            )
            # This is key: tell the frame NOT to shrink to fit its (currently empty) children
            self.img_frame.pack_propagate(False)
            self.img_frame.pack(side="left", padx=(0, 15), anchor="n")

            self.img_label = tkinter.Label(self.img_frame, bg=Theme.BG_PRIMARY)
            self.img_label.pack(fill="both", expand=True)

            if urls:
                self._load_image_async(urls[0], scale)

        sf = tkinter.Frame(b, bg=Theme.BG_PRIMARY)
        sf.pack(side="left", fill="both", expand=True, anchor="n")
        gs = stats.get("All Decks", {})
        wr, iwd, smp = gs.get("gihwr", 0.0), gs.get("iwd", 0.0), gs.get("samples", 0)
        tkinter.Label(
            sf,
            text="GLOBAL PERFORMANCE",
            fg=Theme.ACCENT,
            bg=Theme.BG_PRIMARY,
            font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
        ).pack(anchor="w")
        gf = tkinter.Frame(sf, bg=Theme.BG_PRIMARY)
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
                tkinter.Label(
                    gf,
                    text=lbl,
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, int(9 * scale)),
                ).grid(row=ri, column=ci * 2, sticky="w", padx=(0, 6))
                tkinter.Label(
                    gf,
                    text=val,
                    fg=col,
                    bg=Theme.BG_PRIMARY,
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
            tkinter.Label(
                sf,
                text="ARCHETYPE PLAY SHARE",
                fg=Theme.SUCCESS,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            ).pack(anchor="w")
            for k in va[:10]:
                rf = tkinter.Frame(sf, bg=Theme.BG_PRIMARY)
                rf.pack(anchor="w", fill="x", pady=(2, 0))
                tkinter.Label(
                    rf,
                    text=f"• {constants.COLOR_NAMES_DICT.get(k, k)} ({k}):",
                    fg=Theme.TEXT_MAIN,
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, int(9 * scale)),
                ).pack(side="left")
                tkinter.Label(
                    rf,
                    text=f" {stats[k].get('gihwr', 0.0):.1f}% WR",
                    fg=(
                        Theme.TEXT_MAIN
                        if stats[k].get("gihwr", 0.0) < 55.0
                        else Theme.SUCCESS
                    ),
                    bg=Theme.BG_PRIMARY,
                    font=(Theme.FONT_FAMILY, int(9 * scale), "bold"),
                ).pack(side="left")
        if tags:
            tkinter.Label(
                sf,
                text="CARD ROLES",
                fg=Theme.WARNING,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, int(10 * scale), "bold"),
            ).pack(anchor="w", pady=(12, 4))
            tkinter.Label(
                sf,
                text="   ".join(
                    [constants.TAG_VISUALS.get(t, t.capitalize()) for t in tags]
                ),
                fg=Theme.TEXT_MAIN,
                bg=Theme.BG_PRIMARY,
                font=(Theme.FONT_FAMILY, int(9 * scale), "bold"),
                wraplength=int(280 * scale),
                justify="left",
            ).pack(anchor="w")
        # Anchor to the mouse position AT THE TIME OF CREATION
        self._mouse_x = parent.winfo_pointerx()
        self._mouse_y = parent.winfo_pointery()
        self._reposition()

        parent.bind(
            "<Leave>",
            lambda e: self.destroy() if self.winfo_exists() else None,
            add="+",
        )
        self.bind("<Button-1>", lambda e: self.destroy())

    def _reposition(self):
        """Calculates bounds using the static initial mouse position so the tooltip doesn't teleport."""
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return

        self.update_idletasks()
        ww = self.winfo_width()
        wh = self.winfo_height()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        offset_x, offset_y = 25, 25

        if self._mouse_x + offset_x + ww > sw:
            tx = max(self._mouse_x - offset_x - ww - 10, 0)
        else:
            tx = max(self._mouse_x + offset_x, 0)

        if self._mouse_y + offset_y + wh > sh:
            ty = max(self._mouse_y - offset_y - wh - 10, 0)
        else:
            ty = max(self._mouse_y + offset_y, 0)

        self.geometry(f"+{tx}+{ty}")

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
    def __init__(self, parent, columns, **kwargs):
        super().__init__(
            parent, columns=columns, show="headings", style="Treeview", **kwargs
        )
        self.column_sort_state, self.active_fields, self.base_labels = (
            {i: False for i in columns},
            [],
            {},
        )
        self._setup_headers(columns)
        self._setup_row_colors()

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
            self.heading(i, text=l, command=lambda x=i: self._handle_sort(x))
            self.column(
                i,
                width=140 if i == "name" else 50,
                minwidth=70 if i == "name" else 30,
                stretch=True,
                anchor=tkinter.W if i == "name" else tkinter.CENTER,
            )

    def _setup_row_colors(self):
        for t, b, f in [
            ("white", "#f4f4f5", "#18181b"),
            ("blue", "#e0f2fe", "#0c4a6e"),
            ("black", "#d1d5db", "#111827"),
            ("red", "#fee2e2", "#7f1d1d"),
            ("green", "#dcfce7", "#14532d"),
            ("gold", "#fef3c7", "#78350f"),
            ("colorless", "#e4e4e7", "#27272a"),
            ("elite_bomb", "#78350f", "#fde047"),
            ("high_fit", "#0c4a6e", "#7dd3fc"),
        ]:
            self.tag_configure(
                f"{t}_card" if "elite" not in t and "high" not in t else t,
                background=b,
                foreground=f,
            )

    def _handle_sort(self, column):
        from src.card_logic import field_process_sort

        self.column_sort_state[column] = not self.column_sort_state[column]
        rev = self.column_sort_state[column]
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
            ci = list(self["columns"]).index(column)
        except:
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
            ts.append("bw_odd" if i % 2 == 0 else "bw_even")
            self.item(k, tags=tuple(ts))


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
            **self.kwargs,
        )
        self.tree.active_fields = self.active_fields
        self.tree.pack(fill="both", expand=True)
        if not self.static_columns:
            self.tree.bind("<Button-3>", self._show_context_menu)
            self.tree.bind("<Control-Button-1>", self._show_context_menu)
            self.tree.bind("<Button-1>", self._handle_click)
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
        field, menu = self.active_fields[i], tkinter.Menu(self, tearoff=0)
        if field != "name":
            menu.add_command(
                label=f"Remove '{field.upper()}'",
                command=lambda x=i: self._remove_column(x),
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

    def _remove_column(self, index):
        if len(self.active_fields) > 1:
            self.active_fields.pop(index)
            self._persist()

    def _reset_defaults(self):
        self.active_fields = ["name", "value", "gihwr"]
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
        self.canvas_size, self.counts = 80, {
            "Creatures": 0,
            "Non-Creatures": 0,
            "Lands": 0,
        }
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
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.canvas.configure(bg=Theme.BG_PRIMARY)
            self.redraw()

    def update_counts(self, c, n, l):
        self.counts["Creatures"], self.counts["Non-Creatures"], self.counts["Lands"] = (
            c,
            n,
            l,
        )
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        [w.destroy() for w in self.legend_frame.winfo_children()]
        items = [
            ("Crea", self.counts["Creatures"], Theme.SUCCESS),
            ("Spell", self.counts["Non-Creatures"], Theme.ACCENT),
            ("Land", self.counts["Lands"], Theme.BG_TERTIARY),
        ]
        for lb, c, cl in items:
            rf = tb.Frame(self.legend_frame)
            rf.pack(anchor="w")
            tb.Label(rf, text="●", foreground=cl, font=(None, 6)).pack(side=LEFT)
            tb.Label(rf, text=f"{lb}: {c}", font=(Theme.FONT_FAMILY, 10)).pack(
                side=LEFT, padx=2
            )
        tl = sum(self.counts.values())
        if tl == 0:
            return
        cx, cy, r, a = (
            self.canvas_size / 2,
            self.canvas_size / 2,
            (self.canvas_size / 2) - 2,
            90,
        )
        for c, cl in [
            (self.counts["Creatures"], Theme.SUCCESS),
            (self.counts["Non-Creatures"], Theme.ACCENT),
            (self.counts["Lands"], Theme.BG_TERTIARY),
        ]:
            if c == 0:
                continue
            ex = (c / tl) * 360
            self.canvas.create_arc(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                start=a,
                extent=-ex,
                fill=cl,
                outline="",
                style="pieslice",
            )
            a -= ex
        self.canvas.create_oval(
            cx - r / 2,
            cy - r / 2,
            cx + r / 2,
            cy + r / 2,
            fill=Theme.BG_PRIMARY,
            outline="",
        )
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
        self.scrollbar = tb.Scrollbar(
            self, orient="horizontal", bootstyle="secondary-round"
        )
        self.scrollbar.pack(side="bottom", fill="x")
        self.canvas = tb.Canvas(self, bg=Theme.BG_PRIMARY, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)
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
        nm, ct, cn = (
            card_data["name"],
            card_data.get("mana_cost", ""),
            card_data.get("count", 1),
        )
        cl = sorted(
            list(set(re.findall(r"[WUBRG]", ct or ""))),
            key=lambda x: ["W", "U", "B", "R", "G"].index(x) if x in "WUBRG" else 99,
        )
        ch = tb.Frame(self.container)
        ch.pack(fill=X, pady=1, padx=2)
        tx = f"{cn}x {nm}" if cn > 1 else nm
        if len(cl) > 1:
            lb = tb.Label(
                ch,
                text=tx,
                font=(Theme.FONT_FAMILY, 10),
                foreground="#000000",
                background="#d4af37",
                anchor="w",
                padding=(5, 2),
            )
            lb.pack(side=LEFT, fill=BOTH, expand=True)
            cv = tb.Canvas(ch, width=12, height=20, bg="#d4af37", highlightthickness=0)
            cv.pack(side=RIGHT, fill=Y)
            h = 20 / len(cl)
            for i, c in enumerate(cl):
                cv.create_rectangle(
                    0,
                    i * h,
                    12,
                    (i + 1) * h,
                    fill={
                        "W": "#f8f6f1",
                        "U": "#3498db",
                        "B": "#2c3e50",
                        "R": "#e74c3c",
                        "G": "#00bc8c",
                    }.get(c, "#000"),
                    outline="",
                )
            lb.bind(
                "<Enter>",
                lambda e: CardToolTip(
                    lb,
                    card_data,
                    self.app.configuration.features.images_enabled,
                    constants.UI_SIZE_DICT.get(
                        self.app.configuration.settings.ui_size, 1.0
                    ),
                ),
            )
        else:
            c = cl[0] if cl else "NC"
            s = {
                "W": "warning",
                "U": "info",
                "B": "dark",
                "R": "danger",
                "G": "success",
            }.get(c, "secondary")
            lb = tb.Label(
                ch,
                text=tx,
                foreground="#000000" if c == "W" else None,
                background="#f0f0f0" if c == "W" else None,
                bootstyle=None if c == "W" else f"inverse-{s}",
                font=(Theme.FONT_FAMILY, 10),
                anchor="w",
                padding=(5, 2),
            )
            lb.pack(fill=X)
            lb.bind(
                "<Enter>",
                lambda e: CardToolTip(
                    lb,
                    card_data,
                    self.app.configuration.features.images_enabled,
                    constants.UI_SIZE_DICT.get(
                        self.app.configuration.settings.ui_size, 1.0
                    ),
                ),
            )
