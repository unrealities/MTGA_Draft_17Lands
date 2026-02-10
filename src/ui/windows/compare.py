"""
src/ui/windows/compare.py
Manual Card Comparison Panel.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.configuration import Configuration
from src.card_logic import CardResult, field_process_sort, filter_options
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, AutocompleteEntry, CardToolTip


class ComparePanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration: Configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        # Internal State
        self.compare_list: List[Dict] = []  # Stores the source card objects
        self.card_data_map: Dict[str, Dict] = {}
        self.current_display_list: List[Dict] = (
            []
        )  # Stores processed results for the Treeview

        self._build_ui()
        self.refresh()

    def refresh(self):
        """
        Public entry point for state changes.
        Re-indexes autocomplete and re-calculates comparison stats.
        """
        # 1. Update the master mapping from the current scanner dataset
        self.card_data_map = self.draft.set_data.get_card_ratings() or {}

        # 2. Update Autocomplete source names
        names = [v[constants.DATA_FIELD_NAME] for v in self.card_data_map.values()]
        self.entry_card.set_completion_list(names)

        # 3. Re-build columns to match current Preferences
        self._rebuild_columns()

        # 4. Update the actual data rows
        self._update_content()

    def _build_ui(self):
        # --- Control Bar ---
        self.bar = ttk.Frame(self, style="Card.TFrame", padding=5)
        self.bar.pack(fill="x", pady=(0, 5))

        ttk.Label(
            self.bar,
            text="SEARCH CARD:",
            style="SubHeader.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(side="left", padx=5)

        self.entry_card = AutocompleteEntry(self.bar, completion_list=[], width=40)
        self.entry_card.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_card.bind("<Return>", self._add_card)

        ttk.Button(self.bar, text="Add", width=8, command=self._add_card).pack(
            side="left", padx=2
        )
        ttk.Button(self.bar, text="Clear Table", command=self._clear_list).pack(
            side="right", padx=5
        )

        # --- Table Area ---
        self.table_container = ttk.Frame(self)
        self.table_container.pack(fill="both", expand=True)

    def _rebuild_columns(self):
        """Syncs the table headers with the global Settings -> Columns configuration."""
        settings = self.configuration.settings
        cols = ["Card"]
        headers = {"Card": {"width": 200, "anchor": tkinter.W}}
        self.active_fields = [constants.DATA_FIELD_NAME]

        # Capture the Dashboard's Column 2-7 preferences
        config_cols = [
            settings.column_2,
            settings.column_3,
            settings.column_4,
            settings.column_5,
            settings.column_6,
            settings.column_7,
        ]

        # Label mapping (e.g., 'ever_drawn_win_rate' -> 'GIHWR')
        k2l = {
            v: k.split(":")[0] for k, v in constants.COLUMNS_OPTIONS_EXTRA_DICT.items()
        }

        for val in config_cols:
            if val != constants.DATA_FIELD_DISABLED:
                lbl = k2l.get(val, val.upper())
                cols.append(lbl)
                headers[lbl] = {"width": 65, "anchor": tkinter.CENTER}
                self.active_fields.append(val)

        # Redraw Treeview only if columns actually changed
        if not hasattr(self, "table") or list(self.table["columns"]) != cols:
            for w in self.table_container.winfo_children():
                w.destroy()
            self.table = ModernTreeview(
                self.table_container, columns=cols, headers_config=headers
            )
            self.table.pack(fill="both", expand=True)
            self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _add_card(self, event=None):
        """Validates input against dataset and adds to the compare list."""
        typed = self.entry_card.get().strip().lower()
        if not typed:
            return

        # Search the current set map (Case-Insensitive)
        found = next(
            (
                d
                for d in self.card_data_map.values()
                if d[constants.DATA_FIELD_NAME].lower() == typed
            ),
            None,
        )

        if found:
            if found not in self.compare_list:
                self.compare_list.append(found)
                self._update_content()
            self.entry_card.delete(0, tkinter.END)
        else:
            # 1% Dev UX: Visual feedback on 'Not Found'
            self.entry_card.config(highlightbackground=Theme.ERROR)
            self.after(
                500,
                lambda: self.entry_card.config(highlightbackground=Theme.BG_SECONDARY),
            )

    def _clear_list(self):
        """Wipes the manual comparison state."""
        self.compare_list.clear()
        self._update_content()

    def _update_content(self):
        """Calculates 17Lands stats for the compare list based on active filters."""
        if not hasattr(self, "table"):
            return
        for item in self.table.get_children():
            self.table.delete(item)

        if not self.compare_list:
            return

        # Sync with global filters
        metrics = self.draft.retrieve_set_metrics()
        colors = filter_options(
            self.draft.retrieve_taken_cards(),
            self.configuration.settings.deck_filter,
            metrics,
            self.configuration,
        )

        processor = CardResult(
            metrics,
            self.draft.retrieve_tier_data(),
            self.configuration,
            self.draft.current_pick,
        )

        # Re-fetch card data from map to handle set changes/updates
        active_list = []
        for c in self.compare_list:
            c_name = c[constants.DATA_FIELD_NAME]
            # Try to find the same-named card in the NEW set/source
            actual = next(
                (
                    v
                    for v in self.card_data_map.values()
                    if v[constants.DATA_FIELD_NAME] == c_name
                ),
                None,
            )
            if actual:
                active_list.append(actual)

        if not active_list:
            return

        processed = processor.return_results(active_list, colors, self.active_fields)

        # Sort by first stat column descending (standard for comparison)
        sort_idx = 1 if len(self.active_fields) > 1 else 0
        processed.sort(
            key=lambda x: field_process_sort(x["results"][sort_idx]), reverse=True
        )

        self.current_display_list = processed

        from src.card_logic import row_color_tag

        for idx, p_card in enumerate(processed):
            tag = (
                row_color_tag(p_card.get(constants.DATA_FIELD_MANA_COST, ""))
                if self.configuration.settings.card_colors_enabled
                else ("bw_odd" if idx % 2 == 0 else "bw_even")
            )
            self.table.insert("", "end", iid=idx, values=p_card["results"], tags=(tag,))

    def _on_selection(self, event):
        """Triggers the image tooltip."""
        sel = self.table.selection()
        if not sel:
            return
        idx = int(sel[0])
        card_data = self.current_display_list[idx]
        card_name = card_data["results"][0]

        # Re-map back to original object for image URLs
        orig = next(
            (c for c in self.compare_list if c[constants.DATA_FIELD_NAME] == card_name),
            None,
        )
        if not orig:
            orig = next(
                (
                    c
                    for c in self.card_data_map.values()
                    if c[constants.DATA_FIELD_NAME] == card_name
                ),
                None,
            )

        if orig:
            CardToolTip(
                self.table,
                orig[constants.DATA_FIELD_NAME],
                orig.get(constants.DATA_FIELD_DECK_COLORS, {}),
                orig.get(constants.DATA_SECTION_IMAGES, []),
                self.configuration.features.images_enabled,
                1.0,
            )
