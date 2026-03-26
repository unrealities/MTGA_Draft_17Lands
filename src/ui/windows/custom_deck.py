"""
src/ui/windows/custom_deck.py
Interactive Custom Deck Builder.
Allows users to manually construct decks, add basic lands, and run
Monte Carlo simulations on their custom creations.
"""

import tkinter
from tkinter import ttk
from typing import Dict, Any, List
import random
import requests
import urllib.parse
import hashlib
import os
import io
import re
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk

from src import constants
from src.card_logic import (
    copy_deck,
    stack_cards,
    calculate_dynamic_mana_base,
    format_types_for_ui,
    get_strict_colors,
    is_castable,
    get_functional_cmc,
)
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip, AutoScrollbar
from src.utils import bind_scroll


class CustomDeckPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration, app_context):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration
        self.app_context = app_context

        self.deck_list: List[Dict] = []
        self.sb_list: List[Dict] = []
        self.known_pool_size = 0

        self.image_executor = ThreadPoolExecutor(max_workers=4)
        self.sim_executor = ThreadPoolExecutor(max_workers=1)
        self.hand_images = []
        self.hand_frames = []

        # Seed default columns in configuration if they don't exist
        if "custom_deck_main" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["custom_deck_main"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]
        if "custom_deck_sb" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["custom_deck_sb"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]

        self._build_ui()

    @property
    def main_table(self) -> ttk.Treeview:
        return self.deck_manager.tree if hasattr(self, "deck_manager") else None

    @property
    def sb_table(self) -> ttk.Treeview:
        return self.sb_manager.tree if hasattr(self, "sb_manager") else None

    def import_deck(self, deck_cards: List[Dict], sb_cards: List[Dict]):
        """Receives a deck from the Suggest Deck tab."""
        import copy

        self.deck_list = copy.deepcopy(deck_cards)
        self.sb_list = copy.deepcopy(sb_cards)

        raw_pool = self.draft.retrieve_taken_cards()
        self.known_pool_size = len(raw_pool) if raw_pool else 0

        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

        for widget in self.sim_frame.winfo_children():
            widget.destroy()
        self._clear_sample_hand()
        self.notebook.select(self.builder_tab)

    def refresh(self):
        """Appends newly drafted cards to the sideboard."""
        raw_pool = self.draft.retrieve_taken_cards()
        if not raw_pool:
            self.deck_list = []
            self.sb_list = []
            self.known_pool_size = 0
            self._update_tables()
            self._update_basics_toolbar()
            return

        if len(raw_pool) > self.known_pool_size:
            stacked_pool = stack_cards(raw_pool)

            for pool_card in stacked_pool:
                name = pool_card["name"]
                total_count = pool_card.get("count", 1)

                in_deck = next(
                    (c for c in self.deck_list if c["name"] == name), {}
                ).get("count", 0)
                in_sb = next((c for c in self.sb_list if c["name"] == name), {}).get(
                    "count", 0
                )

                diff = total_count - (in_deck + in_sb)
                if diff > 0:
                    sb_card = next((c for c in self.sb_list if c["name"] == name), None)
                    if sb_card:
                        sb_card["count"] += diff
                    else:
                        new_c = dict(pool_card)
                        new_c["count"] = diff
                        self.sb_list.append(new_c)

            self.known_pool_size = len(raw_pool)
            self._update_tables()
            self._render_deck_stats()

    def _build_ui(self):
        # --- CONTROL BAR ---
        self.header = ttk.Frame(self, style="Card.TFrame", padding=Theme.scaled_val(5))
        self.header.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        ttk.Button(
            self.header,
            text="Clear",
            bootstyle="danger-outline",
            command=self._clear_deck,
        ).pack(side="left", padx=Theme.scaled_val(5))

        ttk.Button(
            self.header,
            text="Auto-Lands",
            bootstyle="info",
            command=self._apply_auto_lands,
        ).pack(side="left", padx=Theme.scaled_val(5))

        # Smart Basics Toolbar (Left Click = Add, Right Click = Remove)
        self.basics_frame = ttk.Frame(self.header, style="Card.TFrame")
        self.basics_frame.pack(side="left", padx=Theme.scaled_val((15, 2)))

        self.basic_buttons = {}
        basics = [
            ("W", "Plains", "light"),
            ("U", "Island", "info"),
            ("B", "Swamp", "dark"),
            ("R", "Mountain", "danger"),
            ("G", "Forest", "success"),
        ]
        for sym, name, style in basics:
            btn = ttk.Button(
                self.basics_frame, text=f"{sym}: 0", bootstyle=style, width=5, padding=Theme.scaled_val(5)
            )

            # Standard Add (Left Click)
            btn.bind("<ButtonRelease-1>", lambda e, n=name: self._add_specific_basic(n))

            # Standard Remove (Right Click or Middle Click)
            btn.bind("<Button-2>", lambda e, n=name: self._on_basic_remove(e, n))
            btn.bind("<Button-3>", lambda e, n=name: self._on_basic_remove(e, n))

            # Mac Control-Click Remove
            btn.bind(
                "<Control-Button-1>", lambda e, n=name: self._on_basic_remove(e, n)
            )
            btn.bind("<Control-ButtonRelease-1>", lambda e: "break")

            btn.pack(side="left")
            self.basic_buttons[name] = btn

        self.btn_copy = ttk.Button(
            self.header, text="Copy Deck", width=10, command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="right", padx=Theme.scaled_val(5))

        self.btn_sim = ttk.Button(
            self.header,
            text="Analyze",
            bootstyle="success",
            command=self._run_simulation,
        )
        self.btn_sim.pack(side="right", padx=Theme.scaled_val(15))

        # --- TABBED LAYOUT ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # 1. Builder Tab
        self.builder_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.builder_tab, text=" DECK BUILDER ")

        self.v_split = ttk.PanedWindow(self.builder_tab, orient=tkinter.VERTICAL)
        self.v_split.pack(fill="both", expand=True, padx=Theme.scaled_val(2), pady=Theme.scaled_val(2))

        self.deck_frame = ttk.Labelframe(
            self.v_split, text=" MAIN DECK (0) ", padding=Theme.scaled_val(2)
        )
        self.v_split.add(self.deck_frame, weight=3)
        self.deck_manager = DynamicTreeviewManager(
            self.deck_frame,
            view_id="custom_deck_main",
            configuration=self.configuration,
            on_update_callback=self._update_tables,
        )
        self.deck_manager.pack(fill="both", expand=True)

        self.sb_frame = ttk.Labelframe(self.v_split, text=" SIDEBOARD (0) ", padding=Theme.scaled_val(2))
        self.v_split.add(self.sb_frame, weight=2)
        self.sb_manager = DynamicTreeviewManager(
            self.sb_frame,
            view_id="custom_deck_sb",
            configuration=self.configuration,
            on_update_callback=self._update_tables,
        )
        self.sb_manager.pack(fill="both", expand=True)

        # 2. Stats Tab
        self.stats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text=" STATS & ANALYSIS ")
        self.stats_canvas = tkinter.Canvas(
            self.stats_tab, highlightthickness=0, bg=Theme.BG_PRIMARY
        )
        self.stats_scrollbar = AutoScrollbar(
            self.stats_tab, orient="vertical", command=self.stats_canvas.yview
        )
        self.stats_canvas.grid(row=0, column=0, sticky="nsew")
        self.stats_scrollbar.grid(row=0, column=1, sticky="ns")
        self.stats_tab.rowconfigure(0, weight=1)
        self.stats_tab.columnconfigure(0, weight=1)
        self.stats_canvas.configure(yscrollcommand=self.stats_scrollbar.set)
        self.stats_frame = ttk.Frame(self.stats_canvas, padding=Theme.scaled_val(15))
        self.stats_canvas_window = self.stats_canvas.create_window(
            (0, 0), window=self.stats_frame, anchor="nw"
        )

        self.stats_frame.bind(
            "<Configure>",
            lambda e: self.stats_canvas.configure(
                scrollregion=self.stats_canvas.bbox("all")
            ),
        )
        self.stats_canvas.bind(
            "<Configure>",
            lambda e: self.stats_canvas.itemconfig(
                self.stats_canvas_window, width=e.width
            ),
        )
        bind_scroll(self.stats_canvas, self.stats_canvas.yview_scroll)
        bind_scroll(self.stats_frame, self.stats_canvas.yview_scroll)

        # 3. Sim & Hand Tab
        self.hand_tab = ttk.Frame(self.notebook, padding=Theme.scaled_val(15))
        self.notebook.add(self.hand_tab, text=" SIMULATION & SAMPLE HAND ")
        self.hand_tab.columnconfigure(0, weight=3)
        self.hand_tab.columnconfigure(1, weight=5)
        self.hand_tab.rowconfigure(1, weight=1)

        hand_control_bar = ttk.Frame(self.hand_tab)
        hand_control_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=Theme.scaled_val((0, 15)))
        ttk.Button(
            hand_control_bar,
            text="Draw New Hand",
            command=self._draw_sample_hand,
            bootstyle="success-outline",
            width=16,
        ).pack(side="left", padx=Theme.scaled_val(5))

        self.btn_optimize = ttk.Button(
            hand_control_bar,
            text="🤖 Auto-Optimize Deck",
            command=self._auto_optimize_deck,
            bootstyle="info",
        )
        self.btn_optimize.pack(side="left", padx=Theme.scaled_val(10))

        self.hand_canvas_frame = ttk.Frame(self.hand_tab)
        self.hand_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=Theme.scaled_val((0, 15)))
        self.hand_canvas_frame.rowconfigure(0, weight=1)
        self.hand_canvas_frame.columnconfigure(0, weight=1)

        self.hand_canvas = tkinter.Canvas(
            self.hand_canvas_frame, highlightthickness=0, bg=Theme.BG_PRIMARY
        )
        self.hand_scrollbar = AutoScrollbar(
            self.hand_canvas_frame, orient="vertical", command=self.hand_canvas.yview
        )
        self.hand_canvas.grid(row=0, column=0, sticky="nsew")
        self.hand_scrollbar.grid(row=0, column=1, sticky="ns")
        self.hand_canvas.configure(yscrollcommand=self.hand_scrollbar.set)

        self.hand_container = ttk.Frame(self.hand_canvas)
        self.hand_canvas_window = self.hand_canvas.create_window(
            (0, 0), window=self.hand_container, anchor="n"
        )
        self.hand_container.bind(
            "<Configure>",
            lambda e: self.hand_canvas.configure(
                scrollregion=self.hand_canvas.bbox("all")
            ),
        )
        self.hand_canvas.bind(
            "<Configure>",
            lambda e: self.hand_canvas.itemconfig(
                self.hand_canvas_window, width=e.width
            ),
        )
        bind_scroll(self.hand_canvas, self.hand_canvas.yview_scroll)
        bind_scroll(self.hand_container, self.hand_canvas.yview_scroll)

        self.sim_outer_frame = ttk.Labelframe(
            self.hand_tab, text=" MONTE CARLO SIMULATION (10,000 Games) ", padding=Theme.scaled_val(5)
        )
        self.sim_outer_frame.grid(row=1, column=1, sticky="nsew")
        self.sim_canvas = tkinter.Canvas(
            self.sim_outer_frame, highlightthickness=0, bg=Theme.BG_PRIMARY
        )
        self.sim_scrollbar = AutoScrollbar(
            self.sim_outer_frame, orient="vertical", command=self.sim_canvas.yview
        )
        self.sim_canvas.grid(row=0, column=0, sticky="nsew")
        self.sim_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sim_outer_frame.rowconfigure(0, weight=1)
        self.sim_outer_frame.columnconfigure(0, weight=1)

        self.sim_canvas.configure(yscrollcommand=self.sim_scrollbar.set)
        self.sim_frame = ttk.Frame(self.sim_canvas, padding=Theme.scaled_val(15))
        self.sim_canvas_window = self.sim_canvas.create_window(
            (0, 0), window=self.sim_frame, anchor="nw"
        )

        # Attach the dynamic label wrapper to the canvas resize event
        def _on_sim_canvas_resize(event):
            self.sim_canvas.itemconfig(self.sim_canvas_window, width=event.width)
            wrap_w = max(Theme.scaled_val(200), event.width - Theme.scaled_val(40))
            for child in self.sim_frame.winfo_children():
                if getattr(child, "is_dynamic_wrap", False):
                    child.configure(wraplength=wrap_w)
            self.sim_canvas.configure(scrollregion=self.sim_canvas.bbox("all"))

        self.sim_frame.bind(
            "<Configure>",
            lambda e: self.sim_canvas.configure(
                scrollregion=self.sim_canvas.bbox("all")
            ),
        )
        self.sim_canvas.bind("<Configure>", _on_sim_canvas_resize)

        bind_scroll(self.sim_canvas, self.sim_canvas.yview_scroll)
        bind_scroll(self.sim_frame, self.sim_canvas.yview_scroll)

        self.sim_label = ttk.Label(
            self.sim_frame,
            text="Generate a deck to run simulations.",
            font=Theme.scaled_font(11),
        )
        self.sim_label.is_dynamic_wrap = True
        self.sim_label.pack(pady=Theme.scaled_val(20))

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        if "SIMULATION" in self.notebook.tab(self.notebook.select(), "text"):
            self._draw_sample_hand()

    # --- SIMULATION AND OPTIMIZATION TASKS ---
    def _run_simulation(self):
        """Entry point for clicking the 'Analyze' button in the toolbar."""
        self.notebook.select(self.hand_tab)
        self.sim_executor.submit(self._run_monte_carlo_task, self.deck_list)

    def _run_monte_carlo_task(self, deck_list):
        """Executes a Monte Carlo simulation in the background."""
        self.after(
            0,
            lambda: self._show_sim_loading("Running 10,000 Monte Carlo Simulations..."),
        )
        try:
            stats = self._simulate_deck(deck_list, iterations=10000)
            self.after(0, lambda: self._show_sim_results(stats))
        except Exception as e:
            self.after(0, lambda err=str(e): self._show_sim_error(err))

    def _auto_optimize_deck(self):
        """Entry point for the AI Auto-Optimize button."""
        self.sim_executor.submit(self._run_auto_optimize_task)

    def _run_auto_optimize_task(self):
        """Background task that brute-forces deck permutations to find the mathematically optimal build."""
        self.after(
            0,
            lambda: self._show_sim_loading(
                "AI Auto-Optimizing: Simulating thousands of deck permutations..."
            ),
        )
        try:
            base_deck = list(self.deck_list)
            base_sb = list(self.sb_list)

            total_cards = sum(c.get("count", 1) for c in base_deck)
            if total_cards != 40:
                raise Exception(
                    f"Base deck must be exactly 40 cards to optimize (currently {total_cards})."
                )

            spells = [c for c in base_deck if "Land" not in c.get("types", [])]
            lands = [c for c in base_deck if "Land" in c.get("types", [])]
            sb_spells = [c for c in base_sb if "Land" not in c.get("types", [])]

            deck_colors = get_strict_colors(spells)
            archetype_key = (
                "".join(sorted(deck_colors[:2])) if deck_colors else "All Decks"
            )
            if not archetype_key:
                archetype_key = "All Decks"

            def get_wr(c):
                return float(
                    c.get("deck_colors", {}).get(archetype_key, {}).get("gihwr")
                    or c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )

            spells.sort(key=get_wr)
            sb_spells.sort(key=get_wr, reverse=True)

            worst_spell = spells[0] if spells else None
            best_sb_spell = sb_spells[0] if sb_spells else None

            highest_cmc_spell = (
                max(spells, key=lambda c: get_functional_cmc(c)) if spells else None
            )
            cheap_sb_spells = [c for c in sb_spells if get_functional_cmc(c) <= 2]
            best_cheap_sb = cheap_sb_spells[0] if cheap_sb_spells else None

            basic_lands = [
                c
                for c in lands
                if "Basic" in c.get("types", [])
                or c.get("name") in constants.BASIC_LANDS
            ]
            cuttable_land = basic_lands[0] if basic_lands else None

            permutations = []
            permutations.append(("Base Deck", base_deck, base_sb))

            def swap_cards(deck, sb, out_card, in_card):
                new_deck = []
                new_sb = list(sb)
                removed = False

                for c in deck:
                    if not removed and c["name"] == out_card["name"]:
                        if c.get("count", 1) > 1:
                            new_c = dict(c)
                            new_c["count"] -= 1
                            new_deck.append(new_c)
                        removed = True
                    else:
                        new_deck.append(c)

                if removed and in_card:
                    added = False
                    for c in new_deck:
                        if c["name"] == in_card["name"]:
                            new_c = dict(c)
                            new_c["count"] += 1
                            new_deck = [
                                new_c if x["name"] == in_card["name"] else x
                                for x in new_deck
                            ]
                            added = True
                            break
                    if not added:
                        in_c = dict(in_card)
                        in_c["count"] = 1
                        new_deck.append(in_c)

                    sb_removed = False
                    final_sb = []
                    for c in new_sb:
                        if not sb_removed and c["name"] == in_card["name"]:
                            if c.get("count", 1) > 1:
                                new_c = dict(c)
                                new_c["count"] -= 1
                                final_sb.append(new_c)
                            sb_removed = True
                        else:
                            final_sb.append(c)
                    new_sb = final_sb

                    sb_added = False
                    for c in new_sb:
                        if c["name"] == out_card["name"]:
                            new_c = dict(c)
                            new_c["count"] += 1
                            new_sb = [
                                new_c if x["name"] == out_card["name"] else x
                                for x in new_sb
                            ]
                            sb_added = True
                            break
                    if not sb_added:
                        out_c = dict(out_card)
                        out_c["count"] = 1
                        new_sb.append(out_c)

                return new_deck, new_sb

            if (
                highest_cmc_spell
                and best_cheap_sb
                and highest_cmc_spell["name"] != best_cheap_sb["name"]
            ):
                d, s = swap_cards(base_deck, base_sb, highest_cmc_spell, best_cheap_sb)
                permutations.append(
                    (
                        f"Curve Lower (-{highest_cmc_spell['name']}, +{best_cheap_sb['name']})",
                        d,
                        s,
                    )
                )

            if (
                worst_spell
                and best_sb_spell
                and worst_spell["name"] != best_sb_spell["name"]
            ):
                d, s = swap_cards(base_deck, base_sb, worst_spell, best_sb_spell)
                permutations.append(
                    (
                        f"Power Up (-{worst_spell['name']}, +{best_sb_spell['name']})",
                        d,
                        s,
                    )
                )

            if worst_spell and cuttable_land:
                d, s = swap_cards(base_deck, base_sb, worst_spell, cuttable_land)
                permutations.append((f"Play 18 Lands (-{worst_spell['name']})", d, s))

            if cuttable_land and best_sb_spell:
                d, s = swap_cards(base_deck, base_sb, cuttable_land, best_sb_spell)
                permutations.append((f"Play 16 Lands (+{best_sb_spell['name']})", d, s))

            best_score = -9999
            best_perm = None

            for desc, p_deck, p_sb in permutations:
                stats = self._simulate_deck(p_deck, iterations=3000)
                if not stats:
                    continue
                score = (
                    stats["cast_t2"]
                    + stats["cast_t3"]
                    + stats["cast_t4"]
                    + (stats["curve_out"] * 2)
                    - stats["mulligans"]
                    - stats["screw_t3"]
                    - stats["color_screw_t3"]
                )
                if score > best_score:
                    best_score = score
                    best_perm = (desc, p_deck, p_sb)

            if best_perm:
                desc, final_deck, final_sb = best_perm
                final_stats = self._simulate_deck(final_deck, iterations=10000)

                def finalize():
                    self.deck_list = final_deck
                    self.sb_list = final_sb

                    def card_sort_key(x):
                        return (
                            x.get(constants.DATA_FIELD_CMC, 0),
                            x.get(constants.DATA_FIELD_NAME, ""),
                        )

                    self.deck_list.sort(key=card_sort_key)
                    self.sb_list.sort(key=card_sort_key)

                    self._update_tables()
                    self._show_sim_results(
                        final_stats, optimization_note=f"Optimized: {desc}"
                    )
                    self._render_deck_stats()
                    self._draw_sample_hand()
                    self._update_basics_toolbar()

                self.after(0, finalize)
            else:
                raise Exception("Failed to optimize.")
        except Exception as e:
            self.after(0, lambda err=str(e): self._show_sim_error(err))

    def _show_sim_loading(self, msg="Running 10,000 Monte Carlo Simulations..."):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()

        lbl = ttk.Label(
            self.sim_frame,
            text=msg,
            font=Theme.scaled_font(10, "italic"),
            bootstyle="secondary",
            justify="center",
            wraplength=Theme.scaled_val(300),
        )
        lbl.is_dynamic_wrap = True
        lbl.pack(pady=Theme.scaled_val(20))

        progress = ttk.Progressbar(self.sim_frame, mode="indeterminate")
        progress.pack(fill="x", padx=Theme.scaled_val(20))
        progress.start(15)

    def _show_sim_error(self, error):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()
        lbl = ttk.Label(
            self.sim_frame,
            text=f"Simulation Error:\n{error}",
            bootstyle="danger",
            wraplength=Theme.scaled_val(300),
        )
        lbl.is_dynamic_wrap = True
        lbl.pack(pady=Theme.scaled_val(20))

    # --- BASIC LAND HANDLERS ---
    def _on_basic_remove(self, event, color_name):
        self._remove_specific_basic(color_name)
        return "break"

    # --- DRAG AND DROP & SELECTION LOGIC ---
    def _get_card_from_row(self, tree, row_id, is_sb):
        manager = self.sb_manager if is_sb else self.deck_manager
        item_vals = tree.item(row_id)["values"]
        if not item_vals:
            return None

        try:
            name_idx = manager.active_fields.index("name")
            card_name = str(item_vals[name_idx])
        except ValueError:
            return None

        source_list = self.sb_list if is_sb else self.deck_list
        for c in source_list:
            if c["name"] == card_name:
                return c
        return None

    def _bind_dnd(self, tree, is_sb=False):
        tree.bind(
            "<ButtonPress-1>", lambda e: self._on_drag_start(e, tree, is_sb), add="+"
        )
        tree.bind("<B1-Motion>", lambda e: self._on_drag_motion(e, tree), add="+")
        tree.bind(
            "<ButtonRelease-1>",
            lambda e: self._on_drag_release(e, tree, is_sb),
            add="+",
        )
        tree.bind("<Button-3>", lambda e: self._on_right_click(e, tree, is_sb), add="+")
        tree.bind(
            "<Control-Button-1>",
            lambda e: self._on_right_click(e, tree, is_sb),
            add="+",
        )

    def _on_drag_start(self, event, tree, is_sb):
        self._drag_data = None
        row_id = tree.identify_row(event.y)
        if not row_id:
            return

        tree.selection_set(row_id)
        card = self._get_card_from_row(tree, row_id, is_sb)
        if not card:
            return

        self._drag_data = {
            "name": card["name"],
            "x": event.x_root,
            "y": event.y_root,
            "is_sb": is_sb,
        }

    def _on_drag_motion(self, event, tree):
        if getattr(self, "_drag_data", None):
            tree.configure(cursor="hand2")

    def _inside_widget(self, event, widget):
        rx, ry = widget.winfo_rootx(), widget.winfo_rooty()
        rw, rh = widget.winfo_width(), widget.winfo_height()
        return rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh

    def _on_drag_release(self, event, tree, is_sb):
        tree.configure(cursor="")
        if not getattr(self, "_drag_data", None):
            return

        dx, dy = abs(event.x_root - self._drag_data["x"]), abs(
            event.y_root - self._drag_data["y"]
        )
        card_name = self._drag_data["name"]

        if dx < 5 and dy < 5:
            if is_sb:
                self._move_card(self.sb_list, self.deck_list, card_name)
            else:
                self._move_card(self.deck_list, self.sb_list, card_name)
        else:
            if is_sb and self._inside_widget(event, self.deck_frame):
                self._move_card(self.sb_list, self.deck_list, card_name)
            elif not is_sb and self._inside_widget(event, self.sb_frame):
                self._move_card(self.deck_list, self.sb_list, card_name)

        self._drag_data = None

    def _on_right_click(self, event, tree, is_sb):
        if tree.identify_region(event.x, event.y) == "heading":
            return
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        tree.selection_set(row_id)

        card = self._get_card_from_row(tree, row_id, is_sb)
        if card:
            CardToolTip.create(
                tree,
                card,
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
            )

    # --- MOVE LOGIC ---
    def _move_card(self, source_list, dest_list, card_name):
        src_card = next((c for c in source_list if c["name"] == card_name), None)
        if not src_card:
            return

        src_card["count"] -= 1
        if src_card["count"] <= 0:
            source_list.remove(src_card)

        dest_card = next((c for c in dest_list if c["name"] == card_name), None)
        if dest_card:
            dest_card["count"] += 1
        else:
            new_c = dict(src_card)
            new_c["count"] = 1
            dest_list.append(new_c)

        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

    def _clear_deck(self):
        for card in list(self.deck_list):
            if card["name"] in constants.BASIC_LANDS:
                self.deck_list.remove(card)
            else:
                count = card["count"]
                sb_card = next(
                    (c for c in self.sb_list if c["name"] == card["name"]), None
                )
                if sb_card:
                    sb_card["count"] += count
                else:
                    new_c = dict(card)
                    self.sb_list.append(new_c)
                self.deck_list.remove(card)
        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

    # --- MANA BASE LOGIC ---
    def _apply_auto_lands(self):
        """Uses Frank Karsten logic to rebuild the basic mana base for the current spells."""
        self.deck_list = [
            c for c in self.deck_list if c["name"] not in constants.BASIC_LANDS
        ]

        spells = [c for c in self.deck_list if "Land" not in c.get("types", [])]
        non_basic_lands = [c for c in self.deck_list if "Land" in c.get("types", [])]

        if not spells:
            self._update_tables()
            self._update_basics_toolbar()
            return

        deck_colors = get_strict_colors(spells)
        if not deck_colors:
            deck_colors = ["W", "U", "B", "R", "G"]

        total_lands_needed = 40 - len(spells)
        if len(non_basic_lands) > total_lands_needed:
            non_basic_lands.sort(
                key=lambda x: float(
                    x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                ),
                reverse=True,
            )
            non_basic_lands = non_basic_lands[:total_lands_needed]

        needed_basics = max(0, total_lands_needed - len(non_basic_lands))

        basics_to_add = calculate_dynamic_mana_base(
            spells, non_basic_lands, deck_colors, forced_count=needed_basics
        )

        for basic in basics_to_add:
            dest_card = next(
                (c for c in self.deck_list if c["name"] == basic["name"]), None
            )
            if dest_card:
                dest_card["count"] += 1
            else:
                self.deck_list.append(dict(basic))

        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

    def _add_specific_basic(self, color_name):
        color_map = {
            "Plains": "W",
            "Island": "U",
            "Swamp": "B",
            "Mountain": "R",
            "Forest": "G",
        }
        color = color_map.get(color_name, "")

        dest_card = next((c for c in self.deck_list if c["name"] == color_name), None)
        if dest_card:
            dest_card["count"] += 1
        else:
            card = {
                "name": color_name,
                "cmc": 0,
                "types": ["Land", "Basic"],
                "colors": [color] if color else [],
                "count": 1,
            }
            self.deck_list.append(card)

        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

    def _remove_specific_basic(self, color_name):
        dest_card = next((c for c in self.deck_list if c["name"] == color_name), None)
        if not dest_card:
            return

        dest_card["count"] -= 1
        if dest_card["count"] <= 0:
            self.deck_list.remove(dest_card)

        self._update_tables()
        self._render_deck_stats()
        self._update_basics_toolbar()

    def _update_basics_toolbar(self):
        """Updates the numeric counts on the basic land buttons."""
        counts = {
            name: 0
            for _, name, _ in [
                ("W", "Plains", ""),
                ("U", "Island", ""),
                ("B", "Swamp", ""),
                ("R", "Mountain", ""),
                ("G", "Forest", ""),
            ]
        }

        for c in self.deck_list:
            if c["name"] in counts:
                counts[c["name"]] += c.get("count", 1)

        symbol_map = {
            "Plains": "W",
            "Island": "U",
            "Swamp": "B",
            "Mountain": "R",
            "Forest": "G",
        }

        for name, btn in self.basic_buttons.items():
            count = counts[name]
            sym = symbol_map[name]
            btn.configure(text=f"{sym}: {count}")

    # --- RENDERING ---
    def _update_tables(self):
        total_main = sum(c.get("count", 1) for c in self.deck_list)
        total_sb = sum(c.get("count", 1) for c in self.sb_list)

        # Smart Deck Size Warning
        if total_main == 40:
            self.deck_frame.configure(text=f" MAIN DECK ({total_main}) ✔ ")
        elif total_main > 40:
            self.deck_frame.configure(
                text=f" MAIN DECK ({total_main}) ⚠️ CUT {total_main - 40} "
            )
        else:
            self.deck_frame.configure(
                text=f" MAIN DECK ({total_main}) ⚠️ ADD {40 - total_main} "
            )

        self.sb_frame.configure(text=f" SIDEBOARD ({total_sb}) ")

        metrics = self.draft.retrieve_set_metrics()
        tier_data = self.draft.retrieve_tier_data()
        active_filter = self.configuration.settings.deck_filter

        if active_filter == constants.FILTER_OPTION_AUTO:
            active_filter = "All Decks"

        from src.card_logic import format_win_rate, row_color_tag

        def populate_tree(manager, source_list, is_sb):
            tree = manager.tree
            self._bind_dnd(tree, is_sb)

            for item in tree.get_children():
                tree.delete(item)

            # Sort source data strictly by CMC/Name before inserting to guarantee default logical order
            # (Unless the user has explicitly clicked a column header to sort differently, which reapply_sort catches)
            sorted_source = sorted(
                source_list,
                key=lambda x: (
                    x.get(constants.DATA_FIELD_CMC, 0),
                    x.get(constants.DATA_FIELD_NAME, ""),
                ),
            )

            for idx, card in enumerate(sorted_source):
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
                    elif field == "mana_cost":
                        row_values.append(card.get("mana_cost", ""))
                    elif field == "colors":
                        row_values.append("".join(card.get("colors", [])))
                    elif field == "tags":
                        raw_tags = card.get("tags", [])
                        if raw_tags:
                            icons = [
                                constants.TAG_VISUALS.get(t, t).split(" ")[0]
                                for t in raw_tags
                            ]
                            row_values.append(" ".join(icons))
                        else:
                            row_values.append("-")
                    elif "TIER" in field:
                        if tier_data and field in tier_data:
                            tier_obj = tier_data[field]
                            card_name = card.get("name", "")
                            if card_name in tier_obj.ratings:
                                row_values.append(tier_obj.ratings[card_name].rating)
                            else:
                                row_values.append("NA")
                        else:
                            row_values.append("NA")
                    else:
                        stats = card.get("deck_colors", {}).get(
                            active_filter,
                            card.get("deck_colors", {}).get("All Decks", {}),
                        )
                        val = stats.get(field, 0.0)
                        row_values.append(
                            format_win_rate(
                                val,
                                active_filter,
                                field,
                                metrics,
                                self.configuration.settings.result_format,
                            )
                        )

                tag = "bw_odd" if idx % 2 == 0 else "bw_even"
                if self.configuration.settings.card_colors_enabled:
                    tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

                tree.insert("", "end", iid=str(idx), values=row_values, tags=(tag,))

            if hasattr(tree, "reapply_sort"):
                tree.reapply_sort()

        populate_tree(self.deck_manager, self.deck_list, False)
        populate_tree(self.sb_manager, self.sb_list, True)

    def _render_deck_stats(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        if not self.deck_list:
            return

        total_cards = sum(c.get("count", 1) for c in self.deck_list)
        creatures = sum(
            c.get("count", 1)
            for c in self.deck_list
            if "Creature" in c.get("types", [])
        )
        lands = sum(
            c.get("count", 1) for c in self.deck_list if "Land" in c.get("types", [])
        )
        spells = total_cards - creatures - lands

        pips = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        curve = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        tags = {}
        cmc_sum = 0
        non_lands = 0

        supertypes = {
            "Creature",
            "Instant",
            "Sorcery",
            "Enchantment",
            "Artifact",
            "Planeswalker",
            "Land",
            "Legendary",
            "Basic",
            "Snow",
            "World",
            "Tribal",
            "Kindred",
            "Ongoing",
        }
        subtypes = {}

        for c in self.deck_list:
            count = c.get("count", 1)
            if "Land" not in c.get("types", []):
                non_lands += count
                cmc = get_functional_cmc(c)
                cmc_sum += cmc * count
                idx = min(cmc, 6)
                if idx == 0:
                    idx = 1
                curve[idx] += count

                cost = c.get("mana_cost", "")
                for symbol in "WUBRG":
                    pips[symbol] += cost.count(symbol) * count

                for t in c.get("tags", []):
                    tags[t] = tags.get(t, 0) + count

            if "Creature" in c.get("types", []):
                for t in c.get("types", []):
                    if t not in supertypes:
                        subtypes[t] = subtypes.get(t, 0) + count

        avg_cmc = cmc_sum / non_lands if non_lands else 0
        top_tribes = sorted(subtypes.items(), key=lambda x: x[1], reverse=True)[:5]

        comp_frame = ttk.Frame(self.stats_frame)
        comp_frame.pack(fill="x", pady=Theme.scaled_val(5))
        ttk.Label(
            comp_frame,
            text="DECK COMPOSITION",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        ttk.Label(
            comp_frame,
            text=f"Total Cards: {total_cards}  |  Creatures: {creatures}  |  Non-Creatures: {spells}  |  Lands: {lands}",
        ).pack(anchor="w", pady=Theme.scaled_val(2))

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=Theme.scaled_val(8))

        color_frame = ttk.Frame(self.stats_frame)
        color_frame.pack(fill="x", pady=Theme.scaled_val(5))
        ttk.Label(
            color_frame,
            text="COLOR REQUIREMENTS (PIPS)",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")

        pip_str = []
        for symbol, name, color in [
            ("W", "White", Theme.TEXT_MUTED),
            ("U", "Blue", Theme.ACCENT),
            ("B", "Black", "#8b8b93"),
            ("R", "Red", Theme.ERROR),
            ("G", "Green", Theme.SUCCESS),
        ]:
            if pips[symbol] > 0:
                pip_str.append(f"{name} ({symbol}): {pips[symbol]}")
        ttk.Label(
            color_frame, text="  |  ".join(pip_str) if pip_str else "Colorless"
        ).pack(anchor="w", pady=Theme.scaled_val(2))

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=Theme.scaled_val(8))

        tags_frame = ttk.Frame(self.stats_frame)
        tags_frame.pack(fill="x", pady=Theme.scaled_val(5))
        ttk.Label(
            tags_frame,
            text="ROLES & SYNERGIES",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")

        if tags:
            tag_str = []
            for tag_key, cnt in sorted(
                tags.items(), key=lambda item: item[1], reverse=True
            ):
                ui_name = constants.TAG_VISUALS.get(tag_key, tag_key.capitalize())
                tag_str.append(f"{ui_name}: {cnt}")

            for i in range(0, len(tag_str), 4):
                ttk.Label(tags_frame, text="    ".join(tag_str[i : i + 4])).pack(
                    anchor="w", pady=Theme.scaled_val(2)
                )
        else:
            ttk.Label(
                tags_frame,
                text="No Scryfall tags found for this set.",
                bootstyle="secondary",
            ).pack(anchor="w", pady=Theme.scaled_val(2))

        if top_tribes:
            tribe_str = "  |  ".join([f"{t}: {c}" for t, c in top_tribes])
            ttk.Label(
                tags_frame, text=f"Top Tribes: {tribe_str}", font=Theme.scaled_font(9)
            ).pack(anchor="w", pady=Theme.scaled_val(4))

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=Theme.scaled_val(8))

        curve_frame = ttk.Frame(self.stats_frame)
        curve_frame.pack(fill="x", pady=Theme.scaled_val(5))
        ttk.Label(
            curve_frame,
            text=f"MANA CURVE (Avg CMC: {avg_cmc:.2f})",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        for i in range(1, 7):
            lbl = f"{i} CMC: " if i < 6 else "6+ CMC:"
            cnt = curve[i]
            ttk.Label(
                curve_frame,
                text=f"{lbl:<8} {'█'*cnt} ({cnt})",
                font=Theme.scaled_font(10, family=constants.FONT_MONO_SPACE),
            ).pack(anchor="w", pady=Theme.scaled_val(1))

    def _simulate_deck(self, deck_list, iterations=10000):
        flat_deck = []
        for c in deck_list:
            is_land = "Land" in c.get("types", [])
            colors_produced = set()
            if is_land:
                colors_produced.update(c.get("colors", []))
                text = str(c.get("text", "")).lower()
                if "any color" in text or "fixing_ramp" in c.get("tags", []):
                    colors_produced.update(["W", "U", "B", "R", "G"])

            pips = {}
            if not is_land:
                cost = c.get("mana_cost", "")
                matches = re.findall(r"\{(.*?)\}", cost)
                for pip in matches:
                    opts = [opt for opt in pip.split("/") if opt in "WUBRG"]
                    if opts:
                        p = opts[0]
                        pips[p] = pips.get(p, 0) + 1

            for _ in range(int(c.get("count", 1))):
                flat_deck.append(
                    {
                        "is_land": is_land,
                        "is_removal": "removal" in c.get("tags", []),
                        "colors_produced": colors_produced,
                        "cmc": get_functional_cmc(c),
                        "pips": pips,
                    }
                )

        if len(flat_deck) < 40:
            return None

        stats = {
            "mulligans": 0,
            "screw_t3": 0,
            "screw_t4": 0,
            "flood_t5": 0,
            "cast_t2": 0,
            "cast_t3": 0,
            "cast_t4": 0,
            "curve_out": 0,
            "removal_t4": 0,
            "color_screw_t3": 0,
            "avg_hand_size": 0,
        }

        for _ in range(iterations):
            random.shuffle(flat_deck)

            # Pro-Level London Mulligan Heuristic
            mull_count = 0
            hand = flat_deck[0:7]
            lands = sum(1 for c in hand if c["is_land"])

            if lands < 2 or lands > 5:
                mull_count = 1
                hand = flat_deck[7:14]
                lands = sum(1 for c in hand if c["is_land"])
                if lands < 2 or lands > 4:
                    mull_count = 2
                    hand = flat_deck[14:21]

            if mull_count > 0:
                stats["mulligans"] += 1

            kept_size = 7 - mull_count
            stats["avg_hand_size"] += kept_size
            start_idx = mull_count * 7

            current_7 = flat_deck[start_idx : start_idx + 7]
            if kept_size < 7:
                current_7.sort(key=lambda x: x["cmc"])

            kept_hand = current_7[:kept_size]
            deck_rest = flat_deck[start_idx + 7 :]

            game_state = kept_hand + deck_rest

            t2_state = game_state[: kept_size + 1]
            t3_state = game_state[: kept_size + 2]
            t4_state = game_state[: kept_size + 3]
            t5_state = game_state[: kept_size + 4]

            lands_t3 = [c for c in t3_state if c["is_land"]]
            if len(lands_t3) < 3:
                stats["screw_t3"] += 1

            lands_t4 = [c for c in t4_state if c["is_land"]]
            if len(lands_t4) < 4:
                stats["screw_t4"] += 1

            lands_t5 = sum(1 for c in t5_state if c["is_land"])
            if lands_t5 >= 6:
                stats["flood_t5"] += 1

            if any(c["is_removal"] for c in t4_state):
                stats["removal_t4"] += 1

            def can_cast(state, target_cmc):
                available_lands = [c for c in state if c["is_land"]]
                if len(available_lands) < target_cmc:
                    return False

                spells = [
                    c for c in state if not c["is_land"] and c["cmc"] == target_cmc
                ]
                if not spells:
                    return False

                color_sources = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
                for l in available_lands:
                    for c in l["colors_produced"]:
                        color_sources[c] += 1

                for s in spells:
                    castable = True
                    for pip, count in s["pips"].items():
                        if color_sources[pip] < count:
                            castable = False
                            break
                    if castable:
                        return True
                return False

            c2 = can_cast(t2_state, 2)
            c3 = can_cast(t3_state, 3)
            c4 = can_cast(t4_state, 4)

            if c2:
                stats["cast_t2"] += 1
            if c3:
                stats["cast_t3"] += 1
            if c4:
                stats["cast_t4"] += 1
            if c2 and c3 and c4:
                stats["curve_out"] += 1

            if len(lands_t3) >= 3:
                color_sources = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
                for l in lands_t3:
                    for c in l["colors_produced"]:
                        color_sources[c] += 1

                t3_spells = [c for c in t3_state if not c["is_land"] and c["cmc"] <= 3]
                any_color_screw = False
                for s in t3_spells:
                    for pip, count in s["pips"].items():
                        if color_sources.get(pip, 0) < count:
                            any_color_screw = True
                            break
                if any_color_screw:
                    stats["color_screw_t3"] += 1

        stats["avg_hand_size"] = stats["avg_hand_size"] / iterations
        for k in list(stats.keys()):
            if k != "avg_hand_size":
                stats[k] = (stats[k] / iterations) * 100.0

        return stats

    def _show_sim_results(self, stats, optimization_note=None):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()
        if not stats:
            lbl = ttk.Label(
                self.sim_frame,
                text="Deck must have exactly 40 cards to run simulations.",
                bootstyle="warning",
            )
            lbl.is_dynamic_wrap = True
            lbl.pack(pady=Theme.scaled_val(20))
            return

        def _add_stat(label, value, thresholds, reverse=False, is_percent=True):
            frame = ttk.Frame(self.sim_frame)
            frame.pack(fill="x", pady=Theme.scaled_val(2))
            ttk.Label(frame, text=label, font=Theme.scaled_font(10, "bold")).pack(
                side="left"
            )
            g, f = thresholds

            if not reverse:
                icon, color = (
                    ("🟢 Great", "success")
                    if value >= g
                    else ("🟡 Fair", "warning") if value >= f else ("🔴 Poor", "danger")
                )
            else:
                icon, color = (
                    ("🟢 Great", "success")
                    if value <= g
                    else ("🟡 Fair", "warning") if value <= f else ("🔴 Poor", "danger")
                )

            val_str = f"{value:.1f}%" if is_percent else f"{value:.2f}"
            rf = ttk.Frame(frame)
            rf.pack(side="right")
            ttk.Label(
                rf,
                text=val_str,
                font=Theme.scaled_font(10, "bold"),
                width=6,
                anchor="e",
            ).pack(side="left", padx=Theme.scaled_val((0, 6)))
            ttk.Label(
                rf, text=icon, font=(Theme.FONT_FAMILY, 10, "bold"), bootstyle=color
            ).pack(side="left")

        ttk.Label(
            self.sim_frame,
            text="CONSISTENCY METRICS",
            bootstyle="primary",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))
        _add_stat("T2 Play (2-Drop):", stats["cast_t2"], (65, 50))
        _add_stat("T3 Play (3-Drop):", stats["cast_t3"], (65, 50))
        _add_stat("T4 Play (4-Drop):", stats["cast_t4"], (55, 40))
        _add_stat("Perfect Curve (T2-T4):", stats["curve_out"], (25, 15))
        _add_stat("Removal by Turn 4:", stats["removal_t4"], (60, 45))
        ttk.Separator(self.sim_frame).pack(fill="x", pady=Theme.scaled_val(8))

        ttk.Label(
            self.sim_frame,
            text="RISK FACTORS",
            bootstyle="primary",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))
        _add_stat("Mulligan Rate:", stats["mulligans"], (15, 25), reverse=True)
        _add_stat(
            "Avg. Hand Size:",
            stats["avg_hand_size"],
            (6.8, 6.5),
            reverse=False,
            is_percent=False,
        )
        _add_stat("Missed 3rd Land Drop:", stats["screw_t3"], (15, 25), reverse=True)
        _add_stat("Missed 4th Land Drop:", stats["screw_t4"], (25, 35), reverse=True)
        _add_stat(
            "Color Screwed (T3):", stats["color_screw_t3"], (10, 20), reverse=True
        )
        _add_stat("Mana Flooded (T5):", stats["flood_t5"], (20, 30), reverse=True)

        ttk.Separator(self.sim_frame).pack(fill="x", pady=Theme.scaled_val(8))

        ttk.Label(
            self.sim_frame,
            text="ADVISOR SUMMARY",
            bootstyle="info",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        if optimization_note:
            lbl_opt = ttk.Label(
                self.sim_frame,
                text=optimization_note,
                font=(Theme.FONT_FAMILY, 9, "bold"),
                bootstyle="success",
            )
            lbl_opt.is_dynamic_wrap = True
            lbl_opt.pack(anchor="w", pady=2)

        total_cards = sum(c.get("count", 1) for c in self.deck_list)
        lands = sum(
            c.get("count", 1) for c in self.deck_list if "Land" in c.get("types", [])
        )
        creatures = sum(
            c.get("count", 1)
            for c in self.deck_list
            if "Creature" in c.get("types", [])
        )

        advice = []
        if total_cards != 40:
            advice.append(
                f"⚠️ Deck Size: You are playing {total_cards} cards. Pro players strictly play exactly 40 cards to maximize drawing their best spells."
            )

        if lands < 16:
            advice.append(
                f"⚠️ Land Count: {lands} lands is dangerously low unless you are playing an extreme aggro deck with a curve ending at 3."
            )
        elif lands > 18:
            advice.append(
                f"⚠️ Land Count: {lands} lands increases flood risk. 17 is standard for most Limited decks."
            )

        if creatures < 13:
            advice.append(
                f"⚠️ Creatures: Only {creatures} creatures. Limited decks typically require 14-17 to maintain board presence and apply pressure."
            )

        if stats["cast_t2"] < 50:
            advice.append(
                "⚠️ Early Game: Turn 2 play rate is very low. You desperately need more 2-drops to survive aggro and stabilize the board."
            )

        if stats["removal_t4"] < 40:
            advice.append(
                "⚠️ Interaction: You lack early removal. Consider prioritizing cheap interaction from your sideboard."
            )

        if stats["color_screw_t3"] > 15:
            advice.append(
                "⚠️ Mana Base: High color screw risk. Review your colored pips vs sources. You may need more dual lands or to cut a greedy splash."
            )

        if stats["screw_t3"] > 20:
            advice.append(
                "⚠️ Mana Screw: Frequently missing 3rd land drops. Consider running 17 or 18 lands, or adding card draw/cantrips."
            )

        if stats["flood_t5"] > 25:
            advice.append(
                "⚠️ Mana Flood: High flood risk. Consider cutting a land or adding more 'mana sinks' (cards with activated abilities)."
            )

        # Swap Suggestion
        spells_list = [c for c in self.deck_list if "Land" not in c.get("types", [])]
        sb_spells = [c for c in self.sb_list if "Land" not in c.get("types", [])]
        if spells_list and sb_spells:
            deck_colors = (
                get_strict_colors(spells_list)
                if spells_list
                else ["W", "U", "B", "R", "G"]
            )

            def get_wr(c):
                return float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )

            valid_main = [c for c in spells_list if get_wr(c) > 0]
            valid_sb = [
                c
                for c in sb_spells
                if get_wr(c) > 0 and is_castable(c, deck_colors, strict=True)
            ]

            if valid_main and valid_sb:
                worst_main = min(valid_main, key=get_wr)
                best_sb = max(valid_sb, key=get_wr)

                w_wr = get_wr(worst_main)
                b_wr = get_wr(best_sb)

                if b_wr > w_wr + 1.5:
                    advice.append(
                        f"💡 Swap Suggestion: Cut [{worst_main['name']}] ({w_wr:.1f}%) for [{best_sb['name']}] ({b_wr:.1f}%)."
                    )

        if not advice:
            advice.append(
                "✅ Your deck composition, curve, and mana base look statistically solid!"
            )

        for tip in advice:
            lbl_tip = ttk.Label(self.sim_frame, text=tip, font=Theme.scaled_font(9))
            lbl_tip.is_dynamic_wrap = True
            lbl_tip.pack(anchor="w", pady=Theme.scaled_val(2))

        self.after(
            50,
            lambda: self.sim_canvas.configure(scrollregion=self.sim_canvas.bbox("all")),
        )

    def _clear_sample_hand(self):
        for widget in self.hand_container.winfo_children():
            widget.destroy()
        self.hand_images.clear()
        self.hand_frames = []

    def _draw_sample_hand(self):
        self._clear_sample_hand()
        if not self.deck_list:
            return

        flat_deck = [c for c in self.deck_list for _ in range(int(c.get("count", 1)))]
        if len(flat_deck) < 7:
            return

        hand = random.sample(flat_deck, 7)
        hand.sort(
            key=lambda c: (
                1 if "Land" in c.get("types", []) else 2,
                int(c.get("cmc", 0)),
                c.get("name", ""),
            )
        )

        img_w, img_h, offset_y = Theme.scaled_val(180), Theme.scaled_val(252), Theme.scaled_val(32)
        stack_container = ttk.Frame(
            self.hand_container, width=img_w, height=img_h + (6 * offset_y) + Theme.scaled_val(20)
        )
        stack_container.pack(expand=True, pady=Theme.scaled_val(15))
        stack_container.pack_propagate(False)

        for i, card in enumerate(hand):
            frame = ttk.Frame(
                stack_container, width=img_w, height=img_h, bootstyle="secondary"
            )
            frame.pack_propagate(False)
            frame.place(x=0, y=i * offset_y)
            self.hand_frames.append(frame)

            name_lbl = ttk.Label(
                frame,
                text=card.get("name", "Unknown"),
                font=Theme.scaled_font(9),
                wraplength=img_w - Theme.scaled_val(10),
                justify="center",
                bootstyle="inverse-secondary",
            )
            name_lbl.pack(expand=True)
            name_lbl.bind("<Enter>", lambda e, f=frame: f.lift())
            name_lbl.bind(
                "<Leave>",
                lambda e: [f.lift() for f in self.hand_frames if f.winfo_exists()],
            )

            self.image_executor.submit(
                self._fetch_and_show_image, card, frame, img_w, img_h
            )

    def _fetch_and_show_image(self, card, container_frame, width, height):
        img_url = card.get("image", [None])[0]
        if not img_url and card.get("name") in constants.BASIC_LANDS:
            img_url = f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(card.get('name'))}&format=image"
        if not img_url:
            return

        if img_url.startswith("/static"):
            img_url = f"https://www.17lands.com{img_url}"
        elif "scryfall" in img_url:
            img_url = img_url.replace("/small/", "/large/").replace(
                "/normal/", "/large/"
            )

        cache_dir = os.path.join(constants.TEMP_FOLDER, "Images")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(
            cache_dir, hashlib.md5(img_url.encode("utf-8")).hexdigest() + ".jpg"
        )

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
            img.thumbnail((width, height), Image.Resampling.LANCZOS)

            def apply_img():
                if container_frame.winfo_exists():
                    for w in container_frame.winfo_children():
                        w.destroy()
                    tk_img = ImageTk.PhotoImage(img)
                    self.hand_images.append(tk_img)
                    lbl = ttk.Label(container_frame, image=tk_img, cursor="hand2")
                    lbl.pack(fill="both", expand=True)
                    lbl.bind(
                        "<Button-1>",
                        lambda e: CardToolTip.create(
                            container_frame,
                            card,
                            self.configuration.features.images_enabled,
                            constants.UI_SIZE_DICT.get(
                                self.configuration.settings.ui_size, 1.0
                            ),
                        ),
                    )
                    lbl.bind("<Enter>", lambda e: container_frame.lift())
                    lbl.bind(
                        "<Leave>",
                        lambda e: [
                            f.lift() for f in self.hand_frames if f.winfo_exists()
                        ],
                    )

            self.after(0, apply_img)
        except:
            pass

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.deck_list, self.sb_list))
        self.btn_copy.configure(text="Copied! ✔", bootstyle="success")
        self.after(
            2000, lambda: self.btn_copy.configure(text="Copy Deck", bootstyle="primary")
        )
