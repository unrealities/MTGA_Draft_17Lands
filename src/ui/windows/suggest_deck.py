"""
src/ui/windows/suggest_deck.py
Professional Deck Builder Panel.
Uses the Advisor Engine to suggest optimal archetypes from the pool.
Displays Main Deck and Sideboard in separate notebook tabs.
"""

import tkinter
from tkinter import ttk
from typing import Dict, Any, List

from src import constants
from src.card_logic import suggest_deck, copy_deck
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip


class SuggestDeckPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.suggestions: Dict[str, Any] = {}
        self.current_deck_list: List[Dict] = []
        self.current_sb_list: List[Dict] = []
        self.current_archetype_key: str = ""

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

    def _on_theme_change(self, event=None):
        pass

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
        self.current_deck_list = []
        self.current_sb_list = []
        self.notebook.tab(self.deck_frame, text=" MAIN DECK (0) ")

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
