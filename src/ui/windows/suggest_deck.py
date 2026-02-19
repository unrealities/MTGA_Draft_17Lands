"""
src/ui/windows/suggest_deck.py
Professional Deck Builder Panel.
Uses the Advisor Engine to suggest optimal archetypes from the pool.
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
        self.current_archetype_key: str = ""

        self._build_ui()
        self.refresh()

    @property
    def table(self) -> ttk.Treeview:
        """Dynamically retrieves the current tree widget from the manager."""
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    def refresh(self):
        """Triggers the archetype building algorithm and refreshes the view."""
        self._calculate_suggestions()

    def _build_ui(self):
        """Constructs the deck selection header and the static data table."""
        self.header = ttk.Frame(self, style="Card.TFrame", padding=5)
        self.header.pack(fill="x", pady=(0, 5))

        ttk.Label(
            self.header,
            text="ARCHETYPE:",
            font=(Theme.FONT_FAMILY, 8, "bold"),
            foreground=Theme.ACCENT,
        ).pack(side="left", padx=5)

        self.var_archetype = tkinter.StringVar()
        self.om_archetype = ttk.OptionMenu(
            self.header,
            self.var_archetype,
            "",
            style="TMenubutton",
            command=self._on_deck_selection_change,
        )
        self.om_archetype.pack(side="left", padx=10, fill="x", expand=True)

        ttk.Button(
            self.header, text="Copy Deck", width=12, command=self._copy_to_clipboard
        ).pack(side="right", padx=5)

        cols = ["Card", "#", "Cost", "Type", "Colors", "GIH WR"]
        self.table_manager = DynamicTreeviewManager(
            self,
            view_id="deck_builder",
            configuration=self.configuration,
            on_update_callback=self.refresh,
            static_columns=cols,
        )
        self.table_manager.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _calculate_suggestions(self):
        """Invokes the card_logic to build decks based on current pool."""
        try:
            raw_pool = self.draft.retrieve_taken_cards()
            metrics = (
                self.orchestrator.scanner.retrieve_set_metrics()
                if hasattr(self, "orchestrator")
                else self.draft.retrieve_set_metrics()
            )

            raw_results = suggest_deck(raw_pool, metrics, self.configuration)

            if not raw_results:
                msg = "No viable decks yet"
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
                label = f"{k} {data.get('type', 'Unknown')} (Rating: {data.get('rating', 0):.0f})"
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
        t = self.table
        if t:
            for item in t.get_children():
                t.delete(item)
        self.current_deck_list = []

    def _render_deck(self, label: str):
        self._clear_table()
        data = self.suggestions.get(label)
        if not data:
            return

        # Extract the archetype key (e.g., "UB" from "UB Consistent...")
        # The key is usually the first part of the label or stored in data['colors'] list
        # We construct a string key from the color list
        deck_colors = data.get("colors", [])
        self.current_archetype_key = (
            "".join(sorted(deck_colors)) if deck_colors else "All Decks"
        )

        # If the constructed key is empty, fallback to All Decks
        if not self.current_archetype_key:
            self.current_archetype_key = "All Decks"

        self.current_deck_list = data.get("deck_cards", [])
        # Sort deck by CMC -> Name
        self.current_deck_list.sort(
            key=lambda x: (
                x.get(constants.DATA_FIELD_CMC, 0),
                x.get(constants.DATA_FIELD_NAME, ""),
            )
        )

        from src.card_logic import row_color_tag

        for idx, card in enumerate(self.current_deck_list):
            name = card.get(constants.DATA_FIELD_NAME, "Unknown")
            count = card.get(constants.DATA_FIELD_COUNT, 1)
            cmc = card.get(constants.DATA_FIELD_CMC, 0)
            types = " ".join(card.get(constants.DATA_FIELD_TYPES, []))
            card_colors = "".join(card.get(constants.DATA_FIELD_COLORS, []))
            stats = card.get("deck_colors", {})

            # Check if we have data for the specific pair (e.g. "UB")
            # If not, check if we have data for "All Decks"
            arch_stats = stats.get(self.current_archetype_key, {})
            if not arch_stats.get("gihwr"):
                arch_stats = stats.get("All Decks", {})

            gihwr_val = arch_stats.get("gihwr", 0.0)
            gihwr_str = f"{gihwr_val:.1f}%" if gihwr_val > 0 else "-"

            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            if self.configuration.settings.card_colors_enabled:
                tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            if self.table:
                self.table.insert(
                    "",
                    "end",
                    iid=idx,
                    values=(name, count, cmc, types, card_colors, gihwr_str),
                    tags=(tag,),
                )

    def _copy_to_clipboard(self):
        selection = self.var_archetype.get()
        if selection in self.suggestions:
            deck_data = self.suggestions[selection]
            export_text = copy_deck(
                deck_data.get("deck_cards", []), deck_data.get("sideboard_cards")
            )
            self.clipboard_clear()
            self.clipboard_append(export_text)

    def _on_selection(self, event):
        selection = self.table.selection()
        if not selection:
            return
        idx = int(selection[0])
        if idx < len(self.current_deck_list):
            card = self.current_deck_list[idx]
            CardToolTip(
                self.table,
                card.get(constants.DATA_FIELD_NAME, "Unknown"),
                card.get(constants.DATA_FIELD_DECK_COLORS, {}),
                card.get(constants.DATA_SECTION_IMAGES, []),
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
            )
