"""
src/ui/windows/suggest_deck.py

This module implements the Suggested Decks window.
It analyzes the user's taken cards and proposes viable deck builds (Aggro, Midrange, Control)
based on color combinations and win rates.
"""

import tkinter
from tkinter import ttk
from typing import Dict, Any

from src import constants
from src.configuration import Configuration
from src.card_logic import suggest_deck, copy_deck, get_card_colors
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, identify_safe_coordinates, CardToolTip


class SuggestDeckWindow(tkinter.Toplevel):
    """
    Window for displaying deck suggestions generated from the taken card pool.
    """

    def __init__(self, parent, draft_manager, configuration: Configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.title("Suggested Decks")
        self.resizable(False, True)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)
        self.attributes("-topmost", True)

        # State
        self.suggestions = {}
        self.current_deck_list = []

        # Build UI
        self._build_ui()

        # Initial Calculation
        self._calculate_suggestions()

        # Position
        self.update_idletasks()
        self._position_window(parent)

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # --- Controls Area ---
        controls_frame = ttk.Frame(container, style="Card.TFrame", padding=10)
        controls_frame.pack(fill="x", pady=(0, 10))

        # Deck Selection Dropdown
        ttk.Label(controls_frame, text="Archetype:").pack(side="left")

        self.var_deck_selection = tkinter.StringVar()
        self.om_deck_selection = ttk.OptionMenu(
            controls_frame,
            self.var_deck_selection,
            "",  # Default value
            style="TMenubutton",
            command=self._on_deck_change,
        )
        self.om_deck_selection.pack(side="left", fill="x", expand=True, padx=10)

        # Copy Button
        ttk.Button(
            controls_frame, text="Copy to Clipboard", command=self._copy_to_clipboard
        ).pack(side="right")

        # --- Table Area ---
        columns = ["Card", "Count", "Color", "Cost", "Type"]
        headers = {
            "Card": {"width": 200, "anchor": tkinter.W},
            "Count": {"width": 50, "anchor": tkinter.CENTER},
            "Color": {"width": 50, "anchor": tkinter.CENTER},
            "Cost": {"width": 50, "anchor": tkinter.CENTER},
            "Type": {"width": 100, "anchor": tkinter.W},
        }

        self.table = ModernTreeview(
            container, columns=columns, headers_config=headers, height=20
        )
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _calculate_suggestions(self):
        """Generates deck suggestions using card_logic."""
        try:
            taken_cards = self.draft.retrieve_taken_cards()
            metrics = self.draft.retrieve_set_metrics()

            # This returns a dict: { "WB": { "type": "Mid", "rating": 1234, "deck_cards": [...], ... } }
            raw_suggestions = suggest_deck(taken_cards, metrics, self.configuration)

            if not raw_suggestions:
                self._update_dropdown(["No viable decks found"])
                return

            # Format for dropdown: "WB Mid (Rating: 1357)"
            self.suggestions = {}
            dropdown_options = []

            # Sort suggestions by rating desc
            sorted_keys = sorted(
                raw_suggestions.keys(),
                key=lambda k: raw_suggestions[k]["rating"],
                reverse=True,
            )

            for key in sorted_keys:
                data = raw_suggestions[key]
                label = f"{key} {data['type']} (Rating: {data['rating']})"
                self.suggestions[label] = data
                dropdown_options.append(label)

            self._update_dropdown(dropdown_options)

            # Select best deck by default
            if dropdown_options:
                self.var_deck_selection.set(dropdown_options[0])
                self._display_deck(dropdown_options[0])

        except Exception as e:
            print(f"Error calculating suggestions: {e}")
            self._update_dropdown(["Error generating decks"])

    def _update_dropdown(self, options):
        """Refreshes the OptionMenu items."""
        menu = self.om_deck_selection["menu"]
        menu.delete(0, "end")

        for opt in options:
            menu.add_command(
                label=opt,
                command=lambda val=opt: [
                    self.var_deck_selection.set(val),
                    self._on_deck_change(val),
                ],
            )

        if options:
            self.var_deck_selection.set(options[0])

    def _on_deck_change(self, value):
        if value in self.suggestions:
            self._display_deck(value)

    def _display_deck(self, label):
        """Populates the table with the selected deck's cards."""
        # 1. Clear Table
        for item in self.table.get_children():
            self.table.delete(item)

        data = self.suggestions.get(label)
        if not data:
            return

        self.current_deck_list = data["deck_cards"]
        # Sort by CMC for display
        self.current_deck_list.sort(
            key=lambda x: (
                x.get(constants.DATA_FIELD_CMC, 0),
                x.get(constants.DATA_FIELD_NAME, ""),
            )
        )

        # 2. Populate
        for idx, card in enumerate(self.current_deck_list):
            name = card.get(constants.DATA_FIELD_NAME, "Unknown")
            count = card.get(constants.DATA_FIELD_COUNT, 1)
            cmc = card.get(constants.DATA_FIELD_CMC, 0)

            # Types formatted as string
            types_list = card.get(constants.DATA_FIELD_TYPES, [])
            types_str = " ".join(types_list)

            # Colors logic
            # Use 'colors' field if available (Lands), otherwise calculate from Mana Cost
            if (
                constants.CARD_TYPE_LAND in types_list
                or self.configuration.settings.color_identity_enabled
            ):
                colors = "".join(card.get(constants.DATA_FIELD_COLORS, []))
            else:
                mana_cost = card.get(constants.DATA_FIELD_MANA_COST, "")
                colors = "".join(list(get_card_colors(mana_cost).keys()))

            # Row Tag
            from src.card_logic import row_color_tag

            tag = ""
            if self.configuration.settings.card_colors_enabled:
                # We pass 'colors' string or dict depending on what row_color_tag expects
                # row_color_tag expects a dict of colors usually, or list
                # Let's convert string "WB" to ["W", "B"]
                color_list = list(colors)
                tag = row_color_tag(color_list)
            else:
                tag = "bw_odd" if idx % 2 != 0 else "bw_even"

            self.table.insert(
                "",
                "end",
                iid=idx,
                values=(name, count, colors, cmc, types_str),
                tags=(tag,),
            )

    def _copy_to_clipboard(self):
        """Formats the current deck for Arena and copies to clipboard."""
        selection = self.var_deck_selection.get()
        if selection in self.suggestions:
            deck_data = self.suggestions[selection]
            deck_str = copy_deck(
                deck_data["deck_cards"], deck_data.get("sideboard_cards")
            )

            self.clipboard_clear()
            self.clipboard_append(deck_str)
            self.update()

    def _on_selection(self, event):
        """Displays tooltip for selected card."""
        selection = self.table.selection()
        if not selection:
            return

        idx = int(selection[0])
        if idx < len(self.current_deck_list):
            card = self.current_deck_list[idx]

            # Prepare data for tooltip
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

    def _position_window(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 400, 50)
        self.wm_geometry(f"+{x}+{y}")
