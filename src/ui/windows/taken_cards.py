"""
src/ui/windows/taken_cards.py
Professional Card Pool Viewer.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.card_logic import stack_cards, copy_deck
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip


class TakenCardsPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.current_display_list = []
        self.active_filters = {
            "creature": True,
            "land": True,
            "spell": True,
            "other": True,
        }

        self._build_ui()
        # Trigger first load manually after self.table_manager is assigned
        self.refresh()

    @property
    def table(self) -> ttk.Treeview:
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    def refresh(self):
        self._update_table()

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
            background=Theme.BG_SECONDARY,
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
                type_grp, text=lbl, variable=var, command=self._update_table
            ).pack(side="left", padx=3)

        ttk.Button(
            self.filter_frame, text="Export Pool", command=self._copy_to_clipboard
        ).pack(side="right", padx=5)

        # --- Dynamic Table ---
        self.table_container = ttk.Frame(self)
        self.table_container.pack(fill="both", expand=True)

        self.table_manager = DynamicTreeviewManager(
            self.table_container,
            view_id="taken_table",
            configuration=self.configuration,
            on_update_callback=self._update_table,
        )
        self.table_manager.pack(fill="both", expand=True)
        # Initial binding - Manager handles re-binding on rebuild
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _update_table(self):
        # SAFETY GUARD: Ensure table exists and manager is ready
        t = self.table
        if t is None:
            return

        for item in t.get_children():
            t.delete(item)

        raw_pool = self.draft.retrieve_taken_cards()
        if not raw_pool:
            return

        # Filtering
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

        filtered = [
            c
            for c in raw_pool
            if any(t in c.get(constants.DATA_FIELD_TYPES, []) for t in active_types)
        ]
        self.current_display_list = stack_cards(filtered)

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
                        card.get("deck_colors", {}).get("All Decks", {}).get(field, "-")
                    )
                    row_values.append(
                        f"{val:.1f}" if isinstance(val, float) else str(val)
                    )

            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            t.insert("", "end", values=row_values, tags=(tag,))

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.current_display_list, None))

    def _on_selection(self, event):
        sel = self.table.selection()
        if not sel:
            return
        idx = self.table.index(sel[0])
        if idx < len(self.current_display_list):
            card = self.current_display_list[idx]
            CardToolTip(
                self.table,
                card.get("name", ""),
                card.get("deck_colors", {}),
                card.get("image", []),
                self.configuration.features.images_enabled,
                1.0,
            )
