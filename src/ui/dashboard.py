"""
src/ui/dashboard.py
The Live Draft Dashboard Component.
Compact layout with side-by-side Visuals.
"""

import tkinter
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from typing import List, Dict, Any, Optional

from src import constants
from src.card_logic import (
    field_process_sort,
    row_color_tag,
    CardResult,
    get_deck_metrics,
)
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, SignalMeter, ManaCurvePlot, TypePieChart


class DashboardFrame(tb.Frame):
    def __init__(self, parent, configuration, on_card_select):
        super().__init__(parent)
        self.configuration = configuration
        self.on_card_select = on_card_select

        self._tree_pack: Optional[ModernTreeview] = None
        self._tree_missing: Optional[ModernTreeview] = None

        self.signal_meter: Optional[SignalMeter] = None
        self.curve_plot: Optional[ManaCurvePlot] = None
        self.type_chart: Optional[TypePieChart] = None

        self._fields_pack: List[str] = [constants.DATA_FIELD_NAME]
        self._fields_missing: List[str] = [constants.DATA_FIELD_NAME]

        self._build_layout()

    def get_treeview(self, source_type: str = "pack") -> Optional[ModernTreeview]:
        return self._tree_pack if source_type == "pack" else self._tree_missing

    def _build_layout(self):
        # 3 Column Layout
        self.columnconfigure(0, weight=5)  # Tables (Wide)
        self.columnconfigure(1, weight=1)  # Signals (Narrow)
        self.columnconfigure(2, weight=2)  # Analytics (Medium)
        self.rowconfigure(0, weight=1)

        # --- COL 0: Tables ---
        f_left = tb.Frame(self)
        f_left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Pack Table
        self.table_pack = tb.Frame(f_left)
        self.table_pack.pack(fill="both", expand=True, pady=(0, 5))
        tb.Label(
            self.table_pack, text="PACK", bootstyle="secondary", font=(None, 8)
        ).pack(anchor="w")
        self._tree_pack, self._fields_pack = self._create_data_tree(
            self.table_pack, "pack"
        )
        self._tree_pack.pack(fill="both", expand=True)

        # Missing Table
        self.table_missing = tb.Frame(f_left)
        self.table_missing.pack(fill="both", expand=True)
        tb.Label(
            self.table_missing, text="SEEN", bootstyle="secondary", font=(None, 8)
        ).pack(anchor="w")
        self._tree_missing, self._fields_missing = self._create_data_tree(
            self.table_missing, "missing"
        )
        self._tree_missing.pack(fill="both", expand=True)

        # --- COL 1: Signals ---
        f_mid = tb.Frame(self)
        f_mid.grid(row=0, column=1, sticky="ns", padx=5)

        tb.Label(f_mid, text="SIGNALS", bootstyle="secondary", font=(None, 8)).pack(
            anchor="n"
        )
        self.signal_meter = SignalMeter(f_mid)
        self.signal_meter.pack(fill=BOTH, expand=True, pady=5)

        # --- COL 2: Analytics (Curve + Pie) ---
        f_right = tb.Frame(self)
        f_right.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        # Upper: Curve
        tb.Label(f_right, text="CURVE", bootstyle="secondary", font=(None, 8)).pack(
            anchor="w"
        )
        default_ideal = self.configuration.card_logic.deck_mid.distribution
        self.curve_plot = ManaCurvePlot(f_right, ideal_distribution=default_ideal)
        self.curve_plot.pack(fill=X, expand=True, pady=(0, 10))

        # Lower: Type Balance
        tb.Label(f_right, text="BALANCE", bootstyle="secondary", font=(None, 8)).pack(
            anchor="w"
        )
        self.type_chart = TypePieChart(f_right)
        self.type_chart.pack(fill=X, expand=True)

        # Legend for Pie Chart
        legend = tb.Frame(f_right)
        legend.pack(fill=X, pady=5)
        tb.Label(legend, text="● Crea", foreground=Theme.SUCCESS, font=(None, 7)).pack(
            side=LEFT, padx=2
        )
        tb.Label(legend, text="● Spell", foreground=Theme.ACCENT, font=(None, 7)).pack(
            side=LEFT, padx=2
        )
        tb.Label(
            legend, text="● Land", foreground=Theme.BG_TERTIARY, font=(None, 7)
        ).pack(side=LEFT, padx=2)

    def _create_data_tree(
        self, parent, source_type
    ) -> tuple[ModernTreeview, List[str]]:
        # [Same code as before]
        s = self.configuration.settings
        cols = ["Card"]
        hd = {"Card": {"width": 180, "anchor": tkinter.W}}
        fields = [constants.DATA_FIELD_NAME]

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
                hd[lbl] = {"width": 50, "anchor": tkinter.CENTER}
                fields.append(val)

        t = ModernTreeview(parent, columns=cols, headers_config=hd)
        t.bind("<<TreeviewSelect>>", lambda e: self.on_card_select(e, t, source_type))
        return t, fields

    def update_pack_data(
        self, cards, colors, metrics, tier_data, current_pick, source_type="pack"
    ):
        # [Same code as before]
        tree = self.get_treeview(source_type)
        fields = self._fields_pack if source_type == "pack" else self._fields_missing
        if not tree:
            return

        for item in tree.get_children():
            tree.delete(item)
        if not cards:
            return

        processor = CardResult(metrics, tier_data, self.configuration, current_pick)
        results = processor.return_results(cards, colors, fields)

        sort_idx = 1 if len(fields) > 1 else 0
        results.sort(
            key=lambda x: field_process_sort(x["results"][sort_idx]), reverse=True
        )

        for idx, item in enumerate(results):
            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            if self.configuration.settings.card_colors_enabled:
                tag = row_color_tag(item.get(constants.DATA_FIELD_MANA_COST, ""))
            display_values = [str(val) for val in item["results"]]
            tree.insert("", "end", values=display_values, tags=(tag,))

    def update_signals(self, scores: Dict[str, float]):
        if self.signal_meter:
            self.signal_meter.update_values(scores)

    def update_stats(self, distribution: List[int]):
        if self.curve_plot:
            self.curve_plot.update_curve(distribution)
            self.curve_plot.redraw()

    def update_deck_stats(self, taken_cards):
        """Called by App to update pie chart."""
        if self.type_chart:
            # We need to calculate creatures vs non-creatures here or pass it in
            # Assuming you pass the raw card list:
            creatures = 0
            non_creatures = 0
            lands = 0
            for c in taken_cards:
                types = c.get(constants.DATA_FIELD_TYPES, [])
                if constants.CARD_TYPE_LAND in types:
                    lands += 1
                elif constants.CARD_TYPE_CREATURE in types:
                    creatures += 1
                else:
                    non_creatures += 1
            self.type_chart.update_counts(creatures, non_creatures, lands)
