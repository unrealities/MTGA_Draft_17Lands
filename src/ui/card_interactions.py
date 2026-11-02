"""
src/ui/card_interactions.py
Encapsulates all logic for clicking, right-clicking, generating tooltips,
and external routing (Compare, Scryfall, Clipboard) for MTG cards.
"""

import tkinter
import urllib.parse
from src import constants
from src.ui.styles import Theme
from src.ui.components import CardToolTip
from src.utils import open_file


class CardInteractionManager:
    def __init__(self, app_context):
        self.app = app_context

    def on_card_select(self, event, table, source_type):
        """Triggered when a user clicks a row in the Pack or Wheel tables."""
        if hasattr(event, "x") and hasattr(event, "y"):
            region = table.identify_region(event.x, event.y)
            if region not in ("tree", "cell"):
                return

        selection = table.selection()
        if not selection:
            return

        data_list = (
            self.app.current_pack_data
            if source_type == "pack"
            else self.app.current_missing_data
        )

        item = table.item(selection[0])
        card_name = item.get("text")

        if not card_name:
            item_vals = item["values"]
            try:
                name_idx = getattr(
                    table,
                    "active_fields",
                    self.app.dashboard.pack_manager.active_fields,
                ).index("name")
                raw_name = str(item_vals[name_idx])
                card_name = (
                    raw_name.replace("⭐ ", "")
                    .replace("*", "")
                    .strip()
                )
            except (ValueError, AttributeError, IndexError):
                return

        self.show_tooltip(card_name, table, data_list)

    def show_tooltip_from_advisor(self, card_name, widget):
        """Triggered when a user clicks a card in the Advisor Recommendations panel."""
        self.show_tooltip(
            card_name,
            widget,
            self.app.current_pack_data + self.app.current_missing_data,
        )

    def show_tooltip(self, card_name, widget, data_list):
        """Finds the card data and generates the Tooltip overlay."""
        found = next(
            (c for c in data_list if c.get(constants.DATA_FIELD_NAME) == card_name),
            None,
        )
        if found:
            current_scale = constants.UI_SIZE_DICT.get(
                self.app.configuration.settings.ui_size, 1.0
            )
            CardToolTip.create(
                widget,
                found,
                self.app.configuration.features.images_enabled,
                current_scale,
            )

    def on_card_context_menu(self, event, table, source_type):
        """Spawns a right-click context menu for quick actions on a card."""
        region = table.identify_region(event.x, event.y)
        if region == "heading":
            return

        selection = table.identify_row(event.y)
        if not selection:
            return

        table.selection_set(selection)

        data_list = (
            self.app.current_pack_data
            if source_type == "pack"
            else self.app.current_missing_data
        )

        item = table.item(selection)
        card_name = item.get("text")

        if not card_name:
            item_vals = item["values"]
            try:
                name_idx = table.active_fields.index("name")
                raw_name = str(item_vals[name_idx])
                card_name = (
                    raw_name.replace("⭐ ", "")
                    .replace("*", "")
                    .strip()
                )
            except ValueError:
                return

        found = next(
            (c for c in data_list if c.get(constants.DATA_FIELD_NAME) == card_name),
            None,
        )
        if not found:
            return

        menu = tkinter.Menu(self.app.root, tearoff=0)
        menu.add_command(
            label=f"🔍 Compare '{card_name}'",
            command=lambda: self.send_to_compare(found),
        )
        menu.add_command(
            label="📋 Copy Name",
            command=lambda: self.copy_text_to_clipboard(card_name),
        )
        menu.add_separator()
        menu.add_command(
            label="🌐 View on Scryfall", command=lambda: self.open_scryfall(card_name)
        )

        menu.post(event.x_root, event.y_root)

    def send_to_compare(self, card_data):
        if hasattr(self.app, "panel_compare"):
            self.app.panel_compare.add_external_card(card_data)
            self.app.notebook.select(self.app.panel_compare)
            self.app._ensure_tabs_visible()

    def copy_text_to_clipboard(self, text):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(text)

    def open_scryfall(self, card_name):
        url = f"https://scryfall.com/search?q={urllib.parse.quote(card_name)}"
        open_file(url)
