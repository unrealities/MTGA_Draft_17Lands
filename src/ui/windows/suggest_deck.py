"""
src/ui/windows/suggest_deck.py
Professional Deck Builder Panel.
Uses the Advisor Engine to suggest optimal archetypes from the pool.
Displays Main Deck and Sideboard in separate notebook tabs.
Includes a 10,000 game Monte Carlo Simulation for elite pro-level analysis.
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
from src.card_logic import suggest_deck, copy_deck
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip, AutoScrollbar
from src.utils import bind_scroll


class SuggestDeckPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.suggestions: Dict[str, Any] = {}
        self.current_deck_list: List[Dict] = []
        self.current_sb_list: List[Dict] = []
        self.current_archetype_key: str = ""

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
        self.header.pack(fill="x", pady=(0, 5))

        self.lbl_archetype = ttk.Label(
            self.header,
            text="ARCHETYPE:",
            font=(Theme.FONT_FAMILY, 8, "bold"),
            bootstyle="primary",
        )
        self.lbl_archetype.pack(side="left", padx=5)
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

        self.var_archetype = tkinter.StringVar()
        self.om_archetype = ttk.OptionMenu(
            self.header,
            self.var_archetype,
            "",
            style="TMenubutton",
            command=self._on_deck_selection_change,
        )
        self.om_archetype.pack(side="left", padx=10, fill="x", expand=True)

        self.btn_copy = ttk.Button(
            self.header, text="Copy Deck", width=12, command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="right", padx=5)

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

        # Right Column: Monte Carlo Simulation
        self.sim_frame = ttk.Labelframe(
            self.hand_tab, text=" MONTE CARLO SIMULATION (10,000 Games) ", padding=15
        )
        self.sim_frame.grid(row=1, column=1, sticky="nsew")

        self.sim_label = ttk.Label(
            self.sim_frame,
            text="Generate a deck to run simulations.",
            font=(Theme.FONT_FAMILY, 11),
        )
        self.sim_label.pack(pady=20)

    def _run_monte_carlo_task(self, deck_list):
        self.after(0, self._show_sim_loading)
        try:
            stats = self._simulate_deck(deck_list, iterations=10000)
            self.after(0, lambda: self._show_sim_results(stats))
        except Exception as e:
            self.after(0, lambda e=e: self._show_sim_error(str(e)))

    def _show_sim_loading(self):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()

        ttk.Label(
            self.sim_frame,
            text="Running 10,000 Monte Carlo Simulations...",
            font=(Theme.FONT_FAMILY, 10, "italic"),
            bootstyle="secondary",
        ).pack(pady=20)

        progress = ttk.Progressbar(self.sim_frame, mode="indeterminate")
        progress.pack(fill="x", padx=20)
        progress.start(15)

    def _show_sim_error(self, error):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()
        ttk.Label(
            self.sim_frame, text=f"Simulation Error:\n{error}", bootstyle="danger"
        ).pack(pady=20)

    def _show_sim_results(self, stats):
        for widget in self.sim_frame.winfo_children():
            widget.destroy()

        if not stats:
            ttk.Label(
                self.sim_frame,
                text="Deck must have 40 cards to run simulations.",
                bootstyle="warning",
            ).pack(pady=20)
            return

        def _add_stat(label, value, thresholds, reverse=False, is_percent=True):
            frame = ttk.Frame(self.sim_frame)
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

        ttk.Separator(self.sim_frame).pack(fill="x", pady=8)

        ttk.Label(
            self.sim_frame,
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

        ttk.Separator(self.sim_frame).pack(fill="x", pady=8)

        # --- ADVISOR SUMMARY LOGIC ---
        ttk.Label(
            self.sim_frame,
            text="ADVISOR SUMMARY",
            bootstyle="info",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        advice = []
        if stats["cast_t2"] < 50:
            advice.append("• Add more 2-drops to improve early board presence.")
        if stats["color_screw_t3"] > 15:
            advice.append(
                "• High color screw risk. Consider cutting a splash card or adding more fixing."
            )
        if stats["screw_t3"] > 20:
            advice.append(
                "• Frequently missing land drops. Consider running an extra land."
            )
        if stats["flood_t5"] > 25:
            advice.append(
                "• High flood risk. Consider cutting a land or adding mana sinks."
            )
        if stats["removal_t4"] < 45:
            advice.append("• Low early interaction. Prioritize cheap removal.")

        # Swap Suggestions
        if stats["cast_t2"] < 50 or stats["flood_t5"] > 25:
            expensive_cards = [
                c
                for c in self.current_deck_list
                if int(c.get("cmc", 0)) >= 5 and "Land" not in c.get("types", [])
            ]
            if expensive_cards:
                worst_expensive = min(
                    expensive_cards,
                    key=lambda x: x.get("deck_colors", {})
                    .get("All Decks", {})
                    .get("gihwr", 0),
                )
                cheap_sb = [
                    c
                    for c in self.current_sb_list
                    if int(c.get("cmc", 0)) <= 3
                    and "Land" not in c.get("types", [])
                    and "Creature" in c.get("types", [])
                ]
                if cheap_sb:
                    best_cheap = max(
                        cheap_sb,
                        key=lambda x: x.get("deck_colors", {})
                        .get("All Decks", {})
                        .get("gihwr", 0),
                    )
                    advice.append(
                        f"• Swap: Cut [{worst_expensive['name']}] for [{best_cheap['name']}] to lower curve."
                    )

        if not advice:
            advice.append(
                "• Your deck composition and mana base look statistically solid!"
            )

        for tip in advice:
            ttk.Label(
                self.sim_frame, text=tip, font=(Theme.FONT_FAMILY, 9), wraplength=280
            ).pack(anchor="w", pady=2)

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
                        "cmc": int(c.get("cmc", 0)),
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
                # London Mulligan Heuristic: Drop the highest CMC cards.
                # (Lands have CMC 0 so they are safely kept unless we draw 5+ of them)
                current_7.sort(key=lambda x: x["cmc"])

            kept_hand = current_7[:kept_size]
            deck_rest = flat_deck[start_idx + 7 :]

            # Reconstruct the game state
            game_state = kept_hand + deck_rest

            # On the Play Draw Sequences
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

            # Color Screw logic (3+ lands, have 3-cmc or less spell, but can't cast due to colors)
            if len(lands_t3) >= 3:
                color_sources = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
                for l in lands_t3:
                    for c in l["colors_produced"]:
                        color_sources[c] += 1

                t3_spells = [c for c in t3_state if not c["is_land"] and c["cmc"] <= 3]
                any_color_screw = False
                for s in t3_spells:
                    for pip, count in s["pips"].items():
                        if color_sources[pip] < count:
                            any_color_screw = True
                            break
                if any_color_screw:
                    stats["color_screw_t3"] += 1

        stats["avg_hand_size"] = stats["avg_hand_size"] / iterations
        for k in list(stats.keys()):
            if k != "avg_hand_size":
                stats[k] = (stats[k] / iterations) * 100.0

        return stats

    def _clear_sample_hand(self):
        for widget in self.hand_container.winfo_children():
            widget.destroy()
        self.hand_images.clear()
        self.hand_frames = []

    def _draw_sample_hand(self):
        self._clear_sample_hand()

        if not self.current_deck_list:
            ttk.Label(
                self.hand_container,
                text="Generate a deck first.",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(pady=20)
            return

        flat_deck = []
        for c in self.current_deck_list:
            flat_deck.extend([c] * int(c.get("count", 1)))

        if len(flat_deck) < 7:
            ttk.Label(
                self.hand_container,
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

        stack_container = ttk.Frame(self.hand_container, width=img_w, height=stack_h)
        stack_container.pack(expand=True, pady=15)
        stack_container.pack_propagate(False)

        def restore_z_order(event=None):
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
        if hasattr(self, "stats_canvas") and self.stats_canvas.winfo_exists():
            self.stats_canvas.configure(bg=Theme.BG_PRIMARY)
        if hasattr(self, "hand_canvas") and self.hand_canvas.winfo_exists():
            self.hand_canvas.configure(bg=Theme.BG_PRIMARY)

    def _calculate_suggestions(self):
        try:
            raw_pool = self.draft.retrieve_taken_cards()
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

            raw_results = suggest_deck(
                raw_pool, metrics, self.configuration, event_type
            )

            if not raw_results:
                msg = "Not enough data or playables to suggest a deck"
                self.suggestions = {}
                self._update_dropdown_options([msg])
                self.var_archetype.set(msg)
                self._clear_table()
                return

            self.suggestions = {}
            dropdown_labels = []

            sorted_keys = sorted(
                raw_results.keys(),
                key=lambda k: raw_results[k].get("rating", 0),
                reverse=True,
            )

            for k in sorted_keys:
                data = raw_results[k]
                notes = f" -> {data.get('breakdown')}" if data.get("breakdown") else ""
                label = f"{k} [Est: {data.get('record', 'Unknown')}] (Power: {data.get('rating', 0):.0f}){notes}"

                self.suggestions[label] = data
                dropdown_labels.append(label)

            current_sel = self.var_archetype.get()
            self._update_dropdown_options(dropdown_labels)

            if current_sel in dropdown_labels:
                self._on_deck_selection_change(current_sel)
            elif dropdown_labels:
                self._on_deck_selection_change(dropdown_labels[0])

        except Exception:
            msg = "Builder Error"
            self.suggestions = {}
            self._update_dropdown_options([msg])
            self.var_archetype.set(msg)
            self._clear_table()

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

    def _clear_table(self):
        if self.table:
            for item in self.table.get_children():
                self.table.delete(item)
        if self.sb_table:
            for item in self.sb_table.get_children():
                self.sb_table.delete(item)
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        for widget in self.sim_frame.winfo_children():
            widget.destroy()

        self._clear_sample_hand()

        self.current_deck_list = []
        self.current_sb_list = []
        self.notebook.tab(self.deck_frame, text=" MAIN DECK (0) ")

    def _render_deck_stats(self):
        for widget in self.stats_frame.winfo_children():
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

        comp_frame = ttk.Frame(self.stats_frame)
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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=8)

        color_frame = ttk.Frame(self.stats_frame)
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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=8)

        tags_frame = ttk.Frame(self.stats_frame)
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

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=8)

        curve_frame = ttk.Frame(self.stats_frame)
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

        self._render_deck_stats()

        from src.card_logic import row_color_tag

        total_main_cards = sum(
            c.get(constants.DATA_FIELD_COUNT, 1) for c in self.current_deck_list
        )
        self.notebook.tab(self.deck_frame, text=f" MAIN DECK ({total_main_cards}) ")

        def populate_tree(tree, source_list):
            if not tree:
                return
            for idx, card in enumerate(source_list):
                name = card.get(constants.DATA_FIELD_NAME, "Unknown")
                count = card.get(constants.DATA_FIELD_COUNT, 1)
                cmc = card.get(constants.DATA_FIELD_CMC, 0)
                types = " ".join(card.get(constants.DATA_FIELD_TYPES, []))
                card_colors = "".join(card.get(constants.DATA_FIELD_COLORS, []))
                stats = card.get("deck_colors", {})

                arch_stats = stats.get(self.current_archetype_key, {})
                if not arch_stats.get("gihwr"):
                    arch_stats = stats.get("All Decks", {})

                gihwr_val = arch_stats.get("gihwr", 0.0)
                gihwr_str = f"{gihwr_val:.1f}%" if gihwr_val > 0 else "-"

                tag = "bw_odd" if idx % 2 == 0 else "bw_even"
                if self.configuration.settings.card_colors_enabled:
                    tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

                tree.insert(
                    "",
                    "end",
                    iid=idx,
                    values=(name, count, cmc, types, card_colors, gihwr_str),
                    tags=(tag,),
                )
            if hasattr(tree, "reapply_sort"):
                tree.reapply_sort()

        populate_tree(self.table, self.current_deck_list)
        populate_tree(self.sb_table, self.current_sb_list)

        # Trigger Background Monte Carlo Simulation and Sample Hand
        self.sim_executor.submit(self._run_monte_carlo_task, self.current_deck_list)
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
        tree = self.sb_table if is_sb else self.table
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
