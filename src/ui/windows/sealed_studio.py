"""
src/ui/windows/sealed_studio.py
Provides a massive workspace for Sealed deckbuilding.
Features both a detailed List View and a highly interactive,
MTGA-style Visual Drag-and-Drop Deckbuilder with card images.
"""

import tkinter
from tkinter import ttk, messagebox, simpledialog
import ttkbootstrap as tb
import requests
import json
import io
import os
import hashlib
from typing import List, Dict
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor

from src import constants
from src.configuration import Configuration
from src.ui.styles import Theme
from src.ui.components import (
    DynamicTreeviewManager,
    ManaCurvePlot,
    TypePieChart,
    CardToolTip,
    AutoScrollbar,
)
from src.card_logic import copy_deck, get_deck_metrics
from src.sealed_logic import SealedSession, generate_sealed_shells
from src.utils import open_file


class SealedStudioWindow(tb.Toplevel):
    def __init__(
        self,
        parent,
        app_context,
        configuration: Configuration,
        raw_pool: List[Dict],
        metrics,
        draft_id: str = None,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.configuration = configuration
        self.metrics = metrics

        self.title("Sealed Studio - MTGA Draft Tool")

        width = Theme.scaled_val(1400)
        height = Theme.scaled_val(900)
        self.geometry(f"{width}x{height}")
        self.minsize(Theme.scaled_val(1000), Theme.scaled_val(700))

        draft_id = (
            draft_id
            or app_context.orchestrator.scanner.current_draft_id
            or "local_sealed"
        )

        # Load or create session
        self.session = SealedSession.load_session(draft_id, raw_pool)
        if not self.session:
            self.session = SealedSession(draft_id)
            self.session.load_pool(raw_pool)

        # State
        self.view_mode = "visual"  # Options: "visual" or "list"
        self.image_cache = {}
        self.image_executor = ThreadPoolExecutor(max_workers=6)

        self.filter_vars = {
            "creatures": tkinter.IntVar(value=1),
            "spells": tkinter.IntVar(value=1),
            "lands": tkinter.IntVar(value=1),
            "W": tkinter.IntVar(value=1),
            "U": tkinter.IntVar(value=1),
            "B": tkinter.IntVar(value=1),
            "R": tkinter.IntVar(value=1),
            "G": tkinter.IntVar(value=1),
            "C": tkinter.IntVar(value=1),
            "M": tkinter.IntVar(value=1),
        }

        self.pool_sort_var = tkinter.StringVar(value="Color")
        self.deck_sort_var = tkinter.StringVar(value="CMC")

        if "sealed_pool_table" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["sealed_pool_table"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]
        if "sealed_deck_table" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["sealed_deck_table"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]

        self._build_ui()
        self._refresh_tabs()
        self._refresh_data()

        self.update_idletasks()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = tb.Frame(self, style="Card.TFrame", padding=Theme.scaled_val(10))
        header.pack(fill="x", side="top")

        tb.Label(
            header,
            text="SEALED STUDIO",
            font=Theme.scaled_font(18, "bold"),
            bootstyle="primary",
        ).pack(side="left")

        tb.Button(
            header,
            text="🤖 Auto-Generate Shells",
            bootstyle="success",
            command=self._on_auto_generate,
        ).pack(side="left", padx=Theme.scaled_val(20))

        tb.Button(
            header,
            text="📥 Import Deck",
            bootstyle="info",
            command=self._import_deck_from_clipboard,
        ).pack(side="left", padx=Theme.scaled_val(10))

        tb.Button(
            header,
            text="📋 Copy MTGA Format",
            bootstyle="info-outline",
            command=self._export_active_deck,
        ).pack(side="right", padx=Theme.scaled_val(5))

        tb.Button(
            header,
            text="🌐 Export to Sealeddeck.tech",
            bootstyle="warning-outline",
            command=self._export_to_sealeddeck_tech,
        ).pack(side="right", padx=Theme.scaled_val(5))

        self.btn_view_toggle = tb.Button(
            header,
            text="👁️ Switch to List View",
            bootstyle="secondary-outline",
            command=self._toggle_view,
        )
        self.btn_view_toggle.pack(side="right", padx=Theme.scaled_val(15))

        # Core container
        self.container = ttk.PanedWindow(self, orient=tkinter.HORIZONTAL)
        self.container.pack(
            fill="both",
            expand=True,
            padx=Theme.scaled_val(10),
            pady=Theme.scaled_val(10),
        )

        # --- LIST VIEW FRAMES ---
        self.list_pane_left = tb.Frame(self.container)
        self.list_pane_right = tb.Frame(self.container)
        self._build_list_view()

        # --- VISUAL VIEW FRAME ---
        self.visual_pane = tb.Frame(self.container)
        self._build_visual_view()

        # Initial View Setup
        self._apply_view_mode()

    def _toggle_view(self):
        self.view_mode = "list" if self.view_mode == "visual" else "visual"
        self._apply_view_mode()
        self._refresh_data()

    def _apply_view_mode(self):
        for pane in [self.visual_pane, self.list_pane_left, self.list_pane_right]:
            try:
                self.container.forget(pane)
            except tkinter.TclError:
                pass

        if self.view_mode == "list":
            self.btn_view_toggle.config(text="👁️ Switch to Visual View")
            self.container.add(self.list_pane_left, weight=1)
            self.container.add(self.list_pane_right, weight=1)
        else:
            self.btn_view_toggle.config(text="👁️ Switch to List View")
            self.container.add(self.visual_pane, weight=1)

    def _build_list_view(self):
        # LEFT PANE: MASTER POOL
        pool_header = tb.Frame(self.list_pane_left)
        pool_header.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        self.lbl_pool_title_list = tb.Label(
            pool_header, text="MASTER POOL (0)", font=Theme.scaled_font(12, "bold")
        )
        self.lbl_pool_title_list.pack(side="left")

        filter_frame = tb.Frame(pool_header)
        filter_frame.pack(side="right")

        tb.Label(filter_frame, text="Sort:").pack(side="left", padx=2)
        sort_cb = tb.Combobox(
            filter_frame,
            textvariable=self.pool_sort_var,
            values=["Color", "CMC", "Rarity", "Type"],
            state="readonly",
            width=7,
        )
        sort_cb.pack(side="left", padx=2)
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_data())
        tb.Label(filter_frame, text=" | ").pack(side="left")

        tb.Checkbutton(
            filter_frame,
            text="Creatures",
            variable=self.filter_vars["creatures"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Spells",
            variable=self.filter_vars["spells"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Lands",
            variable=self.filter_vars["lands"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)

        tb.Label(filter_frame, text=" | ").pack(side="left")

        for c, col in [
            ("W", "light"),
            ("U", "info"),
            ("B", "dark"),
            ("R", "danger"),
            ("G", "success"),
            ("M", "warning"),
            ("C", "secondary"),
        ]:
            btn = tb.Checkbutton(
                filter_frame,
                text=c,
                variable=self.filter_vars[c],
                bootstyle=f"{col}-toolbutton",
                command=self._refresh_data,
            )
            btn.pack(side="left", padx=1)

        self.pool_manager = DynamicTreeviewManager(
            self.list_pane_left,
            view_id="sealed_pool_table",
            configuration=self.configuration,
            on_update_callback=self._refresh_data,
        )
        self.pool_manager.pack(fill="both", expand=True)

        # RIGHT PANE: WORKBENCH
        tab_header = tb.Frame(self.list_pane_right)
        tab_header.pack(fill="x")

        self.notebook_list = tb.Notebook(tab_header)
        self.notebook_list.pack(side="left", fill="x", expand=True)
        self.notebook_list.bind("<<NotebookTabChanged>>", self._on_tab_changed_list)

        tb.Button(
            tab_header,
            text="➕",
            width=3,
            command=self._create_new_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="✏️",
            width=3,
            command=self._rename_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="🗑️",
            width=3,
            command=self._delete_tab,
            bootstyle="danger-outline",
        ).pack(side="right", padx=2, pady=2)

        deck_controls = tb.Frame(
            self.list_pane_right, style="Card.TFrame", padding=Theme.scaled_val(5)
        )
        deck_controls.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        self.lbl_deck_title_list = tb.Label(
            deck_controls,
            text="ACTIVE DECK (0)",
            font=Theme.scaled_font(12, "bold"),
            bootstyle="success",
        )
        self.lbl_deck_title_list.pack(side="left", padx=Theme.scaled_val(5))

        tb.Button(
            deck_controls,
            text="Auto-Lands",
            bootstyle="warning",
            command=self._apply_auto_lands,
        ).pack(side="left", padx=Theme.scaled_val(10))

        tb.Button(
            deck_controls,
            text="Clear",
            bootstyle="danger-outline",
            command=self._clear_deck,
        ).pack(side="left", padx=5)
        tb.Button(
            deck_controls,
            text="Add All",
            bootstyle="secondary-outline",
            command=self._add_all_to_deck,
        ).pack(side="left", padx=5)

        sort_frame = tb.Frame(deck_controls)
        sort_frame.pack(side="left", padx=Theme.scaled_val(15))
        tb.Label(sort_frame, text="Sort:").pack(side="left", padx=2)
        deck_sort_cb = tb.Combobox(
            sort_frame,
            textvariable=self.deck_sort_var,
            values=["Color", "CMC", "Rarity", "Type"],
            state="readonly",
            width=7,
        )
        deck_sort_cb.pack(side="left", padx=2)
        deck_sort_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_data())

        self.basics_frame_list = tb.Frame(deck_controls)
        self.basics_frame_list.pack(side="right")
        self.basic_buttons_list = {}
        for sym, name, style in [
            ("W", "Plains", "light"),
            ("U", "Island", "info"),
            ("B", "Swamp", "dark"),
            ("R", "Mountain", "danger"),
            ("G", "Forest", "success"),
        ]:
            btn = tb.Button(
                self.basics_frame_list,
                text=f"{sym}: 0",
                bootstyle=style,
                width=5,
                padding=Theme.scaled_val(3),
            )
            btn.bind("<ButtonRelease-1>", lambda e, n=name: self._add_basic(n))
            btn.bind("<Button-3>", lambda e, n=name: self._remove_basic(n))
            btn.pack(side="left", padx=1)
            self.basic_buttons_list[name] = btn

        self.deck_manager = DynamicTreeviewManager(
            self.list_pane_right,
            view_id="sealed_deck_table",
            configuration=self.configuration,
            on_update_callback=self._refresh_data,
        )
        self.deck_manager.pack(fill="both", expand=True)

        self._build_hud(self.list_pane_right)
        self._bind_dnd_list(self.pool_manager.tree, is_pool=True)
        self._bind_dnd_list(self.deck_manager.tree, is_pool=False)

    def _build_visual_view(self):
        self.visual_splitter = ttk.PanedWindow(
            self.visual_pane, orient=tkinter.VERTICAL
        )
        self.visual_splitter.pack(fill="both", expand=True)

        # --- TOP: DECK CANVAS ---
        deck_frame = tb.Frame(self.visual_splitter)
        self.visual_splitter.add(deck_frame, weight=3)

        tab_header = tb.Frame(deck_frame)
        tab_header.pack(fill="x")

        self.notebook_vis = tb.Notebook(tab_header)
        self.notebook_vis.pack(side="left", fill="x", expand=True)
        self.notebook_vis.bind("<<NotebookTabChanged>>", self._on_tab_changed_vis)

        tb.Button(
            tab_header,
            text="➕",
            width=3,
            command=self._create_new_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="✏️",
            width=3,
            command=self._rename_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="🗑️",
            width=3,
            command=self._delete_tab,
            bootstyle="danger-outline",
        ).pack(side="right", padx=2, pady=2)

        deck_controls = tb.Frame(
            deck_frame, style="Card.TFrame", padding=Theme.scaled_val(5)
        )
        deck_controls.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        self.lbl_deck_title_vis = tb.Label(
            deck_controls,
            text="ACTIVE DECK (0)",
            font=Theme.scaled_font(12, "bold"),
            bootstyle="success",
        )
        self.lbl_deck_title_vis.pack(side="left", padx=Theme.scaled_val(5))

        tb.Button(
            deck_controls,
            text="Auto-Lands",
            bootstyle="warning",
            command=self._apply_auto_lands,
        ).pack(side="left", padx=Theme.scaled_val(10))

        tb.Button(
            deck_controls,
            text="Clear",
            bootstyle="danger-outline",
            command=self._clear_deck,
        ).pack(side="left", padx=5)
        tb.Button(
            deck_controls,
            text="Add All",
            bootstyle="secondary-outline",
            command=self._add_all_to_deck,
        ).pack(side="left", padx=5)

        sort_frame = tb.Frame(deck_controls)
        sort_frame.pack(side="left", padx=Theme.scaled_val(15))
        tb.Label(sort_frame, text="Sort:").pack(side="left", padx=2)
        deck_sort_cb = tb.Combobox(
            sort_frame,
            textvariable=self.deck_sort_var,
            values=["Color", "CMC", "Rarity", "Type"],
            state="readonly",
            width=7,
        )
        deck_sort_cb.pack(side="left", padx=2)
        deck_sort_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_data())

        self.basics_frame_vis = tb.Frame(deck_controls)
        self.basics_frame_vis.pack(side="right")
        self.basic_buttons_vis = {}
        for sym, name, style in [
            ("W", "Plains", "light"),
            ("U", "Island", "info"),
            ("B", "Swamp", "dark"),
            ("R", "Mountain", "danger"),
            ("G", "Forest", "success"),
        ]:
            btn = tb.Button(
                self.basics_frame_vis,
                text=f"{sym}: 0",
                bootstyle=style,
                width=5,
                padding=Theme.scaled_val(3),
            )
            btn.bind("<ButtonRelease-1>", lambda e, n=name: self._add_basic(n))
            btn.bind("<Button-3>", lambda e, n=name: self._remove_basic(n))
            btn.pack(side="left", padx=1)
            self.basic_buttons_vis[name] = btn

        deck_canvas_container = tb.Frame(deck_frame)
        deck_canvas_container.pack(side="top", fill="both", expand=True)
        deck_canvas_container.rowconfigure(0, weight=1)
        deck_canvas_container.columnconfigure(0, weight=1)

        self.deck_canvas = tkinter.Canvas(
            deck_canvas_container, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.deck_scroll = AutoScrollbar(
            deck_canvas_container, orient="horizontal", command=self.deck_canvas.xview
        )
        self.deck_canvas.configure(xscrollcommand=self.deck_scroll.set)
        self.deck_canvas.grid(row=0, column=0, sticky="nsew")
        self.deck_scroll.grid(row=1, column=0, sticky="ew")

        # --- BOTTOM: POOL CANVAS ---
        pool_frame = tb.Frame(self.visual_splitter)
        self.visual_splitter.add(pool_frame, weight=2)

        pool_header = tb.Frame(pool_frame)
        pool_header.pack(fill="x", pady=Theme.scaled_val(5))

        self.lbl_pool_title_vis = tb.Label(
            pool_header, text="MASTER POOL (0)", font=Theme.scaled_font(12, "bold")
        )
        self.lbl_pool_title_vis.pack(side="left")

        filter_frame = tb.Frame(pool_header)
        filter_frame.pack(side="right")

        tb.Label(filter_frame, text="Sort:").pack(side="left", padx=2)
        sort_cb = tb.Combobox(
            filter_frame,
            textvariable=self.pool_sort_var,
            values=["Color", "CMC", "Rarity", "Type"],
            state="readonly",
            width=7,
        )
        sort_cb.pack(side="left", padx=2)
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_data())
        tb.Label(filter_frame, text=" | ").pack(side="left")

        tb.Checkbutton(
            filter_frame,
            text="Creatures",
            variable=self.filter_vars["creatures"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Spells",
            variable=self.filter_vars["spells"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Lands",
            variable=self.filter_vars["lands"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)

        tb.Label(filter_frame, text=" | ").pack(side="left")

        for c, col in [
            ("W", "light"),
            ("U", "info"),
            ("B", "dark"),
            ("R", "danger"),
            ("G", "success"),
            ("M", "warning"),
            ("C", "secondary"),
        ]:
            btn = tb.Checkbutton(
                filter_frame,
                text=c,
                variable=self.filter_vars[c],
                bootstyle=f"{col}-toolbutton",
                command=self._refresh_data,
            )
            btn.pack(side="left", padx=1)

        pool_canvas_container = tb.Frame(pool_frame)
        pool_canvas_container.pack(side="top", fill="both", expand=True)
        pool_canvas_container.rowconfigure(0, weight=1)
        pool_canvas_container.columnconfigure(0, weight=1)

        self.pool_canvas = tkinter.Canvas(
            pool_canvas_container, bg=Theme.BG_PRIMARY, highlightthickness=0
        )
        self.pool_scroll = AutoScrollbar(
            pool_canvas_container, orient="horizontal", command=self.pool_canvas.xview
        )
        self.pool_canvas.configure(xscrollcommand=self.pool_scroll.set)
        self.pool_canvas.grid(row=0, column=0, sticky="nsew")
        self.pool_scroll.grid(row=1, column=0, sticky="ew")

        # Cross-platform mouse wheel scrolling horizontally for canvases
        def _bind_horizontal_scroll(canvas):
            import sys

            if sys.platform == "darwin":
                canvas.bind(
                    "<MouseWheel>",
                    lambda e: canvas.xview_scroll(-1 * e.delta, "units"),
                    add="+",
                )
            elif sys.platform == "win32":
                canvas.bind(
                    "<MouseWheel>",
                    lambda e: canvas.xview_scroll(-1 * (int(e.delta) // 120), "units"),
                    add="+",
                )
            else:
                canvas.bind(
                    "<Button-4>", lambda e: canvas.xview_scroll(-1, "units"), add="+"
                )
                canvas.bind(
                    "<Button-5>", lambda e: canvas.xview_scroll(1, "units"), add="+"
                )

        _bind_horizontal_scroll(self.deck_canvas)
        _bind_horizontal_scroll(self.pool_canvas)

        self._bind_canvas_dnd(self.pool_canvas, is_pool=True)
        self._bind_canvas_dnd(self.deck_canvas, is_pool=False)

    def _build_hud(self, parent):
        self.hud_frame = tb.Labelframe(
            parent, text=" DECK ANALYTICS ", padding=Theme.scaled_val(10)
        )
        self.hud_frame.pack(fill="x", side="bottom", pady=Theme.scaled_val((10, 0)))
        self.hud_frame.columnconfigure(0, weight=1)
        self.hud_frame.columnconfigure(1, weight=1)
        self.hud_frame.columnconfigure(2, weight=1)

        comp_frame = tb.Frame(self.hud_frame)
        comp_frame.grid(row=0, column=0, sticky="nw")
        tb.Label(
            comp_frame,
            text="COMPOSITION",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.lbl_comp_stats = tb.Label(
            comp_frame,
            text="Creatures: 0\nSpells: 0\nLands: 0",
            font=Theme.scaled_font(9),
        )
        self.lbl_comp_stats.pack(anchor="w", pady=Theme.scaled_val(5))

        curve_frame = tb.Frame(self.hud_frame)
        curve_frame.grid(row=0, column=1, sticky="nsew")
        tb.Label(
            curve_frame,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.curve_plot = ManaCurvePlot(
            curve_frame,
            ideal_distribution=self.configuration.card_logic.deck_mid.distribution,
        )
        self.curve_plot.pack(fill="both", expand=True)

        color_frame = tb.Frame(self.hud_frame)
        color_frame.grid(row=0, column=2, sticky="nsew")
        tb.Label(
            color_frame,
            text="BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.type_chart = TypePieChart(color_frame)
        self.type_chart.pack(fill="both", expand=True)

    def _on_close(self):
        self.session.save_session()
        self.destroy()

    def _create_new_tab(self):
        name = simpledialog.askstring(
            "New Deck", "Enter a name for the new deck variant:", parent=self
        )
        if name:
            self.session.create_variant(name)
            self._refresh_tabs()

    def _rename_tab(self):
        if self.session.active_variant_name:
            new_name = simpledialog.askstring(
                "Rename Deck",
                "Enter new name:",
                initialvalue=self.session.active_variant_name,
                parent=self,
            )
            if new_name and self.session.rename_variant(
                self.session.active_variant_name, new_name
            ):
                self._refresh_tabs()

    def _delete_tab(self):
        if len(self.session.variants) > 1:
            if messagebox.askyesno(
                "Delete",
                f"Are you sure you want to delete '{self.session.active_variant_name}'?",
                parent=self,
            ):
                self.session.delete_variant(self.session.active_variant_name)
                self._refresh_tabs()
        else:
            messagebox.showwarning(
                "Cannot Delete", "You must have at least one deck variant.", parent=self
            )

    def _refresh_tabs(self):
        for nb in [self.notebook_list, getattr(self, "notebook_vis", None)]:
            if not nb:
                continue
            for tab in nb.tabs():
                nb.forget(tab)
            for variant_name in self.session.variants.keys():
                f = tb.Frame(nb)
                nb.add(f, text=f" {variant_name} ")
                if variant_name == self.session.active_variant_name:
                    nb.select(f)

    def _on_tab_changed_list(self, event):
        self._handle_tab_change(self.notebook_list)

    def _on_tab_changed_vis(self, event):
        self._handle_tab_change(self.notebook_vis)

    def _handle_tab_change(self, notebook):
        try:
            current_tab_idx = notebook.index(notebook.select())
            tab_name = notebook.tab(current_tab_idx, "text").strip()
            if tab_name in self.session.variants:
                self.session.active_variant_name = tab_name
                # Sync other notebook
                other_nb = (
                    self.notebook_vis
                    if notebook == self.notebook_list
                    else self.notebook_list
                )
                for i in range(other_nb.index("end")):
                    if other_nb.tab(i, "text").strip() == tab_name:
                        other_nb.select(i)
                        break
                self._refresh_data()
        except:
            pass

    def _on_auto_generate(self):
        self.lbl_deck_title_list.config(
            text="GENERATING SHELLS...", bootstyle="warning"
        )
        if hasattr(self, "lbl_deck_title_vis"):
            self.lbl_deck_title_vis.config(
                text="GENERATING SHELLS...", bootstyle="warning"
            )
        self.update_idletasks()

        tier_data = self.app_context.orchestrator.scanner.retrieve_tier_data()
        generate_sealed_shells(self.session, self.metrics, tier_data)

        self._refresh_tabs()
        self._refresh_data()

    def _clear_deck(self):
        main_deck, _ = self.session.get_active_deck_lists()
        for c in main_deck:
            self.session.move_to_sideboard(c["name"], c.get("count", 1))
        self._refresh_data()

    def _add_all_to_deck(self):
        _, sideboard = self.session.get_active_deck_lists()
        for c in sideboard:
            self.session.move_to_main(c["name"], c.get("count", 1))
        self._refresh_data()

    def _refresh_data(self):
        if hasattr(self.app_context, "orchestrator"):
            self.metrics = self.app_context.orchestrator.scanner.retrieve_set_metrics()

        main_deck, sideboard = self.session.get_active_deck_lists()

        pool_count = sum(c.get("count", 1) for c in sideboard)
        deck_count = sum(c.get("count", 1) for c in main_deck)

        self.lbl_pool_title_list.config(text=f"MASTER POOL ({pool_count})")
        if hasattr(self, "lbl_pool_title_vis"):
            self.lbl_pool_title_vis.config(text=f"MASTER POOL ({pool_count})")

        deck_style = "success" if deck_count == 40 else "warning"
        self.lbl_deck_title_list.config(
            text=f"ACTIVE DECK ({deck_count})", bootstyle=deck_style
        )
        if hasattr(self, "lbl_deck_title_vis"):
            self.lbl_deck_title_vis.config(
                text=f"ACTIVE DECK ({deck_count})", bootstyle=deck_style
            )

        show_c, show_s, show_l = (
            self.filter_vars["creatures"].get(),
            self.filter_vars["spells"].get(),
            self.filter_vars["lands"].get(),
        )
        filtered_sb = []
        for c in sideboard:
            t = c.get("types", [])
            is_c = "Creature" in t
            is_l = "Land" in t
            is_s = not is_c and not is_l

            # 1. Type filter
            if is_c and not show_c:
                continue
            if is_s and not show_s:
                continue
            if is_l and not show_l:
                continue

            # 2. Color filter
            colors = c.get("colors", [])
            is_colorless = len(colors) == 0
            is_multi = len(colors) > 1

            if is_multi:
                if not self.filter_vars["M"].get():
                    continue
            elif is_colorless:
                if not self.filter_vars["C"].get():
                    continue
            else:
                col = colors[0]
                if col in self.filter_vars and not self.filter_vars[col].get():
                    continue

            filtered_sb.append(c)

        if self.view_mode == "list":
            self._populate_tree(self.pool_manager, filtered_sb)
            self._populate_tree(self.deck_manager, main_deck)
        else:
            self._populate_canvas(
                self.pool_canvas, filtered_sb, self.pool_sort_var.get()
            )
            self._populate_canvas(self.deck_canvas, main_deck, self.deck_sort_var.get())

        self._update_hud(main_deck)
        self._update_basics_toolbar(main_deck)

    def _populate_tree(self, manager, card_list):
        tree = manager.tree
        for item in tree.get_children():
            tree.delete(item)

        card_list.sort(key=lambda x: (x.get("cmc", 0), x.get("name", "")))

        from src.card_logic import format_win_rate, row_color_tag, format_types_for_ui

        active_filter = "All Decks"

        for idx, card in enumerate(card_list):
            row_values = []
            for field in manager.active_fields:
                if field == "name":
                    row_values.append(card.get("name", "Unknown"))
                elif field == "count":
                    row_values.append(str(card.get("count", 1)))
                elif field == "cmc":
                    row_values.append(str(card.get("cmc", 0)))
                elif field == "types":
                    row_values.append(format_types_for_ui(card.get("types", [])))
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "tags":
                    raw_tags = card.get("tags", [])
                    row_values.append(
                        " ".join(
                            [
                                constants.TAG_VISUALS.get(t, t).split(" ")[0]
                                for t in raw_tags
                            ]
                        )
                        if raw_tags
                        else "-"
                    )
                else:
                    stats = card.get("deck_colors", {}).get(active_filter, {})
                    val = stats.get(field, 0.0)
                    row_values.append(
                        format_win_rate(
                            val,
                            active_filter,
                            field,
                            self.metrics,
                            self.configuration.settings.result_format,
                        )
                    )

            tag = (
                row_color_tag(card.get("mana_cost", ""))
                if self.configuration.settings.card_colors_enabled
                else ("bw_odd" if idx % 2 == 0 else "bw_even")
            )
            tree.insert(
                "",
                "end",
                iid=str(idx),
                text=card.get("name", ""),
                values=row_values,
                tags=(tag,),
            )

        if hasattr(tree, "reapply_sort"):
            tree.reapply_sort()

    def _populate_canvas(self, canvas, cards, sort_by):
        canvas.delete("all")
        if not cards:
            return

        columns = {}
        col_labels = {}
        col_order = []

        if sort_by == "Color":
            for c in cards:
                col_id = self._get_color_group(c)
                columns.setdefault(col_id, []).append(c)
            col_order = [0, 1, 2, 3, 4, 5, 6, 7]
            col_labels = {
                0: "White",
                1: "Blue",
                2: "Black",
                3: "Red",
                4: "Green",
                5: "Multicolor",
                6: "Colorless",
                7: "Lands",
            }
        elif sort_by == "CMC":
            for c in cards:
                if "Land" in c.get("types", []):
                    columns.setdefault(7, []).append(c)
                else:
                    cmc = min(6, int(c.get("cmc", 0)))
                    columns.setdefault(cmc, []).append(c)
            col_order = [0, 1, 2, 3, 4, 5, 6, 7]
            col_labels = {
                0: "0 CMC",
                1: "1 CMC",
                2: "2 CMC",
                3: "3 CMC",
                4: "4 CMC",
                5: "5 CMC",
                6: "6+ CMC",
                7: "Lands",
            }
        elif sort_by == "Rarity":
            for c in cards:
                if "Land" in c.get("types", []) and "Basic" in c.get("types", []):
                    columns.setdefault(4, []).append(c)
                    continue
                rarity = str(c.get("rarity", "common")).lower()
                if rarity == "common":
                    columns.setdefault(0, []).append(c)
                elif rarity == "uncommon":
                    columns.setdefault(1, []).append(c)
                elif rarity in ["rare", "mythic"]:
                    columns.setdefault(2, []).append(c)
                else:
                    columns.setdefault(0, []).append(c)
            col_order = [0, 1, 2, 4]
            col_labels = {
                0: "Common",
                1: "Uncommon",
                2: "Rare/Mythic",
                4: "Basic Lands",
            }
        elif sort_by == "Type":
            for c in cards:
                t = c.get("types", [])
                if "Creature" in t:
                    columns.setdefault(0, []).append(c)
                elif "Instant" in t or "Sorcery" in t:
                    columns.setdefault(1, []).append(c)
                elif "Artifact" in t or "Enchantment" in t:
                    columns.setdefault(2, []).append(c)
                elif "Planeswalker" in t or "Battle" in t:
                    columns.setdefault(3, []).append(c)
                elif "Land" in t:
                    columns.setdefault(4, []).append(c)
                else:
                    columns.setdefault(5, []).append(c)
            col_order = [0, 1, 2, 3, 4, 5]
            col_labels = {
                0: "Creatures",
                1: "Instants/Sorceries",
                2: "Artifacts/Enchantments",
                3: "Planeswalkers/Battles",
                4: "Lands",
                5: "Other",
            }

        scale = Theme.current_scale
        CARD_W = int(130 * scale)
        CARD_H = int(182 * scale)
        Y_OFFSET = int(32 * scale)  # Increased spacing to expose title bars beautifully
        X_SPACE = int(140 * scale)

        max_y = 0
        current_x = Theme.scaled_val(15)

        for col_id in col_order:
            if col_id not in columns:
                continue
            col_cards = columns[col_id]
            col_cards.sort(key=lambda x: (x.get("cmc", 0), x.get("name", "")))

            col_count = sum(c.get("count", 1) for c in col_cards)
            canvas.create_text(
                current_x,
                Theme.scaled_val(10),
                text=f"{col_labels[col_id]} ({col_count})",
                fill=Theme.TEXT_MAIN,
                font=Theme.scaled_font(11, "bold"),
                anchor="nw",
            )

            current_y = Theme.scaled_val(35)
            for card in col_cards:
                for _ in range(card.get("count", 1)):
                    inst_tag = f"inst_{id(card)}_{current_y}"
                    overlay_tag = f"overlay_{inst_tag}"
                    group_tags = ("card", f"cardname_{card['name']}", inst_tag)
                    overlay_group = (
                        "card",
                        f"cardname_{card['name']}",
                        inst_tag,
                        overlay_tag,
                    )

                    canvas.create_rectangle(
                        current_x,
                        current_y,
                        current_x + CARD_W,
                        current_y + CARD_H,
                        fill=Theme.BG_TERTIARY,
                        outline=Theme.BG_SECONDARY,
                        tags=group_tags,
                    )

                    # Store the ID of the placeholder text so it can be erased when the image loads
                    placeholder_text_id = canvas.create_text(
                        current_x + 5,
                        current_y + 5,
                        text=card.get("name", ""),
                        fill=Theme.TEXT_MAIN,
                        font=Theme.scaled_font(8),
                        width=CARD_W - 10,
                        anchor="nw",
                        tags=overlay_group,
                    )

                    self._load_canvas_image(
                        card,
                        canvas,
                        current_x,
                        current_y,
                        CARD_W,
                        CARD_H,
                        group_tags,
                        overlay_tag,
                        placeholder_text_id,
                    )

                    gihwr = (
                        card.get("deck_colors", {})
                        .get("All Decks", {})
                        .get("gihwr", 0.0)
                    )
                    if gihwr > 0:
                        bg_col = (
                            Theme.SUCCESS
                            if gihwr >= 58.0
                            else (Theme.WARNING if gihwr >= 54.0 else Theme.ERROR)
                        )
                        # Much smaller, cleaner badge in the top left so it doesn't cover mana costs
                        rect_w = Theme.scaled_val(28)
                        rect_h = Theme.scaled_val(14)
                        rx = current_x + 2
                        ry = current_y + 2

                        canvas.create_rectangle(
                            rx,
                            ry,
                            rx + rect_w,
                            ry + rect_h,
                            fill=bg_col,
                            outline="",
                            tags=overlay_group,
                        )
                        canvas.create_text(
                            rx + (rect_w / 2),
                            ry + (rect_h / 2),
                            text=f"{gihwr:.1f}",
                            fill="#ffffff",
                            font=Theme.scaled_font(7, "bold"),
                            tags=overlay_group,
                        )

                    current_y += Y_OFFSET

            max_y = max(max_y, current_y + CARD_H)
            current_x += X_SPACE

        canvas.configure(scrollregion=(0, 0, current_x, max_y + Theme.scaled_val(20)))

    def _get_color_group(self, card):
        if "Land" in card.get("types", []):
            return 7
        colors = card.get("colors", [])
        if len(colors) == 0:
            return 6
        if len(colors) > 1:
            return 5
        mapping = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        return mapping.get(colors[0], 6)

    def _load_canvas_image(self, card, canvas, x, y, w, h, tags, overlay_tag, text_id):
        name = card.get("name")
        urls = card.get("image", [])
        if not urls and name in constants.BASIC_LANDS:
            import urllib.parse

            urls = [
                f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(name)}&format=image"
            ]
        if not urls:
            return

        img_url = urls[0]
        if img_url.startswith("/static"):
            img_url = f"https://www.17lands.com{img_url}"
        elif "scryfall" in img_url and "format=image" not in img_url:
            img_url = img_url.replace("/small/", "/large/").replace(
                "/normal/", "/large/"
            )

        cache_key = hashlib.md5(img_url.encode("utf-8")).hexdigest()

        if cache_key in self.image_cache:
            if canvas.winfo_exists():
                canvas.create_image(
                    x, y, image=self.image_cache[cache_key], anchor="nw", tags=tags
                )
                canvas.delete(
                    text_id
                )  # Delete the placeholder text since the actual art is available
                # Raise ONLY the stat box above the image
                for t in canvas.find_withtag(overlay_tag):
                    canvas.tag_raise(t)
            return

        def fetch():
            cache_dir = os.path.join(constants.TEMP_FOLDER, "Images")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{cache_key}.jpg")
            try:
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as f:
                        img_data = f.read()
                else:
                    r = requests.get(
                        img_url, headers={"User-Agent": "MTGADraftTool/5.0"}, timeout=8
                    )
                    r.raise_for_status()
                    img_data = r.content
                    with open(cache_path, "wb") as f:
                        f.write(img_data)

                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((w, h), Image.Resampling.LANCZOS)

                def apply_img():
                    if canvas.winfo_exists():
                        tk_img = ImageTk.PhotoImage(img)
                        self.image_cache[cache_key] = tk_img
                        canvas.create_image(x, y, image=tk_img, anchor="nw", tags=tags)
                        canvas.delete(
                            text_id
                        )  # Delete the placeholder text since the actual art is available
                        # Raise ONLY the stat box above the image
                        for t in canvas.find_withtag(overlay_tag):
                            canvas.tag_raise(t)

                self.after(0, apply_img)
            except Exception:
                pass

        self.image_executor.submit(fetch)

    def _update_hud(self, main_deck):
        metrics = get_deck_metrics(main_deck)
        self.lbl_comp_stats.config(
            text=f"Creatures: {metrics.creature_count}\nSpells: {metrics.noncreature_count}\nLands: {metrics.total_cards - metrics.creature_count - metrics.noncreature_count}\nAvg CMC: {metrics.cmc_average:.2f}"
        )
        self.curve_plot.update_curve(metrics.distribution_all)

        type_counts = {
            "Creature": metrics.creature_count,
            "Instant/Sorcery": 0,
            "Artifact/Enchantment": 0,
            "Land": 0,
        }
        for c in main_deck:
            t, count = c.get("types", []), c.get("count", 1)
            if "Instant" in t or "Sorcery" in t:
                type_counts["Instant/Sorcery"] += count
            elif "Artifact" in t or "Enchantment" in t:
                type_counts["Artifact/Enchantment"] += count
            elif "Land" in t:
                type_counts["Land"] += count
        self.type_chart.update_counts(type_counts)

    def _update_basics_toolbar(self, main_deck):
        counts = {
            n: 0
            for _, n, _ in [
                ("W", "Plains", ""),
                ("U", "Island", ""),
                ("B", "Swamp", ""),
                ("R", "Mountain", ""),
                ("G", "Forest", ""),
            ]
        }
        for c in main_deck:
            if c["name"] in counts:
                counts[c["name"]] += c.get("count", 1)

        symbol_map = {
            "Plains": "W",
            "Island": "U",
            "Swamp": "B",
            "Mountain": "R",
            "Forest": "G",
        }
        for name, btn in self.basic_buttons_list.items():
            btn.configure(text=f"{symbol_map[name]}: {counts[name]}")
        if hasattr(self, "basic_buttons_vis"):
            for name, btn in self.basic_buttons_vis.items():
                btn.configure(text=f"{symbol_map[name]}: {counts[name]}")

    def _bind_dnd_list(self, tree, is_pool=True):
        tree._dnd_bound = True
        tree.bind(
            "<ButtonPress-1>",
            lambda e: self._on_list_drag_start(e, tree, is_pool),
            add="+",
        )
        tree.bind("<B1-Motion>", lambda e: self._on_list_drag_motion(e, tree), add="+")
        tree.bind(
            "<ButtonRelease-1>",
            lambda e: self._on_list_drag_release(e, tree, is_pool),
            add="+",
        )
        tree.bind(
            "<Button-3>", lambda e: self._on_context_menu(e, tree, is_pool), add="+"
        )
        tree.bind(
            "<Control-Button-1>",
            lambda e: self._on_context_menu(e, tree, is_pool),
            add="+",
        )

    def _bind_canvas_dnd(self, canvas, is_pool=True):
        canvas.bind(
            "<ButtonPress-1>",
            lambda e: self._on_canvas_press(e, canvas, is_pool),
            add="+",
        )
        canvas.bind("<B1-Motion>", self._on_canvas_motion, add="+")
        canvas.bind("<ButtonRelease-1>", self._on_canvas_release, add="+")
        canvas.bind(
            "<Button-3>",
            lambda e: self._on_canvas_right_click(e, canvas, is_pool),
            add="+",
        )
        canvas.bind(
            "<Control-Button-1>",
            lambda e: self._on_canvas_right_click(e, canvas, is_pool),
            add="+",
        )

    def _on_list_drag_start(self, event, tree, is_pool):
        self._drag_data = None
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        tree.selection_set(row_id)
        card_name = tree.item(row_id).get("text")
        if card_name:
            self._drag_data = {
                "name": card_name,
                "x": event.x_root,
                "y": event.y_root,
                "is_pool": is_pool,
            }

    def _on_list_drag_motion(self, event, tree):
        if getattr(self, "_drag_data", None):
            tree.configure(cursor="hand2")

    def _on_list_drag_release(self, event, tree, is_pool):
        tree.configure(cursor="")
        if not getattr(self, "_drag_data", None):
            return

        dx, dy = abs(event.x_root - self._drag_data["x"]), abs(
            event.y_root - self._drag_data["y"]
        )
        card_name = self._drag_data["name"]

        if dx >= 5 or dy >= 5:
            target_widget = self.deck_manager if is_pool else self.pool_manager
            rx, ry = target_widget.winfo_rootx(), target_widget.winfo_rooty()
            rw, rh = target_widget.winfo_width(), target_widget.winfo_height()
            if rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh:
                if is_pool:
                    self.session.move_to_main(card_name)
                else:
                    self.session.move_to_sideboard(card_name)
                self._refresh_data()
        else:
            if is_pool:
                self.session.move_to_main(card_name)
            else:
                self.session.move_to_sideboard(card_name)
            self._refresh_data()
        self._drag_data = None

    def _on_canvas_press(self, event, canvas, is_pool):
        item = canvas.find_withtag("current")
        if not item:
            return
        tags = canvas.gettags(item[0])
        inst_tag = next((t for t in tags if t.startswith("inst_")), None)
        name_tag = next((t for t in tags if t.startswith("cardname_")), None)

        if inst_tag and name_tag:
            self._drag_data = {
                "name": name_tag.replace("cardname_", ""),
                "inst": inst_tag,
                "x": event.x_root,
                "y": event.y_root,
                "canvas": canvas,
                "is_pool": is_pool,
            }
            for it in canvas.find_withtag(inst_tag):
                canvas.tag_raise(it)

    def _on_canvas_motion(self, event):
        if getattr(self, "_drag_data", None):
            dx = event.x_root - self._drag_data["x"]
            dy = event.y_root - self._drag_data["y"]
            self._drag_data["canvas"].move(self._drag_data["inst"], dx, dy)
            self._drag_data["x"] = event.x_root
            self._drag_data["y"] = event.y_root

    def _on_canvas_release(self, event):
        if getattr(self, "_drag_data", None):
            data = self._drag_data
            self._drag_data = None

            target = event.widget.winfo_containing(event.x_root, event.y_root)

            if data["is_pool"] and target == self.deck_canvas:
                self.session.move_to_main(data["name"])
            elif not data["is_pool"] and target == self.pool_canvas:
                self.session.move_to_sideboard(data["name"])
            else:
                # Click logic (no move)
                if data["is_pool"]:
                    self.session.move_to_main(data["name"])
                else:
                    self.session.move_to_sideboard(data["name"])

            self._refresh_data()

    def _on_canvas_right_click(self, event, canvas, is_pool):
        item = canvas.find_withtag("current")
        if not item:
            return
        tags = canvas.gettags(item[0])
        name_tag = next((t for t in tags if t.startswith("cardname_")), None)
        if name_tag:
            name = name_tag.replace("cardname_", "")

            card = next(
                (c for c in self.session.master_pool if c.get("name") == name), None
            )
            if card:
                CardToolTip.create(
                    canvas,
                    card,
                    self.configuration.features.images_enabled,
                    constants.UI_SIZE_DICT.get(
                        self.configuration.settings.ui_size, 1.0
                    ),
                )

    def _on_context_menu(self, event, tree, is_pool):
        region = tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        row_id = tree.identify_row(event.y)
        if not row_id:
            return

        tree.selection_set(row_id)
        card_name = tree.item(row_id).get("text")

        if card_name:
            card = next(
                (c for c in self.session.master_pool if c.get("name") == card_name),
                None,
            )
            if not card and card_name in constants.BASIC_LANDS:
                card = {"name": card_name, "cmc": 0, "types": ["Land", "Basic"]}

            if card:
                CardToolTip.create(
                    tree,
                    card,
                    self.configuration.features.images_enabled,
                    constants.UI_SIZE_DICT.get(
                        self.configuration.settings.ui_size, 1.0
                    ),
                )

    def _add_basic(self, name):
        self.session.move_to_main(name)
        self._refresh_data()

    def _remove_basic(self, name):
        self.session.move_to_sideboard(name)
        self._refresh_data()

    def _apply_auto_lands(self):
        from src.card_logic import calculate_dynamic_mana_base, get_strict_colors

        main_deck, _ = self.session.get_active_deck_lists()

        for c in main_deck:
            if c["name"] in constants.BASIC_LANDS:
                self.session.move_to_sideboard(c["name"], c.get("count", 1))

        main_deck, _ = self.session.get_active_deck_lists()
        spells = [c for c in main_deck if "Land" not in c.get("types", [])]
        non_basic_lands = [c for c in main_deck if "Land" in c.get("types", [])]

        if not spells:
            return

        colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        needed = max(0, 40 - len(spells) - len(non_basic_lands))

        basics_to_add = calculate_dynamic_mana_base(
            spells, non_basic_lands, colors, forced_count=needed
        )
        for b in basics_to_add:
            self.session.move_to_main(b["name"], 1)

        self._refresh_data()

    def _import_deck_from_clipboard(self):
        try:
            text = self.clipboard_get()
            import re

            deck_cards = []
            for line in text.split("\n"):
                line = line.strip()
                if not line or line.lower() in (
                    "deck",
                    "sideboard",
                    "commander",
                    "companion",
                ):
                    continue

                match = re.match(r"^(\d+)\s+([^(]+)", line)
                if match:
                    count = int(match.group(1))
                    name = match.group(2).strip()
                    deck_cards.append({"name": name, "count": count})

            if not deck_cards:
                messagebox.showwarning(
                    "Import Failed",
                    "No valid MTGA format cards found in clipboard.",
                    parent=self,
                )
                return

            self.session.create_variant("Imported Deck")
            self.session.variants[
                self.session.active_variant_name
            ].main_deck_counts.clear()

            missing_cards = []
            for req in deck_cards:
                from src.utils import sanitize_card_name

                clean_name = sanitize_card_name(req["name"])
                success = self.session.move_to_main(clean_name, req["count"])
                if not success:
                    success = self.session.move_to_main(req["name"], req["count"])
                    if not success:
                        missing_cards.append(req["name"])

            self._refresh_tabs()
            self._refresh_data()

            if missing_cards:
                msg = "Deck imported, but the following cards were skipped because they are not in your pool (or you exceeded your owned quantity limits):\n\n"
                msg += ", ".join(missing_cards[:10])
                if len(missing_cards) > 10:
                    msg += f" ...and {len(missing_cards) - 10} more."
                messagebox.showwarning("Partial Import", msg, parent=self)
            else:
                messagebox.showinfo(
                    "Success", "Deck imported successfully!", parent=self
                )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import deck: {e}", parent=self)

    def _export_active_deck(self):
        main_deck, sideboard = self.session.get_active_deck_lists()
        export_text = copy_deck(main_deck, sideboard)
        self.clipboard_clear()
        self.clipboard_append(export_text)
        messagebox.showinfo(
            "Export Successful", "Deck copied to clipboard in MTGA format!", parent=self
        )

    def _export_to_sealeddeck_tech(self):
        main_deck, sideboard = self.session.get_active_deck_lists()
        mtga_payload = copy_deck(main_deck, sideboard)

        lbl = (
            self.lbl_deck_title_vis
            if self.view_mode == "visual"
            else self.lbl_deck_title_list
        )
        lbl.config(text="EXPORTING TO BROWSER...", bootstyle="warning")
        self.update_idletasks()

        import threading

        def _api_call():
            try:
                response = requests.post(
                    "https://sealeddeck.tech/api/pools",
                    json={"pool": mtga_payload},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    url = data.get("url")
                    if url:
                        open_file(url)
                    else:
                        raise ValueError("No URL returned from API")
                else:
                    raise Exception(f"HTTP {response.status_code}")
            except Exception as e:

                def _err():
                    self.clipboard_clear()
                    self.clipboard_append(mtga_payload)
                    messagebox.showwarning(
                        "API Error",
                        "Could not reach Sealeddeck.tech automatically.\n\nYour deck has been copied to the clipboard. You can paste it manually at sealeddeck.tech.",
                        parent=self,
                    )

                self.after(0, _err)
            finally:
                self.after(0, self._refresh_data)

        threading.Thread(target=_api_call, daemon=True).start()
