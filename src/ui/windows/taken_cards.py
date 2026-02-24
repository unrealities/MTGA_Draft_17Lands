"""
src/ui/windows/taken_cards.py
Professional Card Pool Viewer.
Supports both List View (Table) and Visual View (Mana Curve Stacks).
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.card_logic import stack_cards, copy_deck, row_color_tag
from src.ui.styles import Theme
from src.ui.components import (
    DynamicTreeviewManager,
    CardToolTip,
    ScrolledFrame,
    CardPile,
)


class TakenCardsPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.current_display_list = []
        self.view_mode = "list"  # "list" or "visual"

        # UI State for Checkbuttons
        self.vars = {}

        self._build_ui()
        # Trigger first load manually
        self.refresh()

    @property
    def table(self) -> ttk.Treeview:
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    def refresh(self):
        # 1. Get Data
        raw_pool = self.draft.retrieve_taken_cards()
        if not raw_pool:
            self.current_display_list = []
        else:
            # 2. Filter
            active_types = []
            if self.vars["creature"].get():
                active_types.append(constants.CARD_TYPE_CREATURE)
            if self.vars["land"].get():
                active_types.append(constants.CARD_TYPE_LAND)
            if self.vars["spell"].get():
                active_types.extend(
                    [constants.CARD_TYPE_INSTANT, constants.CARD_TYPE_SORCERY]
                )
            if self.vars["other"].get():
                active_types.extend(
                    [
                        constants.CARD_TYPE_ARTIFACT,
                        constants.CARD_TYPE_ENCHANTMENT,
                        constants.CARD_TYPE_PLANESWALKER,
                    ]
                )

            filtered = []
            for c in raw_pool:
                types = c.get(constants.DATA_FIELD_TYPES, [])

                if not types and self.vars["other"].get():
                    filtered.append(c)
                    continue

                # Standard filtering
                if any(t in types for t in active_types):
                    filtered.append(c)

            self.current_display_list = stack_cards(filtered)

        # 3. Render based on mode
        if self.view_mode == "list":
            self._update_table_view()
        else:
            self._render_visual_view()

    def _build_ui(self):
        # --- Control Bar ---
        self.filter_frame = ttk.Frame(self, style="Card.TFrame", padding=5)
        self.filter_frame.pack(fill="x", pady=(0, 5))

        type_grp = ttk.Frame(self.filter_frame, style="Card.TFrame")
        type_grp.pack(side="left", padx=5)

        ttk.Label(
            type_grp,
            text="FILTER:",
            font=(Theme.FONT_FAMILY, 8, "bold"),
            foreground=Theme.ACCENT,
        ).pack(side="left", padx=5)

        self.vars = {}
        for lbl, key in [
            ("Creatures", "creature"),
            ("Lands", "land"),
            ("Spells", "spell"),
            ("Other", "other"),
        ]:
            var = tkinter.IntVar(value=1)
            self.vars[key] = var
            ttk.Checkbutton(
                type_grp, text=lbl, variable=var, command=self.refresh
            ).pack(side="left", padx=3)

        # View Toggle & Export
        btn_frame = ttk.Frame(self.filter_frame, style="Card.TFrame")
        btn_frame.pack(side="right")

        self.btn_view = ttk.Button(
            btn_frame,
            text="Switch to Visual View",
            command=self._toggle_view,
            bootstyle="info-outline",
        )
        self.btn_view.pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Export Pool", command=self._copy_to_clipboard).pack(
            side="left", padx=5
        )

        # --- Content Container ---
        self.content_area = ttk.Frame(self)
        self.content_area.pack(fill="both", expand=True)

        # 1. Table View (Default)
        self.table_manager = DynamicTreeviewManager(
            self.content_area,
            view_id="taken_table",
            configuration=self.configuration,
            on_update_callback=lambda: None,  # We handle updates manually via refresh()
        )
        self.table_manager.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

        # 2. Visual View (Hidden initially)
        self.visual_scroller = ScrolledFrame(self.content_area)
        # We don't pack it yet

    def _toggle_view(self):
        if self.view_mode == "list":
            self.view_mode = "visual"
            self.btn_view.config(text="Switch to List View")
            self.table_manager.pack_forget()
            self.visual_scroller.pack(fill="both", expand=True)
            self._render_visual_view()
        else:
            self.view_mode = "list"
            self.btn_view.config(text="Switch to Visual View")
            self.visual_scroller.pack_forget()
            self.table_manager.pack(fill="both", expand=True)
            self._update_table_view()

    def _update_table_view(self):
        t = self.table
        if t is None:
            return

        for item in t.get_children():
            t.delete(item)

        for idx, card in enumerate(self.current_display_list):
            row_values = []
            for field in self.table_manager.active_fields:
                if field == "name":
                    row_values.append(card.get("name", "Unknown"))
                elif field == "count":
                    row_values.append(card.get("count", 1))
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                else:
                    val = (
                        card.get("deck_colors", {}).get("All Decks", {}).get(field, 0.0)
                    )
                    if val == 0.0 or val == "-":
                        row_values.append("-")
                    else:
                        row_values.append(
                            f"{val:.1f}" if isinstance(val, float) else str(val)
                        )

            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            if int(self.configuration.settings.card_colors_enabled):
                tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            t.insert("", "end", values=row_values, tags=(tag,))

    def _render_visual_view(self):
        # Clear existing piles
        for widget in self.visual_scroller.scrollable_frame.winfo_children():
            widget.destroy()

        # Buckets: Lands, 1, 2, 3, 4, 5, 6+
        buckets = {
            "Lands": [],
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
            "6+": [],
            "Unknown": [],  # Bucket for recovered cards with no CMC data
        }

        for card in self.current_display_list:
            if constants.CARD_TYPE_LAND in card.get(constants.DATA_FIELD_TYPES, []):
                buckets["Lands"].append(card)
                continue

            # Handle unknown CMC safely
            try:
                cmc = int(card.get(constants.DATA_FIELD_CMC, 0))
                if cmc == 0 and not card.get(constants.DATA_FIELD_TYPES):
                    buckets["Unknown"].append(card)
                    continue
            except:
                buckets["Unknown"].append(card)
                continue

            if cmc <= 1:
                buckets["1"].append(card)
            elif cmc == 2:
                buckets["2"].append(card)
            elif cmc == 3:
                buckets["3"].append(card)
            elif cmc == 4:
                buckets["4"].append(card)
            elif cmc == 5:
                buckets["5"].append(card)
            else:
                buckets["6+"].append(card)

        # Render Piles
        keys = ["Lands", "1", "2", "3", "4", "5", "6+", "Unknown"]
        for key in keys:
            card_list = buckets.get(key, [])
            if not card_list and key not in ["Lands", "Unknown"]:
                continue  # Skip empty CMC columns to save space
            if not card_list:
                continue

            # Create Column
            pile_frame = ttk.Frame(self.visual_scroller.scrollable_frame)
            pile_frame.pack(side="left", fill="y", padx=5, pady=5, anchor="n")

            # Use the CardPile component
            pile = CardPile(pile_frame, title=f"CMC {key}", app_instance=self)
            pile.pack(fill="both", expand=True)

            # Sort by Color then Name
            card_list.sort(key=lambda x: (x.get("colors", []), x.get("name", "")))

            for card in card_list:
                pile.add_card(card)

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.current_display_list, None))

    def _on_selection(self, event):
        sel = self.table.selection()
        if not sel:
            return

        item_vals = self.table.item(sel[0])["values"]
        try:
            name_idx = self.table_manager.active_fields.index("name")
            card_name = (
                str(item_vals[name_idx])
                .replace("⭐ ", "")
                .replace("[+] ", "")
                .replace("*", "")
                .strip()
            )
        except ValueError:
            return

        card = next(
            (c for c in self.current_display_list if c.get("name") == card_name), None
        )
        if card:
            CardToolTip(
                self.table,
                card.get("name", ""),
                card.get("deck_colors", {}),
                card.get("image", []),
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
            )
