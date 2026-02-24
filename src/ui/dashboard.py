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
    CollapsibleFrame,
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
        f_left.grid(row=0, column=0, sticky="nsew", padx=(10, 15), pady=10)

        # 1. Pack Table
        self.table_pack_container = CollapsibleFrame(
            f_left, title="LIVE PACK: TACTICAL EVALUATION"
        )
        self.table_pack_container.pack(fill="both", expand=True, pady=(0, 15))

        self.pack_manager = DynamicTreeviewManager(
            self.table_pack_container.content_frame,
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
        self.table_missing_container = CollapsibleFrame(
            f_left, title="SEEN CARDS (WHEEL TRACKER)", expanded=False
        )
        self.table_missing_container.pack(fill="both", expand=True, pady=(0, 10))

        self.missing_manager = DynamicTreeviewManager(
            self.table_missing_container.content_frame,
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
        f_side = ttk.Frame(self, width=250)
        f_side.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        f_side.pack_propagate(False)

        self.signal_container = CollapsibleFrame(f_side, title="OPEN LANES")
        self.signal_container.pack(fill="x", pady=(0, 15))
        self.signal_meter = SignalMeter(self.signal_container.content_frame)
        self.signal_meter.pack(fill="x")

        self.curve_container = CollapsibleFrame(f_side, title="MANA CURVE")
        self.curve_container.pack(fill="x", pady=(0, 15))
        default_ideal = self.configuration.card_logic.deck_mid.distribution
        self.curve_plot = ManaCurvePlot(
            self.curve_container.content_frame, ideal_distribution=default_ideal
        )
        self.curve_plot.pack(fill="x")

        self.pool_container = CollapsibleFrame(f_side, title="POOL BALANCE")
        self.pool_container.pack(fill="x", pady=(0, 15))
        self.type_chart = TypePieChart(self.pool_container.content_frame)
        self.type_chart.pack(fill="x")

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
                from src.card_logic import (
                    row_color_tag,
                )  # Inline import to avoid circular dependency

                row_tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            display_name = name
            if rec:
                if rec.is_elite:
                    display_name = f"⭐ {name}"
                    row_tag = (
                        "elite_bomb"
                        if not self.configuration.settings.card_colors_enabled
                        else row_tag
                    )
                elif rec.archetype_fit == "High":
                    display_name = f"[+] {name}"
                    row_tag = (
                        "high_fit"
                        if not self.configuration.settings.card_colors_enabled
                        else row_tag
                    )

            row_values = []
            for field in tree.active_fields:
                if field == "name":
                    row_values.append(str(display_name))
                elif field == "value":
                    if rec:
                        row_values.append(f"{rec.contextual_score:.0f}")
                    else:
                        val = stats.get("gihwr", 0.0)
                        row_values.append(f"{val:.0f}" if val != 0.0 else "-")
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "count":
                    row_values.append(str(card.get("count", "-")))
                elif field == "wheel":
                    if rec and rec.wheel_chance > 0:
                        row_values.append(f"{rec.wheel_chance:.0f}%")
                    else:
                        row_values.append("-")
                elif "TIER" in field:
                    if tier_data and field in tier_data:
                        tier_obj = tier_data[field]
                        raw_name = card.get(constants.DATA_FIELD_NAME, "")
                        if raw_name in tier_obj.ratings:
                            row_values.append(tier_obj.ratings[raw_name].rating)
                        else:
                            row_values.append("NA")
                    else:
                        row_values.append("NA")
                else:
                    val = stats.get(field, 0.0)
                    if val == 0.0:
                        row_values.append("-")
                    else:
                        row_values.append(
                            f"{val:.1f}"
                            if field
                            in ["gihwr", "ohwr", "gpwr", "gnswr", "gdwr", "iwd"]
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
