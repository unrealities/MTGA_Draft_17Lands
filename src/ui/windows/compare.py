"""
src/ui/windows/compare.py
Professional Card Comparison Workspace.
"""

import tkinter
from tkinter import ttk
from src import constants
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, AutocompleteEntry, CardToolTip


class ComparePanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration
        self.compare_list = []
        self._build_ui()
        self.refresh()

    @property
    def table(self) -> ttk.Treeview:
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    def refresh(self):
        card_map = self.draft.set_data.get_card_ratings() or {}
        self.entry_card.set_completion_list(
            [v.get("name", "") for v in card_map.values()]
        )
        self._update_content()

    def _build_ui(self):
        bar = ttk.Frame(self, style="Card.TFrame", padding=5)
        bar.pack(fill="x", pady=(0, 5))

        ttk.Label(
            bar,
            text="SEARCH:",
            font=(Theme.FONT_FAMILY, 8, "bold"),
            background=Theme.BG_SECONDARY,
        ).pack(side="left", padx=5)
        self.entry_card = AutocompleteEntry(bar, completion_list=[], width=40)
        self.entry_card.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_card.bind("<Return>", self._add_card)

        ttk.Button(bar, text="Add", width=8, command=self._add_card).pack(
            side="left", padx=2
        )
        ttk.Button(bar, text="Clear", command=self._clear_list).pack(
            side="right", padx=5
        )

        self.table_manager = DynamicTreeviewManager(
            self,
            view_id="compare_table",
            configuration=self.configuration,
            on_update_callback=self._update_content,
        )
        self.table_manager.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _add_card(self, event=None):
        typed = self.entry_card.get().strip().lower()
        if not typed:
            return
        card_map = self.draft.set_data.get_card_ratings() or {}
        found = next(
            (d for d in card_map.values() if d.get("name", "").lower() == typed), None
        )
        if found and found not in self.compare_list:
            self.compare_list.append(found)
            self._update_content()
            self.entry_card.delete(0, tkinter.END)

    def _clear_list(self):
        self.compare_list.clear()
        self._update_content()

    def _update_content(self):
        t = self.table
        if t is None:
            return
        for item in t.get_children():
            t.delete(item)
        for idx, card in enumerate(self.compare_list):
            row = []
            for field in self.table_manager.active_fields:
                if field == "name":
                    row.append(card.get("name", ""))
                elif field == "colors":
                    row.append("".join(card.get("colors", [])))
                else:
                    val = (
                        card.get("deck_colors", {}).get("All Decks", {}).get(field, "-")
                    )
                    row.append(f"{val:.1f}" if isinstance(val, float) else str(val))
            t.insert(
                "", "end", values=row, tags=("bw_odd" if idx % 2 == 0 else "bw_even",)
            )

    def _on_selection(self, event):
        sel = self.table.selection()
        if not sel:
            return
        idx = self.table.index(sel[0])
        if idx < len(self.compare_list):
            card = self.compare_list[idx]
            CardToolTip(
                self.table,
                card.get("name", ""),
                card.get("deck_colors", {}),
                card.get("image", []),
                self.configuration.features.images_enabled,
                1.0,
            )
