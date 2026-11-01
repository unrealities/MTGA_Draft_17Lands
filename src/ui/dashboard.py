"""
src/ui/dashboard.py
The Professional Live Draft Dashboard.
Supports dynamic grid layouts that auto-adjust based on pack/wheel card counts.
Features built-in state management for onboarding UX and waiting screens.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any, Optional
import threading
import json

from src import constants
from src.card_logic import field_process_sort, row_color_tag
from src.ui.styles import Theme
from src.utils import open_file
from src.ui.components import (
    ModernTreeview,
    DynamicTreeviewManager,
    SignalMeter,
    ManaCurvePlot,
    TypePieChart,
    CollapsibleFrame,
    AutoScrollbar,
)
from src.advisor.schema import Recommendation
from src.ui.advisor_view import AdvisorPanel
from src.card_logic import format_win_rate
from src.ui.dashboard_recap import DraftRecapScreen


class DashboardFrame(ttk.Frame):
    def __init__(
        self,
        parent,
        configuration,
        on_card_select,
        on_reconfigure_ui,
        on_advisor_click=None,
        on_context_menu=None,
    ):
        super().__init__(parent)
        self.configuration = configuration
        self.on_card_select = on_card_select
        self.on_reconfigure_ui = on_reconfigure_ui
        self.on_advisor_click = on_advisor_click
        self.on_context_menu = on_context_menu

        self.pack_manager: Optional[DynamicTreeviewManager] = None
        self.missing_manager: Optional[DynamicTreeviewManager] = None

        self.signal_meter: Optional[SignalMeter] = None
        self.curve_plot: Optional[ManaCurvePlot] = None
        self.type_chart: Optional[TypePieChart] = None

        self.recap_screen: Optional[DraftRecapScreen] = None

        # Track counts for dynamic vertical splitting and State Evaluation
        self._pack_count = 0
        self._missing_count = 0
        self._taken_count = 0
        self._current_event_type = ""
        self._current_event_set = ""
        self._current_pack = 0
        self._current_pick = 0

        self._build_layout()

    def get_treeview(self, source_type: str = "pack") -> Optional[ModernTreeview]:
        if source_type == "pack":
            return self.pack_manager.tree if self.pack_manager else None
        return self.missing_manager.tree if self.missing_manager else None

    def _build_layout(self):
        self._dynamic_wrap_labels = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_no_data_state()
        self._build_waiting_state()
        self._build_deck_recovery_state()
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
            font=Theme.scaled_font(11, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, Theme.scaled_val(8)))

        tips = [
            (
                "🎨 Themes & Mana Flairs:",
                "Use the 'Theme' menu at the very top of the window to select Magic-inspired color palettes.",
            ),
            (
                "📊 Custom Columns:",
                "Right-click any table header (like 'GIH WR' or 'NAME') to re-arrange, add, or remove stats. You can even display your downloaded Tier Lists!",
            ),
            (
                "📁 Custom MTGA Installs:",
                "If MTG Arena is installed on a custom drive and dataset downloads fail, click 'File -> Locate MTGA Data Folder...' to link your local files.",
            ),
            (
                "⚙️ Preferences:",
                "Go to File -> Preferences... to change the UI Scale, switch to A-F letter grades, or enable colorful table rows based on mana cost.",
            ),
        ]

        for title, desc in tips:
            row = ttk.Frame(tips_frame)
            row.pack(fill="x", pady=Theme.scaled_val(3))

            ttk.Label(
                row,
                text=title,
                font=Theme.scaled_font(9, "bold"),
                bootstyle="primary",
            ).pack(anchor="nw")

            lbl = ttk.Label(
                row,
                text=desc,
                font=Theme.scaled_font(9),
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
            font=Theme.scaled_font(13, "bold"),
            bootstyle="primary",
            justify="center",
        ).pack(pady=(0, Theme.scaled_val(10)), anchor="center")

        desc1 = ttk.Label(
            center_box,
            text="No 17Lands dataset is currently loaded. You need to download data before you can draft.",
            font=Theme.scaled_font(9),
            justify="center",
        )
        desc1.pack(pady=(0, Theme.scaled_val(15)), anchor="center")
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
                font=Theme.scaled_font(9, "bold"),
            ).pack(anchor="w", pady=Theme.scaled_val(2))

        expl_frame = ttk.Frame(center_box)
        expl_frame.pack(pady=(Theme.scaled_val(15), 0), anchor="center")

        ttk.Label(
            expl_frame,
            text="Dataset Options:",
            font=Theme.scaled_font(9, "bold"),
            bootstyle="warning",
        ).pack(anchor="w", pady=(0, Theme.scaled_val(5)))

        lbl_ug = ttk.Label(
            expl_frame,
            text="• USERS: 'All' pulls data from everyone. 'Top' pulls data exclusively from top players.",
            font=Theme.scaled_font(9),
            justify="left",
        )
        lbl_ug.pack(anchor="w", pady=Theme.scaled_val(2))
        self._dynamic_wrap_labels.append(lbl_ug)

        lbl_mg = ttk.Label(
            expl_frame,
            text="• MIN GAMES: The minimum amount of data required to show color-specific win rates.",
            font=Theme.scaled_font(9),
            justify="left",
        )
        lbl_mg.pack(anchor="w", pady=Theme.scaled_val(2))
        self._dynamic_wrap_labels.append(lbl_mg)

        tips = self._build_customization_tips(center_box)
        tips.pack(pady=(Theme.scaled_val(20), 0), anchor="center")

    def _build_waiting_state(self):
        """State 2: Data downloaded, but no draft is active."""
        self.waiting_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.waiting_frame)
        center_box.pack(expand=True)

        self.lbl_waiting_title = ttk.Label(
            center_box,
            text="Waiting for draft to begin...",
            font=Theme.scaled_font(13, "bold"),
            bootstyle="primary",
            justify="center",
        )
        self.lbl_waiting_title.pack(pady=(0, Theme.scaled_val(10)), anchor="center")

        self.lbl_waiting_desc = ttk.Label(
            center_box,
            text="Ensure 'Detailed Logs (Plugin Support)' is checked in your MTGA Account Settings.",
            font=Theme.scaled_font(9),
            justify="center",
        )
        self.lbl_waiting_desc.pack(pady=(0, Theme.scaled_val(20)), anchor="center")
        self._dynamic_wrap_labels.append(self.lbl_waiting_desc)

        tips = self._build_customization_tips(center_box)
        tips.pack(anchor="center")

    def _build_deck_recovery_state(self):
        """State 2C: Draft Completed. Shows Fantasy-style Recap."""
        self.recovery_frame = ttk.Frame(self)
        self.recovery_frame.columnconfigure(0, weight=1)
        self.recovery_frame.rowconfigure(0, weight=1)

        def _launch_sealed():
            from src.ui.windows.sealed_studio import SealedStudioWindow

            raw_pool = self.orchestrator.scanner.retrieve_taken_cards()
            metrics = self.orchestrator.scanner.retrieve_set_metrics()
            SealedStudioWindow(
                self.winfo_toplevel(), self, self.configuration, raw_pool, metrics
            )

        self.recap_screen = DraftRecapScreen(
            self.recovery_frame, launch_sealed_callback=_launch_sealed
        )
        self.recap_screen.grid(row=0, column=0, sticky="nsew")

    def update_pool_summary(self, taken_cards, metrics, draft_id=""):
        if self.recap_screen:
            self.recap_screen.update_summary(
                taken_cards, metrics, draft_id, self._current_event_type
            )

    def _build_active_state(self):
        """State 3: Active drafting / deckbuilding."""
        self.content_frame = ttk.Frame(self)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # The Horizontal Slider replacing the rigid grid layout
        self.h_splitter = ttk.PanedWindow(self.content_frame, orient=tkinter.HORIZONTAL)
        self.h_splitter.grid(row=0, column=0, sticky="nsew")
        self.h_splitter.bind("<ButtonRelease-1>", self._on_sash_drag_end)

        # --- LEFT: Tables ---
        self.f_left = ttk.Frame(self.h_splitter)
        self.h_splitter.add(self.f_left, weight=1)

        self.f_left.columnconfigure(0, weight=1)
        self.f_left.columnconfigure(1, weight=0)  # Button column
        self.f_left.rowconfigure(0, weight=1)
        self.f_left.rowconfigure(1, weight=0)

        # 1. Pack Table
        self.pack_frame = ttk.Labelframe(
            self.f_left,
            text=" LIVE PACK: TACTICAL EVALUATION ",
            padding=Theme.scaled_val(5),
        )
        self.pack_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(Theme.scaled_val(10), 0),
            pady=(Theme.scaled_val(10), 0),
        )

        self.pack_manager = DynamicTreeviewManager(
            self.pack_frame,
            view_id="pack_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
            height=1,
        )
        self.pack_manager.pack(fill="both", expand=True)

        if not getattr(self.pack_manager.tree, "_selection_bound", False):
            self.pack_manager.tree.bind(
                "<ButtonRelease-1>",
                lambda e, t=self.pack_manager.tree, s="pack": self.on_card_select(
                    e, t, s
                ),
                add="+",
            )
            for event_type in ["<Button-3>", "<Control-Button-1>"]:
                self.pack_manager.tree.bind(
                    event_type,
                    lambda e, t=self.pack_manager.tree, s="pack": (
                        self.on_context_menu(e, t, s) if self.on_context_menu else None
                    ),
                    add="+",
                )
            self.pack_manager.tree._selection_bound = True

        # 2. Missing Table (Wheel Tracker)
        self.missing_frame = ttk.Labelframe(
            self.f_left,
            text=" SEEN CARDS (WHEEL TRACKER) ",
            padding=Theme.scaled_val(5),
        )

        self.missing_manager = DynamicTreeviewManager(
            self.missing_frame,
            view_id="missing_table",
            configuration=self.configuration,
            on_update_callback=self.on_reconfigure_ui,
            height=1,
        )
        self.missing_manager.pack(fill="both", expand=True)

        if not getattr(self.missing_manager.tree, "_selection_bound", False):
            self.missing_manager.tree.bind(
                "<ButtonRelease-1>",
                lambda e, t=self.missing_manager.tree, s="missing": self.on_card_select(
                    e, t, s
                ),
                add="+",
            )
            for event_type in ["<Button-3>", "<Control-Button-1>"]:
                self.missing_manager.tree.bind(
                    event_type,
                    lambda e, t=self.missing_manager.tree, s="missing": (
                        self.on_context_menu(e, t, s) if self.on_context_menu else None
                    ),
                    add="+",
                )
            self.missing_manager.tree._selection_bound = True

        self.missing_frame.grid_remove()

        # --- MIDDLE: Thin Rail Button ---
        self.sidebar_visible = self.configuration.settings.collapsible_states.get(
            "sidebar_panel", True
        )

        self.rail_btn = ttk.Button(
            self.f_left,
            text="◀" if self.sidebar_visible else "▶",
            command=self._toggle_sidebar,
            bootstyle="secondary-link",
            cursor="hand2",
            takefocus=False,
            width=1,
            padding=0,
        )
        self.rail_btn.grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="",
            padx=(Theme.scaled_val(2), Theme.scaled_val(2)),
        )

        # --- RIGHT: Sidebar ---
        self.sidebar_frame = ttk.Frame(self.h_splitter, width=Theme.scaled_val(280))

        self.sidebar_frame.rowconfigure(0, weight=1)
        self.sidebar_frame.columnconfigure(0, weight=1)

        self._sidebar_scrollbar = AutoScrollbar(self.sidebar_frame, orient="vertical")
        self._sidebar_canvas = tkinter.Canvas(
            self.sidebar_frame,
            highlightthickness=0,
            yscrollcommand=self._sidebar_scrollbar.set,
        )
        self._sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        self._sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        self._sidebar_scrollbar.config(command=self._sidebar_canvas.yview)

        self.sidebar_container = ttk.Frame(self._sidebar_canvas)
        self._sidebar_canvas_window = self._sidebar_canvas.create_window(
            (0, 0), window=self.sidebar_container, anchor="nw"
        )

        def _on_sidebar_resize(event):
            self._sidebar_canvas.itemconfig(
                self._sidebar_canvas_window, width=event.width
            )

        def _on_sidebar_content_resize(event):
            self._sidebar_canvas.configure(
                scrollregion=self._sidebar_canvas.bbox("all")
            )

        self._sidebar_canvas.bind("<Configure>", _on_sidebar_resize)
        self.sidebar_container.bind("<Configure>", _on_sidebar_content_resize)

        # Cross-platform safe scrolling
        from src.utils import bind_scroll

        bind_scroll(self._sidebar_canvas, self._sidebar_canvas.yview_scroll)
        bind_scroll(self.sidebar_container, self._sidebar_canvas.yview_scroll)
        self.sidebar_container.bind(
            "<Enter>",
            lambda e: bind_scroll(
                self.sidebar_container, self._sidebar_canvas.yview_scroll
            ),
        )

        if self.sidebar_visible:
            self.h_splitter.add(self.sidebar_frame, weight=0)

        # --- Advisor Panel ---
        self.advisor_panel = AdvisorPanel(
            self.sidebar_container,
            self.configuration,
            on_click_callback=self.on_advisor_click,
        )
        self._advisor_pack_opts = dict(
            fill="x",
            pady=(Theme.scaled_val(10), Theme.scaled_val(15)),
            padx=(0, Theme.scaled_val(10)),
        )
        self.advisor_panel.pack(**self._advisor_pack_opts)

        self.signal_container = CollapsibleFrame(
            self.sidebar_container,
            title="OPEN LANES",
            configuration=self.configuration,
            setting_key="open_lanes_panel",
        )
        self.signal_container.pack(
            fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10))
        )
        self.signal_meter = SignalMeter(self.signal_container.content_frame)
        self.signal_meter.pack(fill="x")

        self.curve_container = CollapsibleFrame(
            self.sidebar_container,
            title="MANA CURVE",
            configuration=self.configuration,
            setting_key="mana_curve_panel",
        )
        self.curve_container.pack(
            fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10))
        )
        self.set_advisor_visible(self.configuration.settings.advisor_enabled)

        default_ideal = self.configuration.card_logic.deck_mid.distribution
        self.curve_plot = ManaCurvePlot(
            self.curve_container.content_frame, ideal_distribution=default_ideal
        )
        self.curve_plot.pack(fill="x")

        self.pool_container = CollapsibleFrame(
            self.sidebar_container,
            title="POOL BALANCE",
            configuration=self.configuration,
            setting_key="pool_balance_panel",
        )
        self.pool_container.pack(
            fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10))
        )
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

        is_human = self._current_event_type in [
            constants.LIMITED_TYPE_STRING_DRAFT_PREMIER,
            constants.LIMITED_TYPE_STRING_DRAFT_TRAD,
            constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO,
            constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO_TRAD,
        ]

        is_bot = self._current_event_type in [
            constants.LIMITED_TYPE_STRING_DRAFT_QUICK,
            constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO_QUICK,
            constants.LIMITED_TYPE_STRING_DRAFT_BOT,
        ]

        expected_total = 42
        if (
            hasattr(self, "orchestrator")
            and self.orchestrator
            and self.orchestrator.scanner
        ):
            history = self.orchestrator.scanner.retrieve_draft_history()
            max_pack_size = 0
            for entry in history:
                pack_size = entry.get("Pick", 1) + len(entry.get("Cards", [])) - 1
                if pack_size > max_pack_size:
                    max_pack_size = pack_size

            if max_pack_size >= 15:
                expected_total = max_pack_size * 3
            elif max_pack_size == 14:
                expected_total = 42
            elif max_pack_size == 13:
                expected_total = 39

        draft_complete = (is_human or is_bot) and self._taken_count >= expected_total
        sealed_complete = (
            "Sealed" in self._current_event_type and self._taken_count >= 40
        )

        show_recovery = draft_complete or sealed_complete

        was_content_hidden = not self.content_frame.winfo_viewable()
        self.content_frame.grid_remove()
        self.waiting_frame.grid_remove()
        self.no_data_frame.grid_remove()
        if hasattr(self, "recovery_frame"):
            self.recovery_frame.grid_remove()

        if not has_any_datasets:
            pass
        elif has_draft_data:
            if show_recovery:
                self.recovery_frame.grid(row=0, column=0, sticky="nsew")
            else:
                self.content_frame.grid(row=0, column=0, sticky="nsew")

                if was_content_hidden and self.sidebar_visible:

                    def fix_sash():
                        try:
                            curr_w = self.winfo_width()
                            if curr_w > 200:
                                dash_sash = getattr(
                                    self.configuration.settings,
                                    "dashboard_sash",
                                    Theme.scaled_val(800),
                                )
                                safe_sash = min(
                                    dash_sash, curr_w - Theme.scaled_val(280)
                                )
                                if safe_sash > Theme.scaled_val(50):
                                    self.h_splitter.sashpos(0, safe_sash)
                        except Exception:
                            pass

                    self.after(50, fix_sash)
        else:
            if self._current_event_set:
                self.lbl_waiting_title.config(
                    text=f"Draft Started: {self._current_event_set} {self._current_event_type}"
                )
                self.lbl_waiting_desc.config(
                    text="Waiting for pack data to appear in the log..."
                )
            else:
                self.lbl_waiting_title.config(text="Waiting for draft to begin...")
                self.lbl_waiting_desc.config(
                    text="Ensure 'Detailed Logs (Plugin Support)' is checked in your MTGA Account Settings."
                )

            self.waiting_frame.grid(row=0, column=0, sticky="nsew")

    def _adjust_grid_weights(self):
        """Dynamically shifts vertical space based on wheel tracker visibility."""
        if self._missing_count == 0:
            self.missing_frame.grid_remove()
            self.f_left.rowconfigure(0, weight=1, minsize=0)
            self.f_left.rowconfigure(1, weight=0, minsize=0)
        else:
            self.missing_frame.grid(
                row=1,
                column=0,
                sticky="nsew",
                padx=(Theme.scaled_val(10), 0),
                pady=(Theme.scaled_val(15), Theme.scaled_val(10)),
            )

            pack_w = max(1, self._pack_count)
            miss_w = max(1, self._missing_count)

            self.f_left.rowconfigure(0, weight=pack_w, minsize=Theme.scaled_val(140))
            self.f_left.rowconfigure(1, weight=miss_w, minsize=Theme.scaled_val(140))

    def update_pack_data(
        self,
        cards,
        colors,
        metrics,
        tier_data,
        current_pick,
        source_type="pack",
        recommendations=None,
        picked_cards=None,
    ):
        tree = self.get_treeview(source_type)
        if not tree or not hasattr(tree, "active_fields"):
            return

        for item in tree.get_children():
            tree.delete(item)

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

            is_picked = False
            if picked_cards and source_type == "pack":
                if any(c.get(constants.DATA_FIELD_NAME) == name for c in picked_cards):
                    is_picked = True

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

            if is_picked:
                row_tag = "picked"

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
                    "card_name": name,
                    "vals": row_values,
                    "tag": row_tag,
                    "sort_key": (
                        rec.contextual_score if rec else stats.get("gihwr", 0.0)
                    ),
                }
            )

        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)

        for i, row in enumerate(processed_rows):
            if not self.configuration.settings.card_colors_enabled and row["tag"] in [
                "bw_odd",
                "bw_even",
            ]:
                row["tag"] = "bw_odd" if i % 2 == 0 else "bw_even"

            tree.insert(
                "",
                "end",
                text=row.get("card_name", ""),
                values=row["vals"],
                tags=(row["tag"],),
            )

        if hasattr(tree, "reapply_sort"):
            tree.reapply_sort()

    def update_signals(self, scores: Dict[str, float]):
        if self.signal_meter:
            self.signal_meter.update_values(scores)

    def update_stats(self, distribution: List[int]):
        if self.curve_plot:
            self.curve_plot.update_curve(distribution)

    def update_deck_balance(self, taken_cards):
        self._taken_count = len(taken_cards) if taken_cards else 0
        self._update_dashboard_state()

        if not self.type_chart:
            return

        type_counts = {
            "Creature": 0,
            "Planeswalker": 0,
            "Battle": 0,
            "Instant": 0,
            "Sorcery": 0,
            "Enchantment": 0,
            "Artifact": 0,
            "Land": 0,
        }
        for card in taken_cards:
            name = card.get("name", "")
            types = card.get("types", [])

            if "Basic" in types or name in constants.BASIC_LANDS:
                continue

            count = card.get("count", 1)
            if "Creature" in types:
                type_counts["Creature"] += count
            elif "Planeswalker" in types:
                type_counts["Planeswalker"] += count
            elif "Battle" in types:
                type_counts["Battle"] += count
            elif "Instant" in types:
                type_counts["Instant"] += count
            elif "Sorcery" in types:
                type_counts["Sorcery"] += count
            elif "Enchantment" in types:
                type_counts["Enchantment"] += count
            elif "Artifact" in types:
                type_counts["Artifact"] += count
            elif "Land" in types:
                type_counts["Land"] += count

        self.type_chart.update_counts(type_counts)

    def update_recommendations(self, recs):
        if hasattr(self, "advisor_panel"):
            self.advisor_panel.update_recommendations(recs)

    def set_advisor_visible(self, visible):
        if not hasattr(self, "advisor_panel"):
            return
        if not visible:
            self.advisor_panel.pack_forget()
        elif not self.advisor_panel.winfo_manager():
            # Restore it above Open Lanes, where it was built.
            self.advisor_panel.pack(
                before=self.signal_container, **self._advisor_pack_opts
            )

    def _on_sash_drag_end(self, event):
        try:
            self.configuration.settings.dashboard_sash = self.h_splitter.sashpos(0)
        except Exception:
            pass

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self.rail_btn.config(text="◀" if self.sidebar_visible else "▶")

        if self.sidebar_visible:
            self.h_splitter.add(self.sidebar_frame, weight=0)

            self.update_idletasks()

            current_width = self.winfo_width()
            default_sash = (
                max(Theme.scaled_val(50), current_width - Theme.scaled_val(280))
                if current_width > Theme.scaled_val(280)
                else Theme.scaled_val(800)
            )

            dash_sash = getattr(
                self.configuration.settings, "dashboard_sash", default_sash
            )
            if dash_sash < Theme.scaled_val(
                50
            ) or dash_sash >= current_width - Theme.scaled_val(20):
                dash_sash = default_sash

            self.h_splitter.sashpos(0, dash_sash)
        else:
            try:
                self.configuration.settings.dashboard_sash = self.h_splitter.sashpos(0)
            except:
                pass
            self.h_splitter.forget(self.sidebar_frame)

        self.configuration.settings.collapsible_states["sidebar_panel"] = (
            self.sidebar_visible
        )
        from src.configuration import write_configuration

        write_configuration(self.configuration)
