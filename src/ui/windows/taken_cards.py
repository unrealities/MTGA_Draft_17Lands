"""
src/ui/windows/taken_cards.py

This module implements the Taken Cards window.
It displays a list of all cards selected during the current draft,
with filtering options for colors and card types.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.configuration import Configuration
from src.card_logic import CardResult, stack_cards, deck_card_search, field_process_sort
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, identify_safe_coordinates, CardToolTip


class TakenCardsWindow(tkinter.Toplevel):
    """
    Window showing the user's current card pool.
    Features:
    - Filtering by Color (Deck Filter)
    - Filtering by Card Type (Creatures, Lands, etc.)
    - Toggleable Statistics Columns
    - Copy to Clipboard
    """

    def __init__(self, parent, draft_manager, configuration: Configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.title("Taken Cards")
        self.resizable(False, True)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)
        self.attributes("-topmost", True)

        # UI State Variables (mapped to configuration in _build_ui)
        self.vars = {}

        # Data State
        self.current_display_list = []

        # Build UI
        self._build_ui()

        # Initial Population
        self._update_table()

        # Position
        self.update_idletasks()
        self._position_window(parent)

        # Cleanup on close (remove traces if any were added manually, though we rely on command callbacks)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # --- Top Controls: Filters ---
        filter_frame = ttk.Frame(container, style="Card.TFrame", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        # Row 1: Deck Filter & Copy Button
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill="x", pady=(0, 5))

        ttk.Label(row1, text="Deck Filter:").pack(side="left")

        # Deck Filter OptionMenu
        deck_colors = self.draft.retrieve_color_win_rate(
            self.configuration.settings.filter_format
        )
        filter_options = list(deck_colors.keys())

        self.var_deck_filter = tkinter.StringVar(
            value=self.configuration.settings.deck_filter
        )

        # Ensure default value exists in list (it might be "Auto" which resolves dynamically)
        # We'll rely on the update logic to handle specific values

        om_filter = ttk.OptionMenu(
            row1,
            self.var_deck_filter,
            filter_options[0] if filter_options else constants.FILTER_OPTION_AUTO,
            *filter_options,
            style="TMenubutton",
            command=lambda _: self._update_table(),
        )
        om_filter.pack(side="left", fill="x", expand=True, padx=10)

        ttk.Button(row1, text="Copy List", command=self._copy_to_clipboard).pack(
            side="right"
        )

        # Row 2: Card Types
        row2 = ttk.Frame(filter_frame)
        row2.pack(fill="x", pady=(0, 5))

        ttk.Label(row2, text="Show Types:", style="Muted.TLabel").pack(
            side="left", padx=(0, 10)
        )

        type_configs = [
            ("Creatures", "taken_type_creature_enabled", True),
            (
                "Lands",
                "taken_type_land_enabled",
                True,
            ),
            ("Spells", "taken_type_spells_enabled", True),  # Instants/Sorceries
            (
                "Other",
                "taken_type_other_enabled",
                True,
            ),  # Artifacts/Enchantments/Planeswalkers
        ]

        for label, var_name, default in type_configs:
            var = tkinter.IntVar(value=1 if default else 0)
            self.vars[var_name] = var
            cb = ttk.Checkbutton(
                row2, text=label, variable=var, command=self._update_table
            )
            cb.pack(side="left", padx=5)

        # Row 3: Columns (Stats)
        row3 = ttk.Frame(filter_frame)
        row3.pack(fill="x")

        ttk.Label(row3, text="Columns:", style="Muted.TLabel").pack(
            side="left", padx=(0, 23)
        )

        # We bind these to the configuration settings directly if possible, or local vars that update config
        # Mapping to config attributes:
        col_configs = [
            ("GIHWR", "taken_gihwr_enabled"),
            ("ALSA", "taken_alsa_enabled"),
            ("ATA", "taken_ata_enabled"),
            ("GP WR", "taken_gpwr_enabled"),
            ("OH WR", "taken_ohwr_enabled"),
            ("GD WR", "taken_gdwr_enabled"),
            ("GNS WR", "taken_gndwr_enabled"),
            ("IWD", "taken_iwd_enabled"),
            ("WHEEL", "taken_wheel_enabled"),
        ]

        settings = self.configuration.settings

        for label, attr_name in col_configs:
            # Check if attribute exists in settings (GIHWR might not be toggleable in original code?)
            # Assuming GIHWR is always shown based on original code 'Column11'.
            if attr_name == "taken_gihwr_enabled":
                continue

            current_val = getattr(settings, attr_name, False)
            var = tkinter.IntVar(value=int(current_val))
            self.vars[attr_name] = var

            # Callback updates config AND table
            def on_toggle(a=attr_name, v=var):
                setattr(self.configuration.settings, a, bool(v.get()))
                self._rebuild_table_columns()
                self._update_table()

            cb = ttk.Checkbutton(row3, text=label, variable=var, command=on_toggle)
            cb.pack(side="left", padx=5)

        # --- Table Area ---
        # We need a container for the table because we might destroy/recreate it when columns change
        self.table_container = ttk.Frame(container)
        self.table_container.pack(fill="both", expand=True)

        self._rebuild_table_columns()

    def _rebuild_table_columns(self):
        """Reconstructs the Treeview based on selected columns."""
        # Clear existing table if it exists
        for widget in self.table_container.winfo_children():
            widget.destroy()

        # Base Columns
        cols = ["Card", "Count", "Colors"]
        self.headers = {
            "Card": {"width": 200, "anchor": tkinter.W},
            "Count": {"width": 50, "anchor": tkinter.CENTER},
            "Colors": {"width": 60, "anchor": tkinter.CENTER},
        }

        # Dynamic Columns based on settings
        # Mapping UI Label -> Internal Data Key (for CardResult)
        col_map = {
            "taken_alsa_enabled": (constants.DATA_FIELD_ALSA, "ALSA"),
            "taken_ata_enabled": (constants.DATA_FIELD_ATA, "ATA"),
            "taken_gpwr_enabled": (constants.DATA_FIELD_GPWR, "GP WR"),
            "taken_ohwr_enabled": (constants.DATA_FIELD_OHWR, "OH WR"),
            "taken_gdwr_enabled": (constants.DATA_FIELD_GDWR, "GD WR"),
            "taken_gndwr_enabled": (constants.DATA_FIELD_GNSWR, "GNS WR"),
            "taken_iwd_enabled": (constants.DATA_FIELD_IWD, "IWD"),
            "taken_wheel_enabled": (constants.DATA_FIELD_WHEEL, "WHEEL"),
        }

        settings = self.configuration.settings
        self.active_fields = [
            constants.DATA_FIELD_NAME,
            constants.DATA_FIELD_COUNT,
            constants.DATA_FIELD_COLORS,
        ]

        for attr, (field_key, label) in col_map.items():
            if getattr(settings, attr, False):
                cols.append(label)
                self.headers[label] = {"width": 60, "anchor": tkinter.CENTER}
                self.active_fields.append(field_key)

        # Always add GIHWR at the end
        cols.append("GIH WR")
        self.headers["GIH WR"] = {"width": 60, "anchor": tkinter.CENTER}
        self.active_fields.append(constants.DATA_FIELD_GIHWR)

        # Create Table
        self.table = ModernTreeview(
            self.table_container, columns=cols, headers_config=self.headers, height=20
        )
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _update_table(self):
        """Fetches data, filters it, and populates the table."""
        if not hasattr(self, "table"):
            return

        # 1. Clear Table
        for item in self.table.get_children():
            self.table.delete(item)

        # 2. Retrieve Cards
        taken_cards = self.draft.retrieve_taken_cards()  # List of card objects
        if not taken_cards:
            return

        # 3. Filter by Type
        active_types = []
        if self.vars["taken_type_creature_enabled"].get():
            active_types.append(constants.CARD_TYPE_CREATURE)
        if self.vars["taken_type_land_enabled"].get():
            active_types.append(constants.CARD_TYPE_LAND)
        if self.vars["taken_type_spells_enabled"].get():
            active_types.extend(
                [constants.CARD_TYPE_INSTANT, constants.CARD_TYPE_SORCERY]
            )
        if self.vars["taken_type_other_enabled"].get():
            active_types.extend(
                [
                    constants.CARD_TYPE_ARTIFACT,
                    constants.CARD_TYPE_ENCHANTMENT,
                    constants.CARD_TYPE_PLANESWALKER,
                ]
            )

        if not active_types:
            return

        # Filter logic:
        # deck_card_search(deck, search_colors, card_types, include_types, include_colorless, include_partial)
        # We want to match ANY of the types.
        # We are NOT filtering by color here (that's Deck Filter for stats),
        # we want to show all taken cards that match the types.

        # Helper to check types locally since deck_card_search is complex regarding colors
        filtered_cards = []
        for card in taken_cards:
            card_types = card.get(constants.DATA_FIELD_TYPES, [])
            if any(t in card_types for t in active_types):
                filtered_cards.append(card)

        # 4. Stack Cards (Duplicates -> Count)
        stacked_cards = stack_cards(filtered_cards)

        # 5. Process Stats (CardResult)
        # Determine stats filter color
        deck_filter_label = self.var_deck_filter.get()
        # Retrieve internal key for this label (Reverse lookup from draft manager)
        # Assuming draft manager has a method or we access the map
        deck_colors_map = self.draft.retrieve_color_win_rate(
            self.configuration.settings.filter_format
        )
        # map is { Label: Key }
        filter_key = deck_colors_map.get(
            deck_filter_label, constants.FILTER_OPTION_AUTO
        )

        # If Auto, calculate colors based on taken cards
        search_colors = [filter_key]
        if filter_key == constants.FILTER_OPTION_AUTO:
            from src.card_logic import filter_options

            metrics = self.draft.retrieve_set_metrics()
            # We use the FULL taken_cards list for auto-detection, not just the type-filtered one
            search_colors = filter_options(
                taken_cards, filter_key, metrics, self.configuration
            )

        processor = CardResult(
            self.draft.retrieve_set_metrics(),
            self.draft.retrieve_tier_data(),
            self.configuration,
            self.draft.current_pick,
        )

        # CardResult returns dicts with "results" list matching self.active_fields order
        processed_cards = processor.return_results(
            stacked_cards, search_colors, self.active_fields
        )

        # 6. Sort (Default by GIHWR descending)
        # GIHWR is always last in our list
        processed_cards.sort(
            key=lambda x: field_process_sort(x["results"][-1]), reverse=True
        )

        self.current_display_list = processed_cards

        # 7. Populate
        for idx, p_card in enumerate(processed_cards):
            # Row Color Tag
            from src.card_logic import row_color_tag

            tag = ""
            if self.configuration.settings.card_colors_enabled:
                # Need to check if it's a land for color logic
                # We need access to the card types which might not be in results
                # But CardResult usually passes through data if requested
                # Since we don't have types in active_fields, we can't check easily
                # However, CardResult returns a COPY of the card with 'results' added.
                # So we can access original fields!

                c_colors = p_card.get(constants.DATA_FIELD_MANA_COST, "")
                if constants.CARD_TYPE_LAND in p_card.get(
                    constants.DATA_FIELD_TYPES, []
                ):
                    c_colors = p_card.get(constants.DATA_FIELD_COLORS, [])

                # Convert string color to list if needed, or pass directly
                tag = row_color_tag(
                    list(c_colors) if isinstance(c_colors, str) else c_colors
                )
            else:
                tag = "bw_odd" if idx % 2 != 0 else "bw_even"

            self.table.insert("", "end", iid=idx, values=p_card["results"], tags=(tag,))

    def _copy_to_clipboard(self):
        """Copies the displayed list to clipboard in Arena format."""
        from src.card_logic import copy_deck

        # We need the stacked cards list.
        # We can reconstruct it from self.current_display_list
        # But copy_deck expects a list of dicts with 'name' and 'count'

        deck_export = []
        for p_card in self.current_display_list:
            # p_card is the dictionary returned by CardResult
            # It has "name", "count", etc. from the original stack_cards object
            deck_export.append(p_card)

        deck_str = copy_deck(deck_export, None)

        self.clipboard_clear()
        self.clipboard_append(deck_str)
        self.update()

    def _on_selection(self, event):
        """Displays tooltip."""
        selection = self.table.selection()
        if not selection:
            return

        idx = int(selection[0])
        if idx < len(self.current_display_list):
            card = self.current_display_list[idx]

            # Reconstruct Stats for tooltip
            stats = card.get(constants.DATA_FIELD_DECK_COLORS, {})
            images = card.get(constants.DATA_SECTION_IMAGES, [])

            CardToolTip(
                self.table,
                card[constants.DATA_FIELD_NAME],
                stats,
                images,
                self.configuration.features.images_enabled,
                1.0,
                None,
            )

    def _on_close(self):
        self.destroy()

    def _position_window(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 600, 50)
        self.wm_geometry(f"+{x}+{y}")
