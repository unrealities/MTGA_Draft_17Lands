"""
src/ui/dashboard.py
The Professional Live Draft Dashboard.
Supports dynamic columns for both Pack and Missing card tables.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any, Optional

from src import constants
from src.card_logic import field_process_sort, row_color_tag
from src.ui.styles import Theme
from src.ui.components import (
    ModernTreeview,
    DynamicTreeviewManager,
    SignalMeter,
    ManaCurvePlot,
    TypePieChart,
)
from src.advisor.schema import Recommendation


class DashboardFrame(ttk.Frame):
    def __init__(self, parent, configuration, on_card_select, on_reconfigure_ui):
        super().__init__(parent)
        self.configuration = configuration
        self.on_card_select = on_card_select
        self.on_reconfigure_ui = on_reconfigure_ui

        # Managers and Components
        self.pack_manager: Optional[DynamicTreeviewManager] = None
        self.missing_manager: Optional[DynamicTreeviewManager] = None

        self.signal_meter: Optional[SignalMeter] = None
        self.curve_plot: Optional[ManaCurvePlot] = None
        self.type_chart: Optional[TypePieChart] = None

        self._build_layout()

    def get_treeview(self, source_type: str = "pack") -> Optional[ModernTreeview]:
        if source_type == "pack":
            return self.pack_manager.tree if self.pack_manager else None
        return self.missing_manager.tree if self.missing_manager else None

    def _build_layout(self):
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- LEFT: Tables ---
        f_left = ttk.Frame(self)
        f_left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # 1. Pack Table
        self.table_pack_container = ttk.Frame(f_left)
        self.table_pack_container.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(
            self.table_pack_container,
            text="LIVE PACK: TACTICAL EVALUATION",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 5))

        self.pack_manager = DynamicTreeviewManager(
            self.table_pack_container,
            view_id="pack_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
        )
        self.pack_manager.pack(fill="both", expand=True)
        self.pack_manager.tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.on_card_select(e, self.pack_manager.tree, "pack"),
        )

        # 2. Missing Table
        self.table_missing_container = ttk.Frame(f_left)
        self.table_missing_container.pack(fill="both", expand=True)
        ttk.Label(
            self.table_missing_container,
            text="SEEN CARDS (WHEEL TRACKER)",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 5))

        self.missing_manager = DynamicTreeviewManager(
            self.table_missing_container,
            view_id="missing_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
        )
        self.missing_manager.pack(fill="both", expand=True)
        self.missing_manager.tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.on_card_select(e, self.missing_manager.tree, "missing"),
        )

        # --- RIGHT: Sidebar ---
        f_side = ttk.Frame(self, width=220)
        f_side.grid(row=0, column=1, sticky="nsew", padx=5)
        f_side.pack_propagate(False)

        ttk.Label(f_side, text="OPEN LANES", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        self.signal_meter = SignalMeter(f_side)
        self.signal_meter.pack(fill="x", pady=(0, 15))

        ttk.Label(f_side, text="MANA CURVE", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        default_ideal = self.configuration.card_logic.deck_mid.distribution
        self.curve_plot = ManaCurvePlot(f_side, ideal_distribution=default_ideal)
        self.curve_plot.pack(fill="x", pady=(0, 15))

        ttk.Label(f_side, text="POOL BALANCE", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        self.type_chart = TypePieChart(f_side)
        self.type_chart.pack(fill="x")

        self._configure_special_tags()

    def _configure_special_tags(self):
        """Adds elite highlighting to the trees."""
        for manager in [self.pack_manager, self.missing_manager]:
            if manager and manager.tree:
                manager.tree.tag_configure(
                    "elite_bomb", background="#4a3f1d", foreground="#ffd700"
                )
                manager.tree.tag_configure(
                    "high_fit", background="#1d3a4a", foreground="#00d4ff"
                )

    def update_pack_data(
        self,
        cards,
        colors,
        metrics,
        tier_data,
        current_pick,
        source_type="pack",
        recommendations=None,
    ):
        tree = self.get_treeview(source_type)
        # Ensure we have a valid widget and it has its configuration injected
        if not tree or not hasattr(tree, "active_fields"):
            return

        # Sync the tags every time we rebuild the underlying tree
        self._configure_special_tags()

        for item in tree.get_children():
            tree.delete(item)
        if not cards:
            return

        rec_map = {r.card_name: r for r in (recommendations or [])}
        active_filter = colors[0] if colors else "All Decks"
        processed_rows = []

        for card in cards:
            name = card.get(constants.DATA_FIELD_NAME, "Unknown")
            stats = card.get("deck_colors", {}).get(active_filter, {})
            rec = rec_map.get(name)

            row_tag = "bw_odd" if len(processed_rows) % 2 == 0 else "bw_even"
            if self.configuration.settings.card_colors_enabled:
                row_tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            display_name = name
            if rec:
                if rec.is_elite:
                    display_name = f"⭐ {name}"
                    row_tag = "elite_bomb"
                elif rec.archetype_fit == "High":
                    display_name = f"[+] {name}"
                    row_tag = "high_fit"

            row_values = []
            for field in tree.active_fields:
                if field == "name":
                    row_values.append(str(display_name))
                elif field == "value":
                    val = rec.contextual_score if rec else stats.get("gihwr", 0.0)
                    row_values.append(f"{val:.0f}")
                elif field == "colors":
                    row_values.append(card.get("colors", ""))
                else:
                    val = stats.get(field, 0.0)
                    row_values.append(
                        f"{val:.1f}"
                        if field in ["gihwr", "ohwr", "gpwr", "iwd"]
                        else str(val)
                    )

            processed_rows.append(
                {
                    "vals": row_values,
                    "tag": row_tag,
                    "sort_key": (
                        rec.contextual_score if rec else stats.get("gihwr", 0.0)
                    ),
                }
            )

        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)
        for row in processed_rows:
            tree.insert("", "end", values=row["vals"], tags=(row["tag"],))

    def update_signals(self, scores: Dict[str, float]):
        if self.signal_meter:
            self.signal_meter.update_values(scores)

    def update_stats(self, distribution: List[int]):
        if self.curve_plot:
            self.curve_plot.update_curve(distribution)
            self.curve_plot.redraw()

    def update_deck_balance(self, taken_cards):
        if not self.type_chart:
            return
        c, n, l = 0, 0, 0
        for card in taken_cards:
            types = card.get(constants.DATA_FIELD_TYPES, [])
            if constants.CARD_TYPE_LAND in types:
                l += 1
            elif constants.CARD_TYPE_CREATURE in types:
                c += 1
            else:
                n += 1
        self.type_chart.update_counts(c, n, l)
