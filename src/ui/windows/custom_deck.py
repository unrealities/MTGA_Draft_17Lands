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
                self.basics_frame,
                text=f"{sym}: 0",
                bootstyle=style,
                width=5,
                padding=Theme.scaled_val(5),
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
        self.v_split.pack(
            fill="both", expand=True, padx=Theme.scaled_val(2), pady=Theme.scaled_val(2)
        )

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

        self.sb_frame = ttk.Labelframe(
            self.v_split, text=" SIDEBOARD (0) ", padding=Theme.scaled_val(2)
        )
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
        hand_control_bar.grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=Theme.scaled_val((0, 15))
        )
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
        self.hand_canvas_frame.grid(
            row=1, column=0, sticky="nsew", padx=Theme.scaled_val((0, 15))
        )
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
            self.hand_tab,
            text=" MONTE CARLO SIMULATION (10,000 Games) ",
            padding=Theme.scaled_val(5),
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

    def _clear_table(self):
        table = getattr(self, "table", None)
        if table:
            for item in table.get_children():
                table.delete(item)

        sb_table = getattr(self, "sb_table", None)
        if sb_table:
            for item in sb_table.get_children():
                sb_table.delete(item)

        stats_frame = getattr(self, "stats_frame", None)
        if stats_frame and stats_frame.winfo_exists():
            for widget in stats_frame.winfo_children():
                widget.destroy()

        sim_frame = getattr(self, "sim_frame", None)
        if sim_frame and sim_frame.winfo_exists():
            for widget in sim_frame.winfo_children():
                widget.destroy()

        if hasattr(self, "_clear_sample_hand"):
            self._clear_sample_hand()

        self.current_deck_list = []
        self.current_sb_list = []

        notebook = getattr(self, "notebook", None)
        deck_frame = getattr(self, "deck_frame", None)
        if notebook and deck_frame:
            try:
                notebook.tab(deck_frame, text=" MAIN DECK (0) ")
            except Exception:
                pass

    def _on_tab_changed(self, event):
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        if "SIMULATION & SAMPLE HAND" in current_tab:
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
            from src.card_logic import simulate_deck

            stats = simulate_deck(deck_list, iterations=10000)
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

            from src.card_logic import optimize_deck, get_strict_colors

            spells = [c for c in base_deck if "Land" not in c.get("types", [])]
            deck_colors = get_strict_colors(spells)
            archetype_key = (
                "".join(sorted(deck_colors[:2])) if deck_colors else "All Decks"
            )

            final_deck, final_sb, final_stats, opt_note = optimize_deck(
                base_deck, base_sb, archetype_key, deck_colors
            )

            if final_deck:

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
                    self._show_sim_results(final_stats, optimization_note=opt_note)
                    self._render_deck_stats()
                    self._draw_sample_hand()
                    self._update_basics_toolbar()

                self.after(0, finalize)
            else:
                raise Exception("Failed to optimize.")
        except Exception as e:

            def show_err():
                self._show_sim_error(str(e))
                import tkinter.messagebox

                tkinter.messagebox.showwarning(
                    "Optimization Failed", str(e), parent=self
                )

            self.after(0, show_err)

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

    def _show_sim_results(self, stats, optimization_note=None):
        sim_frame = getattr(self, "sim_frame", None)
        if not sim_frame or not sim_frame.winfo_exists():
            return

        for widget in sim_frame.winfo_children():
            widget.destroy()

        if not stats:
            ttk.Label(
                sim_frame,
                text="Deck must have 40 cards to analyze.",
                bootstyle="warning",
            ).pack(pady=Theme.scaled_val(20))
            return

        def _add_stat(label, value, thresholds, reverse=False, is_percent=True):
            frame = ttk.Frame(sim_frame)
            frame.pack(fill="x", pady=Theme.scaled_val(2))
            ttk.Label(frame, text=label, font=Theme.scaled_font(10, "bold")).pack(
                side="left"
            )

            good_val, fair_val = thresholds

            if not reverse:
                if value >= good_val:
                    icon, color = "🟢 Great", "success"
                elif value >= fair_val:
                    icon, color = "🟡 Fair", "warning"
                else:
                    icon, color = "🔴 Poor", "danger"
            else:
                if value <= good_val:
                    icon, color = "🟢 Great", "success"
                elif value <= fair_val:
                    icon, color = "🟡 Fair", "warning"
                else:
                    icon, color = "🔴 Poor", "danger"

            val_str = f"{value:.1f}%" if is_percent else f"{value:.2f}"

            right_frame = ttk.Frame(frame)
            right_frame.pack(side="right")

            ttk.Label(
                right_frame,
                text=val_str,
                font=Theme.scaled_font(10, "bold"),
                width=6,
                anchor="e",
            ).pack(side="left", padx=Theme.scaled_val((0, 6)))

            ttk.Label(
                right_frame,
                text=icon,
                font=Theme.scaled_font(10, "bold"),
                bootstyle=color,
                anchor="w",
            ).pack(side="left")

        ttk.Label(
            sim_frame,
            text="CONSISTENCY METRICS",
            bootstyle="primary",
            font=Theme.scaled_font(10, "bold"),
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))

        _add_stat("T2 Play (2-Drop):", stats["cast_t2"], (65, 50))
        _add_stat("T3 Play (3-Drop):", stats["cast_t3"], (65, 50))
        _add_stat("T4 Play (4-Drop):", stats["cast_t4"], (55, 40))
        _add_stat("Perfect Curve (T2-T4):", stats["curve_out"], (25, 15))
        _add_stat("Removal by Turn 4:", stats["removal_t4"], (60, 45))

        ttk.Separator(sim_frame).pack(fill="x", pady=Theme.scaled_val(8))

        ttk.Label(
            sim_frame,
            text="RISK FACTORS",
            bootstyle="primary",
            font=Theme.scaled_font(10, "bold"),
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))

        _add_stat("Mulligan Rate:", stats["mulligans"], (15, 25), reverse=True)
        _add_stat(
            "Avg. Hand Size:", stats["avg_hand_size"], (6.8, 6.5), is_percent=False
        )
        _add_stat("Missed 3rd Land Drop:", stats["screw_t3"], (15, 25), reverse=True)
        _add_stat("Missed 4th Land Drop:", stats["screw_t4"], (25, 35), reverse=True)
        _add_stat("Color Screwed (T3):", stats["color_screw_t3"], (6, 12), reverse=True)
        _add_stat("Mana Flooded (T5):", stats["flood_t5"], (20, 30), reverse=True)

        ttk.Separator(sim_frame).pack(fill="x", pady=Theme.scaled_val(8))

        # --- ADVISOR SUMMARY LOGIC ---
        ttk.Label(
            sim_frame,
            text="ADVISOR SUMMARY",
            bootstyle="info",
            font=Theme.scaled_font(10, "bold"),
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))

        if optimization_note:
            lbl_opt = ttk.Label(
                sim_frame,
                text=optimization_note,
                font=Theme.scaled_font(9, "bold"),
                bootstyle="success",
            )
            lbl_opt.is_dynamic_wrap = True
            lbl_opt.pack(anchor="w", pady=Theme.scaled_val(2))

        advice = []
        if stats["cast_t2"] < 50:
            advice.append("• Add more 2-drops to improve early board presence.")

        from src import constants

        non_basics = [
            c
            for c in self.deck_list
            if "Land" in c.get("types", [])
            and "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]
        colorless_lands = [c for c in non_basics if not c.get("colors")]

        if stats["color_screw_t3"] > 10.0:
            if colorless_lands:
                advice.append(
                    f"• Color screw risk is elevated. Consider cutting a colorless utility land (like {colorless_lands[0].get('name', '')}) for a basic land."
                )
            else:
                advice.append(
                    "• High color screw risk. Consider cutting a splash card or adding more fixing."
                )

        # Ensure static advice does not contradict the AI Optimizer's recent actions
        is_18_lands = optimization_note and "18 Lands" in optimization_note
        is_16_lands = optimization_note and "16 Lands" in optimization_note

        if stats["screw_t3"] > 22.0 and not is_16_lands:
            advice.append(
                "• Frequently missing land drops. Consider running an extra land."
            )
        if stats["flood_t5"] > 28.0 and not is_18_lands:
            advice.append(
                "• High flood risk. Consider cutting a land or adding mana sinks."
            )
        if stats["removal_t4"] < 45:
            advice.append("• Low early interaction. Prioritize cheap removal.")

        deck_colors = set()
        for c in self.deck_list:
            if "Land" not in c.get("types", []):
                for col in c.get("colors", []):
                    deck_colors.add(col)

        if len(deck_colors) >= 3:
            advice.append(
                "⚠️ Mana Base: You are playing 3+ colors. This inherently increases your risk of color screw. Ensure you have at least 3-4 strong fixing sources."
            )

        # Swap Suggestions
        if not optimization_note:
            if stats["cast_t2"] < 50 or stats["flood_t5"] > 25:
                expensive_cards = [
                    c
                    for c in self.deck_list
                    if int(c.get("cmc", 0)) >= 5 and "Land" not in c.get("types", [])
                ]
                if expensive_cards:
                    deck_spells = [
                        c for c in self.deck_list if "Land" not in c.get("types", [])
                    ]
                    deck_colors_strict = (
                        get_strict_colors(deck_spells)
                        if deck_spells
                        else ["W", "U", "B", "R", "G"]
                    )

                    worst_expensive = min(
                        expensive_cards,
                        key=lambda x: float(
                            x.get("deck_colors", {})
                            .get("All Decks", {})
                            .get("gihwr", 0)
                        ),
                    )
                    cheap_sb = [
                        c
                        for c in self.sb_list
                        if int(c.get("cmc", 0)) <= 3
                        and "Land" not in c.get("types", [])
                        and "Creature" in c.get("types", [])
                        and is_castable(c, deck_colors_strict, strict=True)
                    ]
                    if cheap_sb:
                        best_cheap = max(
                            cheap_sb,
                            key=lambda x: float(
                                x.get("deck_colors", {})
                                .get("All Decks", {})
                                .get("gihwr", 0)
                            ),
                        )
                        advice.append(
                            f"• Swap: Cut [{worst_expensive['name']}] for [{best_cheap['name']}] to lower curve."
                        )

        for tip in advice:
            lbl_tip = ttk.Label(sim_frame, text=tip, font=Theme.scaled_font(9))
            lbl_tip.is_dynamic_wrap = True
            lbl_tip.pack(anchor="w", pady=Theme.scaled_val(2))

            # Re-trigger a configure event on the parent container to format newly added labels instantly
            sim_frame.event_generate("<Configure>")

        sim_canvas = getattr(self, "sim_canvas", None)
        if sim_canvas and sim_canvas.winfo_exists():
            self.after(
                50,
                lambda: sim_canvas.configure(scrollregion=sim_canvas.bbox("all")),
            )

    def _clear_sample_hand(self):
        hand_container = getattr(self, "hand_container", None)
        if hand_container and hand_container.winfo_exists():
            for widget in hand_container.winfo_children():
                widget.destroy()

        if hasattr(self, "hand_images"):
            self.hand_images.clear()
        if hasattr(self, "hand_frames"):
            self.hand_frames = []

    def _draw_sample_hand(self):
        self._clear_sample_hand()

        hand_container = getattr(self, "hand_container", None)
        if not hand_container or not hand_container.winfo_exists():
            return

        if not self.deck_list:
            ttk.Label(
                hand_container,
                text="Generate a deck first.",
                font=Theme.scaled_font(11),
            ).pack(pady=Theme.scaled_val(20))
            return

        flat_deck = []
        for c in self.deck_list:
            flat_deck.extend([c] * int(c.get("count", 1)))

        if len(flat_deck) < 7:
            ttk.Label(
                hand_container,
                text="Deck has fewer than 7 cards.",
                font=Theme.scaled_font(11),
            ).pack(pady=Theme.scaled_val(20))
            return

        # Draw 7 random cards
        hand = random.sample(flat_deck, 7)

        # Sort the hand: Basic Lands (WUBRG) -> Non-Basic Lands -> Spells (by CMC)
        def hand_sort_key(c):
            types = c.get("types", [])
            name = c.get("name", "")
            cmc = int(c.get("cmc", 0))
            is_land = "Land" in types
            is_basic = "Basic" in types or name in constants.BASIC_LANDS

            if is_land:
                if is_basic:
                    color_order = 5
                    if "Plains" in name:
                        color_order = 0
                    elif "Island" in name:
                        color_order = 1
                    elif "Swamp" in name:
                        color_order = 2
                    elif "Mountain" in name:
                        color_order = 3
                    elif "Forest" in name:
                        color_order = 4
                    return (0, color_order, name)
                return (1, 0, name)
            return (2, cmc, name)

        hand.sort(key=hand_sort_key)

        scale = Theme.current_scale
        # Reduced size for scrollability and sleeker look
        img_w = Theme.scaled_val(180)
        img_h = Theme.scaled_val(252)
        offset_y = Theme.scaled_val(32)

        # Calculate exact height to allow scrolling perfectly
        stack_h = img_h + (6 * offset_y) + 20

        stack_container = ttk.Frame(hand_container, width=img_w, height=stack_h)
        stack_container.pack(expand=True, pady=Theme.scaled_val(15))
        stack_container.pack_propagate(False)

        def restore_z_order(event=None):
            if hasattr(self, "hand_frames"):
                for f in self.hand_frames:
                    if f.winfo_exists():
                        f.lift()

        for i, card in enumerate(hand):
            frame = ttk.Frame(
                stack_container, width=img_w, height=img_h, bootstyle="secondary"
            )
            frame.pack_propagate(False)
            frame.place(x=0, y=i * offset_y)

            self.hand_frames.append(frame)

            # Temporary text label while image downloads
            name_lbl = ttk.Label(
                frame,
                text=card.get("name", "Unknown"),
                font=Theme.scaled_font(9),
                wraplength=img_w - Theme.scaled_val(10),
                justify="center",
                bootstyle="inverse-secondary",
            )
            name_lbl.pack(expand=True)

            # Bindings for the temporary label
            name_lbl.bind("<Enter>", lambda e, f=frame: f.lift())
            name_lbl.bind("<Leave>", restore_z_order)

            # Dispatch to background thread
            self.image_executor.submit(
                self._fetch_and_show_image, card, frame, img_w, img_h
            )

    def _fetch_and_show_image(self, card, container_frame, width, height):
        img_url = ""
        urls = card.get("image", [])
        if urls:
            img_url = urls[0]
        elif card.get("name") in constants.BASIC_LANDS:
            # Fallback to Scryfall API for generated Basic Lands
            img_url = f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(card.get('name'))}&format=image"

        if not img_url:
            return

        if img_url.startswith("/static"):
            img_url = f"https://www.17lands.com{img_url}"
        elif "scryfall" in img_url and "format=image" not in img_url:
            img_url = img_url.replace("/small/", "/large/").replace(
                "/normal/", "/large/"
            )

        cache_dir = os.path.join(constants.TEMP_FOLDER, "Images")
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = hashlib.md5(img_url.encode("utf-8")).hexdigest() + ".jpg"
        cache_path = os.path.join(cache_dir, safe_name)

        try:
            # Load from cache or download
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

                    scale = constants.UI_SIZE_DICT.get(
                        self.configuration.settings.ui_size, 1.0
                    )
                    lbl.bind(
                        "<Button-1>",
                        lambda e, c=card: CardToolTip.create(
                            container_frame,
                            c,
                            self.configuration.features.images_enabled,
                            scale,
                        ),
                    )

                    def restore_z(event=None):
                        if hasattr(self, "hand_frames"):
                            for f in self.hand_frames:
                                if f.winfo_exists():
                                    f.lift()

                    lbl.bind("<Enter>", lambda e: container_frame.lift())
                    lbl.bind("<Leave>", restore_z)

            # Safely sync to main UI thread
            self.after(0, apply_img)

        except Exception:
            pass

    # --- BASIC LAND HANDLERS ---
    def _on_basic_remove(self, event, color_name):
        self._remove_specific_basic(color_name)
        return "break"

    # --- DRAG AND DROP & SELECTION LOGIC ---
    def _get_card_from_row(self, tree, row_id, is_sb):
        item = tree.item(row_id)
        card_name = item.get("text")

        if not card_name:
            manager = self.sb_manager if is_sb else self.deck_manager
            item_vals = item["values"]
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
        if getattr(tree, "_dnd_bound", False):
            return
        tree._dnd_bound = True

        tree.bind(
            "<ButtonPress-1>", lambda e: self._on_drag_start(e, tree, is_sb), add="+"
        )
        tree.bind("<B1-Motion>", lambda e: self._on_drag_motion(e, tree), add="+")
        tree.bind(
            "<ButtonRelease-1>",
            lambda e: self._on_drag_release(e, tree, is_sb),
            add="+",
        )
        tree.bind(
            "<Double-Button-1>",
            lambda e: self._on_double_click(e, tree, is_sb),
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

        dx, dy = (
            abs(event.x_root - self._drag_data["x"]),
            abs(event.y_root - self._drag_data["y"]),
        )
        card_name = self._drag_data["name"]

        if dx >= 5 or dy >= 5:
            if is_sb and self._inside_widget(event, self.deck_frame):
                self._move_card(self.sb_list, self.deck_list, card_name)
            elif not is_sb and self._inside_widget(event, self.sb_frame):
                self._move_card(self.deck_list, self.sb_list, card_name)

        self._drag_data = None

    def _on_double_click(self, event, tree, is_sb):
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        card = self._get_card_from_row(tree, row_id, is_sb)
        if not card:
            return

        if is_sb:
            self._move_card(self.sb_list, self.deck_list, card["name"])
        else:
            self._move_card(self.deck_list, self.sb_list, card["name"])
        return "break"

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
        """Dispatches the brute-force mana optimization to a background thread."""
        self.notebook.select(self.hand_tab)
        self.sim_executor.submit(self._run_auto_lands_task)

    def _run_auto_lands_task(self):
        self.after(
            0,
            lambda: self._show_sim_loading(
                "Simulating perfect mana base permutations..."
            ),
        )

        try:
            from src.advisor.mana_base import brute_force_mana_base, get_strict_colors

            # Extract non-basics
            spells = [c for c in self.deck_list if "Land" not in c.get("types", [])]
            non_basic_lands = [
                c
                for c in self.deck_list
                if "Land" in c.get("types", [])
                and "Basic" not in c.get("types", [])
                and c.get("name") not in constants.BASIC_LANDS
            ]

            if not spells:
                self.after(
                    0, lambda: self._show_sim_error("Add spells to the deck first.")
                )
                return

            deck_colors = get_strict_colors(spells)
            if not deck_colors:
                deck_colors = ["W", "U", "B", "R", "G"]

            total_lands_needed = 40 - len(spells)

            # Trim excess non-basics if needed
            if len(non_basic_lands) > total_lands_needed:
                non_basic_lands.sort(
                    key=lambda x: float(
                        x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                    ),
                    reverse=True,
                )
                non_basic_lands = non_basic_lands[:total_lands_needed]

            needed_basics = max(0, total_lands_needed - len(non_basic_lands))

            # Trigger the AI brute force
            basics_to_add = brute_force_mana_base(
                spells, non_basic_lands, deck_colors, forced_count=needed_basics
            )

            def _finalize():
                # Wipe old basics
                self.deck_list = [
                    c for c in self.deck_list if c["name"] not in constants.BASIC_LANDS
                ]

                # Append the optimal ones
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
                self._run_monte_carlo_task(self.deck_list)

            self.after(0, _finalize)

        except Exception as e:
            self.after(0, lambda err=str(e): self._show_sim_error(err))

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
                            raw_name = card.get("name", "")
                            if raw_name in tier_obj.ratings:
                                row_values.append(tier_obj.ratings[raw_name].rating)
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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(
            fill="x", pady=Theme.scaled_val(8)
        )

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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(
            fill="x", pady=Theme.scaled_val(8)
        )

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
            for tag_key, count in sorted(
                tags.items(), key=lambda item: item[1], reverse=True
            ):
                ui_name = constants.TAG_VISUALS.get(tag_key, tag_key.capitalize())
                tag_str.append(f"{ui_name}: {count}")

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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(
            fill="x", pady=Theme.scaled_val(8)
        )

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
                text=f"{lbl:<8} {'█' * cnt} ({cnt})",
                font=Theme.scaled_font(10, family=constants.FONT_MONO_SPACE),
            ).pack(anchor="w", pady=Theme.scaled_val(1))

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.deck_list, self.sb_list))
        self.btn_copy.configure(text="Copied! ✔", bootstyle="success")
        self.after(
            2000, lambda: self.btn_copy.configure(text="Copy Deck", bootstyle="primary")
        )
