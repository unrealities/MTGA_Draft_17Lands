"""
src/ui/windows/suggest_deck.py
Professional Deck Builder Panel.
Uses the Advisor Engine to suggest optimal archetypes from the pool.
Displays Main Deck and Sideboard in separate notebook tabs.
Includes a 10,000 game Monte Carlo Simulation for elite pro-level analysis.
Features a Ground-Breaking AI Deck Optimizer that simulates permutations.
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
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk

from src import constants
from src.card_logic import copy_deck, get_strict_colors, is_castable
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip, AutoScrollbar
from src.utils import bind_scroll


class SuggestDeckPanel(ttk.Frame):
    def __init__(
        self,
        parent,
        draft_manager,
        configuration,
        on_export_custom=None,
        app_context=None,
    ):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration
        self.on_export_custom = on_export_custom
        self.app_context = app_context

        self.suggestions: Dict[str, Any] = {}
        self.current_deck_list: List[Dict] = []
        self.current_sb_list: List[Dict] = []
        self.current_archetype_key: str = ""

        self.is_building = False

        self.image_executor = ThreadPoolExecutor(max_workers=4)
        self.sim_executor = ThreadPoolExecutor(max_workers=1)
        self.hand_images = []
        self.hand_frames = []

        self._build_ui()

    @property
    def table(self) -> ttk.Treeview:
        """Dynamically retrieves the current Main Deck tree widget from the manager."""
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    @property
    def sb_table(self) -> ttk.Treeview:
        """Dynamically retrieves the current Sideboard tree widget from the manager."""
        return self.sb_manager.tree if hasattr(self, "sb_manager") else None

    def refresh(self):
        """Triggers the archetype building algorithm and refreshes the view."""
        self._calculate_suggestions()

    def _build_ui(self):
        self.header = ttk.Frame(self, style="Card.TFrame", padding=5)
        self.header.pack(fill="x", pady=(0, 0))

        # --- Row 1: Archetype Controls ---
        self.arch_frame = ttk.Frame(self.header, style="Card.TFrame")
        self.arch_frame.pack(fill="x")

        self.lbl_archetype = ttk.Label(
            self.arch_frame,
            text="AI SUGGESTION:",
            font=(Theme.FONT_FAMILY, 8, "bold"),
            bootstyle="primary",
        )
        self.lbl_archetype.pack(side="left", padx=5)
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

        self.var_archetype = tkinter.StringVar()
        self.om_archetype = ttk.OptionMenu(
            self.arch_frame,
            self.var_archetype,
            "",
            style="TMenubutton",
            command=self._on_deck_selection_change,
        )
        self.om_archetype.pack(side="left", padx=10, fill="x", expand=True)

        self.btn_copy = ttk.Button(
            self.arch_frame, text="Copy Deck", width=12, command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="right", padx=5)

        if self.on_export_custom:
            self.btn_export_builder = ttk.Button(
                self.arch_frame,
                text="Export to Custom Builder",
                bootstyle="info-outline",
                command=lambda: self.on_export_custom(
                    self.current_deck_list, self.current_sb_list
                ),
            )
            self.btn_export_builder.pack(side="right", padx=5)

        self.notes_frame = ttk.Frame(self, style="Card.TFrame", padding=(10, 0, 5, 5))
        self.notes_frame.pack(fill="x", pady=(0, 5))
        self.lbl_deck_notes = ttk.Label(
            self.notes_frame,
            text="",
            font=(Theme.FONT_FAMILY, 9),
            bootstyle="info",
        )
        self.lbl_deck_notes.pack(side="left", padx=5)

        # Replaced PanedWindow with a Notebook to give the tables maximum vertical space
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # Main Deck Tab
        self.deck_frame = ttk.Frame(self.notebook, padding=2)
        self.notebook.add(self.deck_frame, text=" MAIN DECK (0) ")

        cols = ["name", "count", "cmc", "types", "colors", "gihwr"]
        self.table_manager = DynamicTreeviewManager(
            self.deck_frame,
            view_id="deck_builder",
            configuration=self.configuration,
            on_update_callback=self.refresh,
            static_columns=cols,
        )
        self.table_manager.pack(fill="both", expand=True)
        self.table.bind(
            "<<TreeviewSelect>>", lambda e: self._on_selection(e, is_sb=False)
        )

        # Sideboard Tab
        self.sb_frame = ttk.Frame(self.notebook, padding=2)
        self.notebook.add(self.sb_frame, text=" SIDEBOARD ")

        self.sb_manager = DynamicTreeviewManager(
            self.sb_frame,
            view_id="deck_builder",
            configuration=self.configuration,
            on_update_callback=self.refresh,
            static_columns=cols,
        )
        self.sb_manager.pack(fill="both", expand=True)
        self.sb_table.bind(
            "<<TreeviewSelect>>", lambda e: self._on_selection(e, is_sb=True)
        )

        # Stats Tab
        self.stats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text=" STATS & ANALYSIS ")

        self.stats_tab.rowconfigure(0, weight=1)
        self.stats_tab.columnconfigure(0, weight=1)

        self.stats_canvas = tkinter.Canvas(
            self.stats_tab, highlightthickness=0, bg=Theme.BG_PRIMARY
        )
        self.stats_scrollbar = AutoScrollbar(
            self.stats_tab, orient="vertical", command=self.stats_canvas.yview
        )

        self.stats_canvas.grid(row=0, column=0, sticky="nsew")
        self.stats_scrollbar.grid(row=0, column=1, sticky="ns")
        self.stats_canvas.configure(yscrollcommand=self.stats_scrollbar.set)

        self.stats_frame = ttk.Frame(self.stats_canvas, padding=15)
        self.stats_canvas_window = self.stats_canvas.create_window(
            (0, 0), window=self.stats_frame, anchor="nw"
        )

        def _on_content_resize(event):
            self.stats_canvas.configure(scrollregion=self.stats_canvas.bbox("all"))

        def _on_canvas_resize(event):
            self.stats_canvas.itemconfig(self.stats_canvas_window, width=event.width)

        self.stats_frame.bind("<Configure>", _on_content_resize)
        self.stats_canvas.bind("<Configure>", _on_canvas_resize)

        bind_scroll(self.stats_canvas, self.stats_canvas.yview_scroll)
        bind_scroll(self.stats_frame, self.stats_canvas.yview_scroll)
        self.stats_frame.bind(
            "<Enter>",
            lambda e: bind_scroll(self.stats_frame, self.stats_canvas.yview_scroll),
        )

        # --- SIMULATION & SAMPLE HAND TAB ---
        self.hand_tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.hand_tab, text=" SIMULATION & SAMPLE HAND ")

        # Two Columns: 0 = Hand Canvas, 1 = Monte Carlo
        self.hand_tab.columnconfigure(0, weight=3)
        self.hand_tab.columnconfigure(1, weight=5)
        self.hand_tab.rowconfigure(1, weight=1)

        hand_control_bar = ttk.Frame(self.hand_tab)
        hand_control_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        self.btn_draw = ttk.Button(
            hand_control_bar,
            text="Draw New Hand",
            command=self._draw_sample_hand,
            bootstyle="success-outline",
            width=16,
        )
        self.btn_draw.pack(side="left", padx=5)

        # Left Column: Scrollable Canvas for Sample Hand
        self.hand_canvas_frame = ttk.Frame(self.hand_tab)
        self.hand_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
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

        def _on_hand_content_resize(event):
            self.hand_canvas.configure(scrollregion=self.hand_canvas.bbox("all"))

        def _on_hand_canvas_resize(event):
            self.hand_canvas.itemconfig(self.hand_canvas_window, width=event.width)

        self.hand_container.bind("<Configure>", _on_hand_content_resize)
        self.hand_canvas.bind("<Configure>", _on_hand_canvas_resize)

        bind_scroll(self.hand_canvas, self.hand_canvas.yview_scroll)
        bind_scroll(self.hand_container, self.hand_canvas.yview_scroll)
        self.hand_container.bind(
            "<Enter>",
            lambda e: bind_scroll(self.hand_container, self.hand_canvas.yview_scroll),
        )

        # Right Column: Scrollable Monte Carlo Simulation
        self.sim_outer_frame = ttk.Labelframe(
            self.hand_tab, text=" MONTE CARLO SIMULATION (10,000 Games) ", padding=5
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

        self.sim_frame = ttk.Frame(self.sim_canvas, padding=15)
        self.sim_canvas_window = self.sim_canvas.create_window(
            (0, 0), window=self.sim_frame, anchor="nw"
        )

        def _on_sim_frame_resize(event):
            self.sim_canvas.configure(scrollregion=self.sim_canvas.bbox("all"))

        def _on_sim_canvas_resize(event):
            self.sim_canvas.itemconfig(self.sim_canvas_window, width=event.width)
            # Guarantee wrapped labels fit without clipping
            wrap_w = max(200, event.width - 40)
            for child in self.sim_frame.winfo_children():
                if isinstance(child, ttk.Label) and getattr(
                    child, "is_dynamic_wrap", False
                ):
                    child.configure(wraplength=wrap_w)
            self.sim_canvas.configure(scrollregion=self.sim_canvas.bbox("all"))

        self.sim_frame.bind("<Configure>", _on_sim_frame_resize)
        self.sim_canvas.bind("<Configure>", _on_sim_canvas_resize)

        bind_scroll(self.sim_canvas, self.sim_canvas.yview_scroll)
        bind_scroll(self.sim_frame, self.sim_canvas.yview_scroll)
        self.sim_frame.bind(
            "<Enter>",
            lambda e: bind_scroll(self.sim_frame, self.sim_canvas.yview_scroll),
        )

        self.sim_label = ttk.Label(
            self.sim_frame,
            text="Generate a deck to analyze.",
            font=(Theme.FONT_FAMILY, 11),
        )
        self.sim_label.is_dynamic_wrap = True
        self.sim_label.pack(pady=20)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _clear_table(self):
        """Highly defensive UI clearing to prevent attribute errors during state transitions."""
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
            # Automatically draw a fresh hand when viewing the tab to ensure it's always responsive
            self._draw_sample_hand()

    def _run_monte_carlo_task(self, deck_list):
        self.after(0, lambda: self._show_sim_loading())
        try:
            from src.card_logic import simulate_deck

            stats = simulate_deck(deck_list, iterations=10000)
            self.after(0, lambda: self._show_sim_results(stats))
        except Exception as e:
            self.after(0, lambda e=e: self._show_sim_error(str(e)))

    def _show_sim_loading(self, msg="Running 10,000 Monte Carlo Simulations..."):
        sim_frame = getattr(self, "sim_frame", None)
        if not sim_frame or not sim_frame.winfo_exists():
            return

        for widget in sim_frame.winfo_children():
            widget.destroy()

        lbl = ttk.Label(
            sim_frame,
            text=msg,
            font=(Theme.FONT_FAMILY, 10, "italic"),
            bootstyle="secondary",
            justify="center",
        )
        lbl.is_dynamic_wrap = True
        lbl.pack(pady=20)

        progress = ttk.Progressbar(sim_frame, mode="indeterminate")
        progress.pack(fill="x", padx=20)
        progress.start(15)

    def _show_sim_error(self, error):
        sim_frame = getattr(self, "sim_frame", None)
        if not sim_frame or not sim_frame.winfo_exists():
            return

        for widget in sim_frame.winfo_children():
            widget.destroy()
        ttk.Label(
            sim_frame,
            text=f"Simulation Error:\n{error}",
            bootstyle="danger",
            wraplength=300,
        ).pack(pady=20)

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
            ).pack(pady=20)
            return

        def _add_stat(label, value, thresholds, reverse=False, is_percent=True):
            frame = ttk.Frame(sim_frame)
            frame.pack(fill="x", pady=2)
            ttk.Label(frame, text=label, font=(Theme.FONT_FAMILY, 10, "bold")).pack(
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
                font=(Theme.FONT_FAMILY, 10, "bold"),
                width=6,
                anchor="e",
            ).pack(side="left", padx=(0, 6))

            ttk.Label(
                right_frame,
                text=icon,
                font=(Theme.FONT_FAMILY, 10, "bold"),
                bootstyle=color,
                anchor="w",
            ).pack(side="left")

        ttk.Label(
            sim_frame,
            text="CONSISTENCY METRICS",
            bootstyle="primary",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        _add_stat("T2 Play (2-Drop):", stats["cast_t2"], (65, 50))
        _add_stat("T3 Play (3-Drop):", stats["cast_t3"], (65, 50))
        _add_stat("T4 Play (4-Drop):", stats["cast_t4"], (55, 40))
        _add_stat("Perfect Curve (T2-T4):", stats["curve_out"], (25, 15))
        _add_stat("Removal by Turn 4:", stats["removal_t4"], (60, 45))

        ttk.Separator(sim_frame).pack(fill="x", pady=8)

        ttk.Label(
            sim_frame,
            text="RISK FACTORS",
            bootstyle="primary",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        _add_stat("Mulligan Rate:", stats["mulligans"], (15, 25), reverse=True)
        _add_stat(
            "Avg. Hand Size:", stats["avg_hand_size"], (6.8, 6.5), is_percent=False
        )
        _add_stat("Missed 3rd Land Drop:", stats["screw_t3"], (15, 25), reverse=True)
        _add_stat("Missed 4th Land Drop:", stats["screw_t4"], (25, 35), reverse=True)
        _add_stat(
            "Color Screwed (T3):", stats["color_screw_t3"], (10, 20), reverse=True
        )
        _add_stat("Mana Flooded (T5):", stats["flood_t5"], (20, 30), reverse=True)

        ttk.Separator(sim_frame).pack(fill="x", pady=8)

        # --- ADVISOR SUMMARY LOGIC ---
        ttk.Label(
            sim_frame,
            text="ADVISOR SUMMARY",
            bootstyle="info",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        if optimization_note:
            lbl_opt = ttk.Label(
                sim_frame,
                text=optimization_note,
                font=(Theme.FONT_FAMILY, 9, "bold"),
                bootstyle="success",
            )
            lbl_opt.is_dynamic_wrap = True
            lbl_opt.pack(anchor="w", pady=2)

        advice = []
        if stats["cast_t2"] < 50:
            advice.append("• Add more 2-drops to improve early board presence.")

        from src import constants

        non_basics = [
            c
            for c in self.current_deck_list
            if "Land" in c.get("types", [])
            and "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]
        colorless_lands = [c for c in non_basics if not c.get("colors")]

        if stats["color_screw_t3"] > 16.0:
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

        # Swap Suggestions
        if not optimization_note:
            if stats["cast_t2"] < 50 or stats["flood_t5"] > 25:
                expensive_cards = [
                    c
                    for c in self.current_deck_list
                    if int(c.get("cmc", 0)) >= 5 and "Land" not in c.get("types", [])
                ]
                if expensive_cards:
                    deck_spells = [
                        c
                        for c in self.current_deck_list
                        if "Land" not in c.get("types", [])
                    ]
                    deck_colors = (
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
                        for c in self.current_sb_list
                        if int(c.get("cmc", 0)) <= 3
                        and "Land" not in c.get("types", [])
                        and "Creature" in c.get("types", [])
                        and is_castable(c, deck_colors, strict=True)
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
            lbl_tip = ttk.Label(sim_frame, text=tip, font=(Theme.FONT_FAMILY, 9))
            lbl_tip.is_dynamic_wrap = True
            lbl_tip.pack(anchor="w", pady=2)

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

        if not self.current_deck_list:
            ttk.Label(
                hand_container,
                text="Generate a deck first.",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(pady=20)
            return

        flat_deck = []
        for c in self.current_deck_list:
            flat_deck.extend([c] * int(c.get("count", 1)))

        if len(flat_deck) < 7:
            ttk.Label(
                hand_container,
                text="Deck has fewer than 7 cards.",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(pady=20)
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

        scale = constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0)
        # Reduced size for scrollability and sleeker look
        img_w = int(180 * scale)
        img_h = int(252 * scale)
        offset_y = int(32 * scale)

        # Calculate exact height to allow scrolling perfectly
        stack_h = img_h + (6 * offset_y) + 20

        stack_container = ttk.Frame(hand_container, width=img_w, height=stack_h)
        stack_container.pack(expand=True, pady=15)
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
                font=(Theme.FONT_FAMILY, 9),
                wraplength=img_w - 10,
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
                    lbl = ttk.Label(container_frame, image=tk_img)
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

                    lbl.configure(cursor="hand2")

            # Safely sync to main UI thread
            self.after(0, apply_img)

        except Exception as e:
            pass

    def _on_theme_change(self, event=None):
        stats_canvas = getattr(self, "stats_canvas", None)
        if stats_canvas and stats_canvas.winfo_exists():
            stats_canvas.configure(bg=Theme.BG_PRIMARY)

        hand_canvas = getattr(self, "hand_canvas", None)
        if hand_canvas and hand_canvas.winfo_exists():
            hand_canvas.configure(bg=Theme.BG_PRIMARY)

    def _calculate_suggestions(self):
        raw_pool = self.draft.retrieve_taken_cards()

        playable_cards = [
            c
            for c in (raw_pool or [])
            if "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]

        if not playable_cards or len(playable_cards) < 23:
            msg = "Not enough playable cards drafted yet (Need 23)."
            self._update_dropdown_options([msg])
            self.var_archetype.set(msg)
            if getattr(self, "app_context", None) and hasattr(
                self.app_context, "loading_overlay"
            ):
                self.app_context.loading_overlay.hide()
            return

        if self.is_building:
            return

        self.is_building = True
        self.var_archetype.set("Initializing AI Builder...")
        self._update_dropdown_options(["Initializing AI Builder..."])
        self._clear_table()
        self.suggestions = {}
        self.incremental_labels = []

        metrics = (
            self.orchestrator.scanner.retrieve_set_metrics()
            if hasattr(self, "orchestrator")
            else self.draft.retrieve_set_metrics()
        )
        _, event_type = (
            self.orchestrator.scanner.retrieve_current_limited_event()
            if hasattr(self, "orchestrator")
            else self.draft.retrieve_current_limited_event()
        )
        dataset_name = self.configuration.card_data.latest_dataset

        def _progress_cb(msg):
            if not self.winfo_exists():
                return
            if "status" in msg:
                if not self.suggestions:
                    self.after(0, lambda: self.var_archetype.set(msg["status"]))
                if getattr(self, "app_context", None) and hasattr(
                    self.app_context, "loading_overlay"
                ):
                    self.after(
                        0,
                        lambda: self.app_context.loading_overlay.update_status(
                            msg["status"]
                        ),
                    )
            elif "variant_label" in msg:
                lbl = msg["variant_label"]
                vd = msg["variant_data"]

                def _update_ui():
                    self.suggestions[lbl] = vd
                    self.incremental_labels.append(lbl)
                    self._update_dropdown_options(self.incremental_labels)

                    if len(self.incremental_labels) == 1:
                        self._on_deck_selection_change(lbl)

                self.after(0, _update_ui)

        def _worker():
            try:
                from src.card_logic import suggest_deck

                raw_results = suggest_deck(
                    raw_pool,
                    metrics,
                    self.configuration,
                    event_type,
                    _progress_cb,
                    dataset_name,
                )
                self.after(0, lambda: self._finalize_build(raw_results))
            except Exception as e:
                self.after(0, lambda: self._handle_builder_error(str(e)))

        self.sim_executor.submit(_worker)

    def _finalize_build(self, sorted_decks):
        self.is_building = False
        if getattr(self, "app_context", None) and hasattr(
            self.app_context, "loading_overlay"
        ):
            self.app_context.loading_overlay.hide()

        if not sorted_decks:
            msg = "Not enough data or playables to suggest a deck"
            self.suggestions = {}
            self._update_dropdown_options([msg])
            self.var_archetype.set(msg)
            return

        self.suggestions = sorted_decks
        dropdown_labels = list(sorted_decks.keys())
        self._update_dropdown_options(dropdown_labels)

        # Always snap to the mathematically strongest deck once analysis completes
        self._on_deck_selection_change(dropdown_labels[0])

    def _handle_builder_error(self, error_msg):
        self.is_building = False
        if getattr(self, "app_context", None) and hasattr(
            self.app_context, "loading_overlay"
        ):
            self.app_context.loading_overlay.hide()

        msg = "Builder Error"
        self.suggestions = {}
        self._update_dropdown_options([msg])
        self.var_archetype.set(msg)
        self._clear_table()
        import logging

        logging.getLogger(__name__).error(f"Suggest Deck Error: {error_msg}")

    def _update_dropdown_options(self, options: List[str]):
        menu = self.om_archetype["menu"]
        menu.delete(0, "end")
        for opt in options:
            menu.add_command(
                label=opt, command=lambda v=opt: self._on_deck_selection_change(v)
            )

    def _on_deck_selection_change(self, label: str):
        if label in self.suggestions:
            self.var_archetype.set(label)
            self._render_deck(label)

    def _update_tables(self):
        """Helper to redraw tables after the Auto-Optimizer modifies the deck lists."""
        total_main_cards = sum(
            c.get(constants.DATA_FIELD_COUNT, 1) for c in self.current_deck_list
        )

        notebook = getattr(self, "notebook", None)
        deck_frame = getattr(self, "deck_frame", None)
        if notebook and deck_frame:
            try:
                notebook.tab(deck_frame, text=f" MAIN DECK ({total_main_cards}) ")
            except Exception:
                pass

        table = getattr(self, "table", None)
        if table:
            for item in table.get_children():
                table.delete(item)

        sb_table = getattr(self, "sb_table", None)
        if sb_table:
            for item in sb_table.get_children():
                sb_table.delete(item)

        from src.card_logic import row_color_tag

        def populate_tree(manager, source_list):
            if not manager or not manager.tree:
                return
            tree = manager.tree

            for idx, card in enumerate(source_list):
                name = card.get(constants.DATA_FIELD_NAME, "Unknown")
                count = card.get(constants.DATA_FIELD_COUNT, 1)
                cmc = card.get(constants.DATA_FIELD_CMC, 0)
                types = " ".join(card.get(constants.DATA_FIELD_TYPES, []))
                card_colors = "".join(card.get(constants.DATA_FIELD_COLORS, []))

                row_values = []
                for field in manager.active_fields:
                    if field == "name":
                        row_values.append(name)
                    elif field == "count":
                        row_values.append(str(count))
                    elif field == "cmc":
                        row_values.append(str(cmc))
                    elif field == "types":
                        row_values.append(types)
                    elif field == "colors":
                        row_values.append(card_colors)
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
                    elif field == "personal":
                        p_stats = card.get("deck_colors", {}).get("Personal", {})
                        val = p_stats.get("gihwr", 0.0)
                        smp = p_stats.get("samples", 0)
                        if smp > 0:
                            row_values.append(f"{val:.1f}%")
                        else:
                            row_values.append("-")
                    else:
                        stats = card.get("deck_colors", {})
                        arch_stats = stats.get(self.current_archetype_key, {})
                        if not arch_stats.get("gihwr"):
                            arch_stats = stats.get("All Decks", {})

                        val = arch_stats.get(field, 0.0)
                        if val > 0:
                            row_values.append(f"{val:.1f}%")
                        else:
                            row_values.append("-")

                tag = "bw_odd" if idx % 2 == 0 else "bw_even"
                if self.configuration.settings.card_colors_enabled:
                    tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

                tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=row_values,
                    tags=(tag,),
                )
            if hasattr(tree, "reapply_sort"):
                tree.reapply_sort()

        if table:
            populate_tree(self.table_manager, self.current_deck_list)
        if sb_table:
            populate_tree(self.sb_manager, self.current_sb_list)

    def _render_deck_stats(self):
        stats_frame = getattr(self, "stats_frame", None)
        if not stats_frame or not stats_frame.winfo_exists():
            return

        for widget in stats_frame.winfo_children():
            widget.destroy()

        if not self.current_deck_list:
            return

        total_cards = sum(c.get("count", 1) for c in self.current_deck_list)
        creatures = sum(
            c.get("count", 1)
            for c in self.current_deck_list
            if "Creature" in c.get("types", [])
        )
        lands = sum(
            c.get("count", 1)
            for c in self.current_deck_list
            if "Land" in c.get("types", [])
        )
        spells = total_cards - creatures - lands

        pips = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        curve = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        tags = {}
        cmc_sum = 0
        non_lands = 0

        for c in self.current_deck_list:
            count = c.get("count", 1)
            if "Land" not in c.get("types", []):
                non_lands += count
                cmc = int(c.get("cmc", 0))
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

        avg_cmc = cmc_sum / non_lands if non_lands else 0

        comp_frame = ttk.Frame(stats_frame)
        comp_frame.pack(fill="x", pady=5)
        ttk.Label(
            comp_frame,
            text="DECK COMPOSITION",
            font=(Theme.FONT_FAMILY, 10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        ttk.Label(
            comp_frame,
            text=f"Total Cards: {total_cards}  |  Creatures: {creatures}  |  Non-Creatures: {spells}  |  Lands: {lands}",
        ).pack(anchor="w", pady=2)

        ttk.Separator(stats_frame, orient="horizontal").pack(fill="x", pady=8)

        color_frame = ttk.Frame(stats_frame)
        color_frame.pack(fill="x", pady=5)
        ttk.Label(
            color_frame,
            text="COLOR REQUIREMENTS (PIPS)",
            font=(Theme.FONT_FAMILY, 10, "bold"),
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
        ).pack(anchor="w", pady=2)

        ttk.Separator(stats_frame, orient="horizontal").pack(fill="x", pady=8)

        tags_frame = ttk.Frame(stats_frame)
        tags_frame.pack(fill="x", pady=5)
        ttk.Label(
            tags_frame,
            text="ROLES & SYNERGIES",
            font=(Theme.FONT_FAMILY, 10, "bold"),
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
                    anchor="w", pady=2
                )
        else:
            ttk.Label(tags_frame, text="No Scryfall tags found for this set.").pack(
                anchor="w", pady=2
            )

        ttk.Separator(stats_frame, orient="horizontal").pack(fill="x", pady=8)

        curve_frame = ttk.Frame(stats_frame)
        curve_frame.pack(fill="x", pady=5)
        ttk.Label(
            curve_frame,
            text=f"MANA CURVE (Avg CMC: {avg_cmc:.2f})",
            font=(Theme.FONT_FAMILY, 10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")

        for i in range(1, 7):
            label = f"{i} CMC: " if i < 6 else "6+ CMC:"
            count = curve[i]
            bar = "█" * count
            ttk.Label(
                curve_frame,
                text=f"{label:<8} {bar} ({count})",
                font=(constants.FONT_MONO_SPACE, 10),
            ).pack(anchor="w", pady=1)

    def _render_deck(self, label: str):
        self._clear_table()
        data = self.suggestions.get(label)
        if not data:
            return

        deck_colors = data.get("colors", [])
        self.current_archetype_key = (
            "".join(sorted(deck_colors)) if deck_colors else "All Decks"
        )
        if not self.current_archetype_key:
            self.current_archetype_key = "All Decks"

        self.current_deck_list = data.get("deck_cards", [])
        self.current_sb_list = data.get("sideboard_cards", [])

        def card_sort_key(x):
            return (
                x.get(constants.DATA_FIELD_CMC, 0),
                x.get(constants.DATA_FIELD_NAME, ""),
            )

        self.current_deck_list.sort(key=card_sort_key)
        self.current_sb_list.sort(key=card_sort_key)

        breakdown = data.get("breakdown", "")
        if hasattr(self, "lbl_deck_notes") and self.lbl_deck_notes.winfo_exists():
            self.lbl_deck_notes.config(text=breakdown)

        self._render_deck_stats()
        self._update_tables()

        # Render Monte Carlo directly from cached data computed during build phase
        stats = data.get("stats")
        opt_note = data.get("optimization_note")
        if stats:
            self._show_sim_results(stats, opt_note)
        else:
            self._show_sim_error("Simulation data missing.")

        # Draw sample hand seamlessly if the user is currently looking at the tab
        notebook = getattr(self, "notebook", None)
        if notebook and notebook.winfo_exists():
            current_tab = notebook.tab(notebook.select(), "text")
            if "SIMULATION & SAMPLE HAND" in current_tab:
                self.after(100, self._draw_sample_hand)

    def _copy_to_clipboard(self):
        selection = self.var_archetype.get()
        if selection in self.suggestions:
            deck_data = self.suggestions[selection]
            export_text = copy_deck(
                deck_data.get("deck_cards", []), deck_data.get("sideboard_cards", [])
            )
            self.clipboard_clear()
            self.clipboard_append(export_text)

            self.btn_copy.config(text="Copied! ✔", bootstyle="success")
            self.after(
                2000,
                lambda: self.btn_copy.config(text="Copy Deck", bootstyle="primary"),
            )

    def _on_selection(self, event, is_sb=False):
        tree = getattr(self, "sb_table" if is_sb else "table", None)
        if not tree:
            return

        selection = tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        source_list = self.current_sb_list if is_sb else self.current_deck_list
        if idx < len(source_list):
            card = source_list[idx]
            CardToolTip.create(
                tree,
                card,
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
            )
