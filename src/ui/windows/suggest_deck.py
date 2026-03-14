"""
src/ui/windows/suggest_deck.py
Professional Deck Builder Panel.
Uses the Advisor Engine to suggest optimal archetypes from the pool.
Displays Main Deck and Sideboard in separate notebook tabs.
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
        self.hand_images = []

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

        # Inner frame where the actual stats widgets will live
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

        # Bind cross-platform scrollwheel
        bind_scroll(self.stats_canvas, self.stats_canvas.yview_scroll)
        bind_scroll(self.stats_frame, self.stats_canvas.yview_scroll)
        self.stats_frame.bind(
            "<Enter>",
            lambda e: bind_scroll(self.stats_frame, self.stats_canvas.yview_scroll),
        )

        # Sample Hand Tab
        self.hand_tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.hand_tab, text=" SAMPLE HAND ")

        hand_control_bar = ttk.Frame(self.hand_tab)
        hand_control_bar.pack(fill="x", pady=(0, 15))

        self.btn_draw = ttk.Button(
            hand_control_bar,
            text="Draw Opening Hand",
            command=self._draw_sample_hand,
            bootstyle="success",
        )
        self.btn_draw.pack(side="left")

        self.hand_container = ttk.Frame(self.hand_tab)
        self.hand_container.pack(fill="both", expand=True)

    def _draw_sample_hand(self):
        # Clear existing hand
        for widget in self.hand_container.winfo_children():
            widget.destroy()
        self.hand_images.clear()

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
        # Increase size for the stacked view for better readability
        img_w = int(220 * scale)
        img_h = int(308 * scale)
        offset_y = int(38 * scale)  # Approximate height of the MTG card title bar

        # Fixed-size container for the stack to center it perfectly
        stack_container = ttk.Frame(
            self.hand_container, width=img_w, height=img_h + (6 * offset_y)
        )
        stack_container.pack(expand=True, pady=15)

        self.hand_frames = []

        def restore_z_order(event=None):
            # Iterating through the array and lifting them in order restores the natural cascade
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

            # Bindings for the temporary label (before image loads)
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

                    # Attach standard tooltip logic so clicking a card in the hand shows its stats
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

                    # Hover effects for the stacked layout
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
            # Leave the placeholder text label if network fails
            pass

    def _on_theme_change(self, event=None):
        if hasattr(self, "stats_canvas") and self.stats_canvas.winfo_exists():
            self.stats_canvas.configure(bg=Theme.BG_PRIMARY)

    def _calculate_suggestions(self):
        """Invokes the card_logic to build decks based on current pool."""
        try:
            raw_pool = self.draft.retrieve_taken_cards()
            metrics = (
                self.orchestrator.scanner.retrieve_set_metrics()
                if hasattr(self, "orchestrator")
                else self.draft.retrieve_set_metrics()
            )

            # Extract the current event type to determine Bo1 vs Bo3 math
            _, event_type = (
                self.orchestrator.scanner.retrieve_current_limited_event()
                if hasattr(self, "orchestrator")
                else self.draft.retrieve_current_limited_event()
            )

            # Pass event_type to suggest_deck
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

            # Sort suggested archetypes by internal 'Deck Rating' descending
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

        self.current_deck_list = []
        self.current_sb_list = []
        self.notebook.tab(self.deck_frame, text=" MAIN DECK (0) ")

    def _render_deck_stats(self):
        """Generates dynamic breakdown of the currently generated deck."""
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

        # 1. Composition
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

        # 2. Color Requirements
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

        # 3. Roles and Tags
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

            # Group into rows of 4 to prevent text run-off
            for i in range(0, len(tag_str), 4):
                ttk.Label(tags_frame, text="    ".join(tag_str[i : i + 4])).pack(
                    anchor="w", pady=2
                )
        else:
            ttk.Label(tags_frame, text="No Scryfall tags found for this set.").pack(
                anchor="w", pady=2
            )

        ttk.Separator(self.stats_frame, orient="horizontal").pack(fill="x", pady=8)

        # 4. Mana Curve
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

        # Sort logically
        def card_sort_key(x):
            return (
                x.get(constants.DATA_FIELD_CMC, 0),
                x.get(constants.DATA_FIELD_NAME, ""),
            )

        self.current_deck_list.sort(key=card_sort_key)
        self.current_sb_list.sort(key=card_sort_key)

        self._render_deck_stats()

        from src.card_logic import row_color_tag

        # Update the Main Deck tab title with the dynamic count
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
