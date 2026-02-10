"""
src/ui/windows/taken_cards.py
Displays card pool with high-density filtering.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.configuration import Configuration
from src.card_logic import CardResult, stack_cards, field_process_sort
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, CardToolTip


class TakenCardsPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration: Configuration):
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
        # Lifecycle: Bootstrap the data immediately
        self.refresh()

    def refresh(self):
        """Public entry point to rebuild columns and data rows."""
        self._rebuild_columns()
        self._update_table()

    def _build_ui(self):
        self.filter_frame = ttk.Frame(self, style="Card.TFrame", padding=5)
        self.filter_frame.pack(fill="x", pady=(0, 5))
        type_grp = ttk.Frame(self.filter_frame, style="Card.TFrame")
        type_grp.pack(side="left", padx=5)
        ttk.Label(
            type_grp,
            text="FILTER:",
            style="SubHeader.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(side="left", padx=5)

        self.vars = {}
        filter_configs = [
            ("Creatures", "creature"),
            ("Lands", "land"),
            ("Spells", "spell"),
            ("Other", "other"),
        ]
        for lbl, key in filter_configs:
            var = tkinter.IntVar(value=1)
            self.vars[key] = var
            ttk.Checkbutton(
                type_grp,
                text=lbl,
                variable=var,
                command=lambda k=key, v=var: self._on_filter_toggle(k, v),
            ).pack(side="left", padx=3)

        btn_grp = ttk.Frame(self.filter_frame, style="Card.TFrame")
        btn_grp.pack(side="right", padx=5)
        ttk.Button(btn_grp, text="Export Pool", command=self._copy_to_clipboard).pack(
            side="right", padx=5
        )

        self.table_container = ttk.Frame(self)
        self.table_container.pack(fill="both", expand=True)

    def _on_filter_toggle(self, key, var):
        self.active_filters[key] = bool(var.get())
        self._update_table()

    def _rebuild_columns(self):
        s = self.configuration.settings
        cols = ["Card", "#", "Colors"]
        hd = {
            "Card": {"width": 200, "anchor": tkinter.W},
            "#": {"width": 40},
            "Colors": {"width": 60},
        }
        self.active_fields = [
            constants.DATA_FIELD_NAME,
            constants.DATA_FIELD_COUNT,
            constants.DATA_FIELD_COLORS,
        ]

        config = [
            s.column_2,
            s.column_3,
            s.column_4,
            s.column_5,
            s.column_6,
            s.column_7,
        ]
        k2l = {
            v: k.split(":")[0] for k, v in constants.COLUMNS_OPTIONS_EXTRA_DICT.items()
        }
        for val in config:
            if val != constants.DATA_FIELD_DISABLED:
                lbl = k2l.get(val, val.upper())
                cols.append(lbl)
                hd[lbl] = {"width": 65}
                self.active_fields.append(val)

        if constants.DATA_FIELD_GIHWR not in self.active_fields:
            cols.append("GIH WR")
            hd["GIH WR"] = {"width": 70}
            self.active_fields.append(constants.DATA_FIELD_GIHWR)

        if not hasattr(self, "table") or list(self.table["columns"]) != cols:
            for w in self.table_container.winfo_children():
                w.destroy()
            self.table = ModernTreeview(
                self.table_container, columns=cols, headers_config=hd
            )
            self.table.pack(fill="both", expand=True)
            self.table.bind("<<TreeviewSelect>>", self._on_selection)

    def _update_table(self):
        if not hasattr(self, "table"):
            return
        for item in self.table.get_children():
            self.table.delete(item)
        raw = self.draft.retrieve_taken_cards()
        if not raw:
            return

        active_types = []
        if self.active_filters["creature"]:
            active_types.append(constants.CARD_TYPE_CREATURE)
        if self.active_filters["land"]:
            active_types.append(constants.CARD_TYPE_LAND)
        if self.active_filters["spell"]:
            active_types.extend(
                [constants.CARD_TYPE_INSTANT, constants.CARD_TYPE_SORCERY]
            )
        if self.active_filters["other"]:
            active_types.extend(
                [
                    constants.CARD_TYPE_ARTIFACT,
                    constants.CARD_TYPE_ENCHANTMENT,
                    constants.CARD_TYPE_PLANESWALKER,
                ]
            )

        filtered = [
            c
            for c in raw
            if any(t in c.get(constants.DATA_FIELD_TYPES, []) for t in active_types)
        ]
        stacked = stack_cards(filtered)

        from src.card_logic import filter_options

        metrics = self.draft.retrieve_set_metrics()
        colors = filter_options(
            raw, self.configuration.settings.deck_filter, metrics, self.configuration
        )
        processed = CardResult(
            metrics, self.draft.retrieve_tier_data(), self.configuration, 1
        ).return_results(stacked, colors, self.active_fields)
        processed.sort(key=lambda x: str(x["results"][0]))
        self.current_display_list = processed

        from src.card_logic import row_color_tag

        for i, p in enumerate(processed):
            tag = (
                row_color_tag(p.get(constants.DATA_FIELD_MANA_COST, ""))
                if self.configuration.settings.card_colors_enabled
                else ("bw_odd" if i % 2 == 0 else "bw_even")
            )
            self.table.insert("", "end", iid=i, values=p["results"], tags=(tag,))

    def _copy_to_clipboard(self):
        from src.card_logic import copy_deck

        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.current_display_list, None))

    def _on_selection(self, event):
        sel = self.table.selection()
        if not sel:
            return
        card = self.current_display_list[int(sel[0])]
        CardToolTip(
            self.table,
            card[constants.DATA_FIELD_NAME],
            card.get(constants.DATA_FIELD_DECK_COLORS, {}),
            card.get(constants.DATA_SECTION_IMAGES, []),
            self.configuration.features.images_enabled,
            1.0,
        )
