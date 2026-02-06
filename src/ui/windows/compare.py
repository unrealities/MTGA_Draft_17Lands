"""
src/ui/windows/compare.py

This module implements the Card Compare window.
It allows users to manually add cards to a list to compare their statistics side-by-side.
This is particularly useful for P1P1 decisions or when logs are unavailable.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.configuration import Configuration
from src.card_logic import CardResult, field_process_sort, filter_options
from src.ui.styles import Theme
from src.ui.components import (
    ModernTreeview,
    AutocompleteEntry,
    identify_safe_coordinates,
    CardToolTip,
)


class CompareWindow(tkinter.Toplevel):
    """
    Window for comparing cards side-by-side.
    """

    def __init__(self, parent, draft_manager, configuration: Configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.title("Compare Cards")
        self.resizable(False, True)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)
        self.attributes("-topmost", True)

        # State
        self.compare_list: List[Dict[str, Any]] = []
        self.card_data_map = self.draft.set_data.get_card_ratings() or {}

        # Build UI
        self._build_ui()

        # Position
        self.update_idletasks()
        self._position_window(parent)

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # --- Input Area ---
        input_frame = ttk.Frame(container)
        input_frame.pack(fill="x", pady=(0, 10))

        # Autocomplete Entry
        card_names = [v[constants.DATA_FIELD_NAME] for v in self.card_data_map.values()]
        self.entry_card = AutocompleteEntry(
            input_frame, completion_list=card_names, width=40
        )
        self.entry_card.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_card.bind("<Return>", self._add_card)
        self.entry_card.focus_set()

        # Clear Button
        btn_clear = ttk.Button(input_frame, text="Clear", command=self._clear_table)
        btn_clear.pack(side="right")

        # --- Table Area ---
        # Define Columns based on Settings
        self.cols = ["Card"]
        # Map config keys to internal data keys using constants
        # We read from configuration on init
        self.headers_map = {
            "Card": {"width": 180, "anchor": tkinter.W},
        }

        # Helper to get field key from config setting
        def get_field_key(setting_val):
            from src.constants import COLUMNS_OPTIONS_EXTRA_DICT

            # If the config value is a Label (e.g., "ALSA: ..."), map it back.
            # If it is already a key, use it.
            if setting_val in COLUMNS_OPTIONS_EXTRA_DICT.values():
                return setting_val

            # Try to find it in the dict values (reverse lookup) - simplified assumption here
            # Ideally config stores the key.
            return setting_val

        settings = self.configuration.settings
        config_cols = [
            settings.column_2,
            settings.column_3,
            settings.column_4,
            settings.column_5,
            settings.column_6,
            settings.column_7,
        ]

        self.active_fields = [constants.DATA_FIELD_NAME]

        for idx, col_setting in enumerate(config_cols):
            field_key = get_field_key(col_setting)
            if field_key != constants.DATA_FIELD_DISABLED:
                col_name = field_key.upper()
                self.cols.append(col_name)
                self.headers_map[col_name] = {"width": 60, "anchor": tkinter.CENTER}
                self.active_fields.append(field_key)

        # Create Table
        self.table = ModernTreeview(
            container, columns=self.cols, headers_config=self.headers_map, height=10
        )
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _add_card(self, event=None):
        name_input = self.entry_card.get().strip()
        if not name_input:
            return

        found_card = None
        # Quick lookup
        for key, data in self.card_data_map.items():
            if data[constants.DATA_FIELD_NAME].lower() == name_input.lower():
                found_card = data
                break

        if found_card and found_card not in self.compare_list:
            self.compare_list.append(found_card)
            self.entry_card.delete(0, tkinter.END)
            self._update_table()
        else:
            pass

    def _clear_table(self):
        self.compare_list.clear()
        self._update_table()

    def _update_table(self):
        # 1. Clear current items
        for item in self.table.get_children():
            self.table.delete(item)

        if not self.compare_list:
            return

        # 2. Determine Deck Colors for Filtering
        taken_cards = self.draft.retrieve_taken_cards()
        # Get current deck filter setting
        deck_filter = self.configuration.settings.deck_filter

        # If 'Auto', calculate colors
        filtered_colors = [deck_filter]
        if deck_filter == constants.FILTER_OPTION_AUTO:
            from src.card_logic import filter_options
            metrics = self.draft.retrieve_set_metrics()
            filtered_colors = filter_options(
                taken_cards, deck_filter, metrics, self.configuration
            )

        # 3. Process Data
        # We use CardResult helper to calculate the values for the columns
        from src.card_logic import CardResult

        metrics = self.draft.retrieve_set_metrics()
        tier_data = self.draft.retrieve_tier_data()  # Need method on scanner/manager

        processor = CardResult(
            metrics, tier_data, self.configuration, self.draft.current_pick
        )

        # return_results returns a list of dicts with a "results" key containing the list of values
        processed_cards = processor.return_results(
            self.compare_list, filtered_colors, self.active_fields
        )

        # 4. Sort (Default: Sort by first stats column descending)
        # If we have at least 2 columns (Name + 1 Stat), sort by that stat
        sort_index = 1 if len(self.active_fields) > 1 else 0

        processed_cards.sort(
            key=lambda x: field_process_sort(x["results"][sort_index]), reverse=True
        )

        # 5. Populate Table
        for idx, p_card in enumerate(processed_cards):
            # Row Tag for Coloring
            from src.card_logic import row_color_tag

            # We need the original card object to check colors for the tag
            # return_results copies the card, so keys like 'colors'/'mana_cost' should exist

            tag = ""
            if self.configuration.settings.card_colors_enabled:
                # Handle Lands vs Spells logic
                c_colors = p_card.get(constants.DATA_FIELD_MANA_COST, "")
                if constants.CARD_TYPE_LAND in p_card.get(
                    constants.DATA_FIELD_TYPES, []
                ):
                    c_colors = p_card.get(constants.DATA_FIELD_COLORS, [])
                tag = row_color_tag(c_colors)
            else:
                tag = "bw_odd" if idx % 2 != 0 else "bw_even"

            self.table.insert(
                "",
                "end",
                iid=idx,  # Simple index ID
                values=p_card["results"],
                tags=(tag,),
            )

        # Store processed list for selection mapping
        self.current_display_list = processed_cards

    def _on_selection(self, event):
        selection = self.table.selection()
        if not selection:
            return

        # Get the index
        idx = int(selection[0])
        if idx < len(self.current_display_list):
            card_data = self.current_display_list[idx]

            # Show Tooltip
            # We need to reconstruct the stats dict for the tooltip
            # This is a bit redundant but ensures the tooltip has full data
            # including what might not be in the table columns (like images)

            # Fetch original data again to get images
            orig_card = next(
                (
                    c
                    for c in self.compare_list
                    if c[constants.DATA_FIELD_NAME]
                    == card_data[constants.DATA_FIELD_NAME]
                ),
                None,
            )

            if orig_card:
                # Prepare stats structure for tooltip
                # The tooltip expects { "Color": { "field": val ... } }
                # The card data from CardResult has nested deck_colors
                stats = orig_card.get(constants.DATA_FIELD_DECK_COLORS, {})
                images = orig_card.get(constants.DATA_SECTION_IMAGES, [])

                CardToolTip(
                    self.table,
                    orig_card[constants.DATA_FIELD_NAME],
                    stats,
                    images,
                    self.configuration.features.images_enabled,
                    1.0,  # Scale
                    None,  # Tier info if available
                )

    def _position_window(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 400, 50)
        self.wm_geometry(f"+{x}+{y}")
