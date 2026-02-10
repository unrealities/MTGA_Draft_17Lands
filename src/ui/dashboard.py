"""
src/ui/dashboard.py
The Live Draft Dashboard Component.
Manages the 3-column grid containing:
- Pack Data & Missing Cards
- Signal Scores
- Pool CMC Curve
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.card_logic import field_process_sort, row_color_tag, CardResult
from src.ui.styles import Theme
from src.ui.components import ModernTreeview


class DashboardFrame(ttk.Frame):
    def __init__(self, parent, configuration, on_card_select):
        super().__init__(parent)
        self.configuration = configuration
        self.on_card_select = on_card_select  # Callback for ToolTips

        # Internal widget references
        self.table_pack = None
        self.table_missing = None
        self.table_signals = None
        self.table_stats = None
        self.active_fields = []

        self._build_layout()

    def _build_layout(self):
        """Constructs the stable Grid-based layout for the top dashboard."""
        self.columnconfigure(0, weight=4)  # Pack & Missing
        self.columnconfigure(1, weight=1)  # Signals
        self.columnconfigure(2, weight=1)  # Stats
        self.rowconfigure(0, weight=1)

        # 1. Left Col: Pack & Missing (Vertical Stack)
        f_left = ttk.Frame(self)
        f_left.grid(row=0, column=0, sticky="nsew", padx=4)

        self.table_pack = self._create_data_table(f_left, "LIVE PACK DATA", "pack")
        self.table_pack.pack(fill="both", expand=True, pady=(0, 10))

        self.table_missing = self._create_data_table(
            f_left, "CARDS NOT SEEN", "missing"
        )
        self.table_missing.pack(fill="both", expand=True)

        # 2. Mid Col: Signals
        f_mid = ttk.Frame(self)
        f_mid.grid(row=0, column=1, sticky="nsew", padx=4)
        ttk.Label(f_mid, text="OPEN SIGNALS", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 5)
        )

        self.table_signals = ModernTreeview(
            f_mid,
            columns=["Color", "Score"],
            headers_config={"Color": {"width": 100}, "Score": {"width": 50}},
        )
        self.table_signals.pack(fill="both", expand=True)

        # 3. Right Col: Stats
        f_right = ttk.Frame(self)
        f_right.grid(row=0, column=2, sticky="nsew", padx=4)
        ttk.Label(f_right, text="POOL CURVE", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 5)
        )

        self.table_stats = ModernTreeview(
            f_right,
            columns=["CMC", "Qty"],
            headers_config={"CMC": {"width": 80}, "Qty": {"width": 40}},
        )
        self.table_stats.pack(fill="both", expand=True)

    def _create_data_table(self, parent, title, source_type):
        """Creates a Treeview with columns mapped to user preferences."""
        container = ttk.Frame(parent)
        ttk.Label(container, text=title, style="Muted.TLabel").pack(
            anchor="w", pady=(0, 5)
        )

        s = self.configuration.settings
        cols = ["Card"]
        hd = {"Card": {"width": 200, "anchor": tkinter.W}}
        active_fields = [constants.DATA_FIELD_NAME]

        # Dynamic Columns 2-7
        config_cols = [
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

        for val in config_cols:
            if val != constants.DATA_FIELD_DISABLED:
                lbl = k2l.get(val, val.upper())
                cols.append(lbl)
                hd[lbl] = {"width": 60, "anchor": tkinter.CENTER}
                active_fields.append(val)

        # Save for data population
        if source_type == "pack":
            self.active_fields = active_fields

        t = ModernTreeview(container, columns=cols, headers_config=hd)
        t.pack(fill="both", expand=True)
        t.bind("<<TreeviewSelect>>", lambda e: self.on_card_select(e, t, source_type))
        return container

    def update_pack_data(
        self, cards, colors, metrics, tier_data, current_pick, source_type="pack"
    ):
        """Populates one of the data tables (Pack or Missing)."""
        container = self.table_pack if source_type == "pack" else self.table_missing
        table = list(container.children.values())[1]  # Get Treeview from Frame

        for item in table.get_children():
            table.delete(item)
        if not cards:
            return

        processor = CardResult(metrics, tier_data, self.configuration, current_pick)
        results = processor.return_results(cards, colors, self.active_fields)

        # Sort by first stat column
        sort_idx = 1 if len(self.active_fields) > 1 else 0
        results.sort(
            key=lambda x: field_process_sort(x["results"][sort_idx]), reverse=True
        )

        for idx, item in enumerate(results):
            if self.configuration.settings.card_colors_enabled:
                tag = row_color_tag(item.get(constants.DATA_FIELD_MANA_COST, ""))
            else:
                tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            table.insert("", "end", values=item["results"], tags=(tag,))

    def update_signals(self, scores: Dict[str, float]):
        """Populates the Signal table."""
        for item in self.table_signals.get_children():
            self.table_signals.delete(item)
        sorted_s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for c, v in sorted_s:
            name = constants.COLOR_NAMES_DICT.get(c, c)
            self.table_signals.insert("", "end", values=(name, f"{v:.1f}"))

    def update_stats(self, distribution: List[int]):
        """Populates the Pool Curve table."""
        for item in self.table_stats.get_children():
            self.table_stats.delete(item)
        for i, val in enumerate(distribution):
            self.table_stats.insert("", "end", values=(f"{i} CMC", val))
