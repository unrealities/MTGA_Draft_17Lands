"""
src/ui/dashboard.py
The Professional Live Draft Dashboard.
Supports dynamic grid layouts that auto-adjust based on pack/wheel card counts.
Features built-in state management for onboarding UX and waiting screens.
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
from src.ui.advisor_view import AdvisorPanel
from src.card_logic import format_win_rate


class DashboardFrame(ttk.Frame):
    def __init__(self, parent, configuration, on_card_select, on_reconfigure_ui):
        super().__init__(parent)
        self.configuration = configuration
        self.on_card_select = on_card_select
        self.on_reconfigure_ui = on_reconfigure_ui

        self.pack_manager: Optional[DynamicTreeviewManager] = None
        self.missing_manager: Optional[DynamicTreeviewManager] = None

        self.signal_meter: Optional[SignalMeter] = None
        self.curve_plot: Optional[ManaCurvePlot] = None
        self.type_chart: Optional[TypePieChart] = None

        # Track counts for dynamic vertical splitting and State Evaluation
        self._pack_count = 0
        self._missing_count = 0
        self._taken_count = 0

        self._build_layout()

    def get_treeview(self, source_type: str = "pack") -> Optional[ModernTreeview]:
        if source_type == "pack":
            return self.pack_manager.tree if self.pack_manager else None
        return self.missing_manager.tree if self.missing_manager else None

    def _build_layout(self):
        self._dynamic_wrap_labels = []
        # Base grid for the Dashboard to hold the State Frames
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_no_data_state()
        self._build_waiting_state()
        self._build_active_state()

        self._update_dashboard_state()
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget == self:
            if event.width > 100:
                wrap_len = min(550, max(300, event.width - 60))
                for lbl in self._dynamic_wrap_labels:
                    if lbl.winfo_exists():
                        lbl.configure(wraplength=wrap_len)

    def _build_customization_tips(self, parent):
        """Helper to build a unified tips section for both waiting screens."""
        tips_frame = ttk.Frame(parent)

        ttk.Label(
            tips_frame,
            text="✨ Personalize Your Experience",
            font=(Theme.FONT_FAMILY, 11, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, 8))

        tips = [
            (
                "🎨 Themes & Mana Flairs:",
                "Use the 'Theme' menu at the very top of the window to select Magic-inspired color palettes.",
            ),
            (
                "📊 Custom Columns:",
                "Right-click any table header (like 'GIH WR' or 'NAME') to add, remove, or swap the stats. You can even display your downloaded Tier Lists!",
            ),
            (
                "⚙️ Preferences:",
                "Go to File -> Preferences... to change the UI Scale, switch to A-F letter grades, or enable colorful table rows based on mana cost.",
            ),
        ]

        for title, desc in tips:
            row = ttk.Frame(tips_frame)
            row.pack(fill="x", pady=3)

            ttk.Label(
                row,
                text=title,
                font=(Theme.FONT_FAMILY, 9, "bold"),
                bootstyle="primary",
            ).pack(anchor="nw")

            lbl = ttk.Label(
                row,
                text=desc,
                font=(Theme.FONT_FAMILY, 9),
                bootstyle="info",
                justify="left",
            )
            lbl.pack(anchor="nw", fill="x", expand=True)
            self._dynamic_wrap_labels.append(lbl)

        return tips_frame

    def _build_no_data_state(self):
        """State 1: First time user, no data downloaded."""
        self.no_data_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.no_data_frame)
        center_box.pack(expand=True)

        ttk.Label(
            center_box,
            text="👋 Welcome to MTGA Draft Tool",
            font=(Theme.FONT_FAMILY, 13, "bold"),
            bootstyle="primary",
            justify="center",
        ).pack(pady=(0, 10), anchor="center")

        desc1 = ttk.Label(
            center_box,
            text="No 17Lands dataset is currently loaded. You need to download data before you can draft.",
            font=(Theme.FONT_FAMILY, 9),
            justify="center",
        )
        desc1.pack(pady=(0, 15), anchor="center")
        self._dynamic_wrap_labels.append(desc1)

        step_frame = ttk.Frame(center_box)
        step_frame.pack(anchor="center")

        steps = [
            "1. Click the 'Datasets' tab below.",
            "2. Select the SET and EVENT you want to play.",
            "3. Click the 'Download Selected Dataset' button.",
        ]
        for s in steps:
            ttk.Label(
                step_frame,
                text=s,
                font=(Theme.FONT_FAMILY, 9, "bold"),
            ).pack(anchor="w", pady=2)

        expl_frame = ttk.Frame(center_box)
        expl_frame.pack(pady=(15, 0), anchor="center")

        ttk.Label(
            expl_frame,
            text="Dataset Options:",
            font=(Theme.FONT_FAMILY, 9, "bold"),
            bootstyle="warning",
        ).pack(anchor="w", pady=(0, 5))

        lbl_ug = ttk.Label(
            expl_frame,
            text="• USERS: 'All' pulls data from everyone. 'Top' pulls data exclusively from top players.",
            font=(Theme.FONT_FAMILY, 9),
            justify="left",
        )
        lbl_ug.pack(anchor="w", pady=2)
        self._dynamic_wrap_labels.append(lbl_ug)

        lbl_mg = ttk.Label(
            expl_frame,
            text="• MIN GAMES: The minimum amount of data required to show color-specific win rates.",
            font=(Theme.FONT_FAMILY, 9),
            justify="left",
        )
        lbl_mg.pack(anchor="w", pady=2)
        self._dynamic_wrap_labels.append(lbl_mg)

        tips = self._build_customization_tips(center_box)
        tips.pack(pady=(20, 0), anchor="center")

    def _build_waiting_state(self):
        """State 2: Data downloaded, but no draft is active."""
        self.waiting_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.waiting_frame)
        center_box.pack(expand=True)

        ttk.Label(
            center_box,
            text="Waiting for draft to begin...",
            font=(Theme.FONT_FAMILY, 13, "bold"),
            bootstyle="primary",
            justify="center",
        ).pack(pady=(0, 10), anchor="center")

        wait_lbl = ttk.Label(
            center_box,
            text="Ensure 'Detailed Logs (Plugin Support)' is checked in your MTGA Account Settings.",
            font=(Theme.FONT_FAMILY, 9),
            justify="center",
        )
        wait_lbl.pack(pady=(0, 20), anchor="center")
        self._dynamic_wrap_labels.append(wait_lbl)

        tips = self._build_customization_tips(center_box)
        tips.pack(anchor="center")

    def _build_active_state(self):
        """State 3: Active drafting / deckbuilding."""
        self.content_frame = ttk.Frame(self)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=0)
        self.content_frame.columnconfigure(2, weight=0)
        self.content_frame.rowconfigure(0, weight=1)

        # --- LEFT: Tables ---
        self.f_left = ttk.Frame(self.content_frame)
        self.f_left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.f_left.columnconfigure(0, weight=1)
        self.f_left.rowconfigure(0, weight=1)
        self.f_left.rowconfigure(1, weight=0)

        # 1. Pack Table
        self.pack_frame = ttk.Frame(self.f_left)
        self.pack_frame.grid(row=0, column=0, sticky="nsew")

        self.lbl_pack_header = ttk.Label(
            self.pack_frame,
            text="LIVE PACK: TACTICAL EVALUATION",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        )
        self.lbl_pack_header.pack(anchor="w", pady=(0, 5))

        self.pack_manager = DynamicTreeviewManager(
            self.pack_frame,
            view_id="pack_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
            height=1,
        )
        self.pack_manager.pack(fill="both", expand=True)

        self.pack_manager.tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.on_card_select(e, self.pack_manager.tree, "pack"),
        )

        # 2. Missing Table (Wheel Tracker)
        self.missing_frame = ttk.Frame(self.f_left)

        self.lbl_missing_header = ttk.Label(
            self.missing_frame,
            text="SEEN CARDS (WHEEL TRACKER)",
            font=(Theme.FONT_FAMILY, 10, "bold"),
        )
        self.lbl_missing_header.pack(anchor="w", pady=(0, 5))

        self.missing_manager = DynamicTreeviewManager(
            self.missing_frame,
            view_id="missing_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
            height=1,
        )
        self.missing_manager.pack(fill="both", expand=True)
        self.missing_manager.tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.on_card_select(e, self.missing_manager.tree, "missing"),
        )

        self.missing_frame.grid_remove()

        # --- MIDDLE: Thin Rail ---
        self.sidebar_visible = self.configuration.settings.collapsible_states.get(
            "sidebar_panel", True
        )

        self.rail_btn = ttk.Button(
            self.content_frame,
            text="◀" if self.sidebar_visible else "▶",
            command=self._toggle_sidebar,
            bootstyle="secondary",
            width=1,
        )
        self.rail_btn.grid(row=0, column=1, sticky="ns", pady=10, padx=(0, 5))

        # --- RIGHT: Sidebar ---
        self.sidebar_frame = ttk.Frame(self.content_frame, width=250)
        self.sidebar_frame.pack_propagate(False)

        if self.sidebar_visible:
            self.sidebar_frame.grid(
                row=0, column=2, sticky="nsew", padx=(0, 10), pady=10
            )

        self.advisor_panel = AdvisorPanel(self.sidebar_frame, self.configuration)
        self.advisor_panel.pack(fill="x", pady=(0, 15))

        self.signal_container = CollapsibleFrame(
            self.sidebar_frame,
            title="OPEN LANES",
            configuration=self.configuration,
            setting_key="open_lanes_panel",
        )
        self.signal_container.pack(fill="x", pady=(0, 15))
        self.signal_meter = SignalMeter(self.signal_container.content_frame)
        self.signal_meter.pack(fill="x")

        self.curve_container = CollapsibleFrame(
            self.sidebar_frame,
            title="MANA CURVE",
            configuration=self.configuration,
            setting_key="mana_curve_panel",
        )
        self.curve_container.pack(fill="x", pady=(0, 15))
        default_ideal = self.configuration.card_logic.deck_mid.distribution
        self.curve_plot = ManaCurvePlot(
            self.curve_container.content_frame, ideal_distribution=default_ideal
        )
        self.curve_plot.pack(fill="x")

        self.pool_container = CollapsibleFrame(
            self.sidebar_frame,
            title="POOL BALANCE",
            configuration=self.configuration,
            setting_key="pool_balance_panel",
        )
        self.pool_container.pack(fill="x", pady=(0, 15))
        self.type_chart = TypePieChart(self.pool_container.content_frame)
        self.type_chart.pack(fill="x")

    def _update_dashboard_state(self):
        """Evaluates the application data and smoothly swaps the active frame."""
        import os

        has_any_datasets = False
        if os.path.exists(constants.SETS_FOLDER):
            for f in os.listdir(constants.SETS_FOLDER):
                if f.endswith(constants.SET_FILE_SUFFIX):
                    has_any_datasets = True
                    break

        has_draft_data = (
            self._pack_count > 0 or self._missing_count > 0 or self._taken_count > 0
        )

        self.content_frame.grid_remove()
        self.waiting_frame.grid_remove()
        self.no_data_frame.grid_remove()

        if not has_any_datasets:
            self.no_data_frame.grid(row=0, column=0, sticky="nsew")
        elif not has_draft_data:
            self.waiting_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.content_frame.grid(row=0, column=0, sticky="nsew")

    def _adjust_grid_weights(self):
        """Dynamically shifts vertical space based on wheel tracker visibility."""
        if self._missing_count == 0:
            self.missing_frame.grid_remove()
            self.f_left.rowconfigure(0, weight=1)
            self.f_left.rowconfigure(1, weight=0)
        else:
            self.missing_frame.grid(row=1, column=0, sticky="nsew", pady=(15, 0))
            pack_w = max(1, self._pack_count)
            miss_w = max(1, self._missing_count)
            self.f_left.rowconfigure(0, weight=pack_w)
            self.f_left.rowconfigure(1, weight=miss_w)

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
        if not tree or not hasattr(tree, "active_fields"):
            return

        tree.bind(
            "<<TreeviewSelect>>",
            lambda e, t=tree, s=source_type: self.on_card_select(e, t, s),
        )

        for item in tree.get_children():
            tree.delete(item)

        # Track card counts for dynamic layout rendering
        if source_type == "pack":
            self._pack_count = len(cards) if cards else 0
        else:
            self._missing_count = len(cards) if cards else 0

        self._adjust_grid_weights()
        self._update_dashboard_state()

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
                from src.card_logic import row_color_tag

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

            returnable_at = card.get("returnable_at", [])
            if returnable_at:
                display_name += " ⟳" + ",".join(str(p) for p in returnable_at)

            row_values = []
            for field in tree.active_fields:
                if field == "name":
                    row_values.append(str(display_name))
                elif field == "value":
                    if rec:
                        row_values.append(f"{rec.contextual_score:.0f}")
                    else:
                        row_values.append("-")
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "tags":
                    raw_tags = card.get("tags", [])
                    if raw_tags:
                        icons_only = [
                            constants.TAG_VISUALS.get(t, t).split(" ")[0]
                            for t in raw_tags
                        ]
                        row_values.append(" ".join(icons_only))
                    else:
                        row_values.append("-")
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
                    row_values.append(
                        format_win_rate(
                            val,
                            active_filter,
                            field,
                            metrics,
                            self.configuration.settings.result_format,
                        )
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

        if hasattr(tree, "reapply_sort"):
            tree.reapply_sort()

    def update_signals(self, scores: Dict[str, float]):
        if self.signal_meter:
            self.signal_meter.update_values(scores)

    def update_stats(self, distribution: List[int]):
        if self.curve_plot:
            self.curve_plot.update_curve(distribution)

    def update_deck_balance(self, taken_cards):
        # Determine if we have a pool loaded to enforce the "Active" state
        self._taken_count = len(taken_cards) if taken_cards else 0
        self._update_dashboard_state()

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

    def update_recommendations(self, recs):
        if hasattr(self, "advisor_panel"):
            self.advisor_panel.update_recommendations(recs)

    def _toggle_sidebar(self):
        """Dynamically grid or hide the sidebar via the rail button."""
        self.sidebar_visible = not self.sidebar_visible
        self.rail_btn.config(text="◀" if self.sidebar_visible else "▶")

        if self.sidebar_visible:
            self.sidebar_frame.grid(
                row=0, column=2, sticky="nsew", padx=(0, 10), pady=10
            )
        else:
            self.sidebar_frame.grid_remove()

        self.configuration.settings.collapsible_states["sidebar_panel"] = (
            self.sidebar_visible
        )
        from src.configuration import write_configuration

        write_configuration(self.configuration)
