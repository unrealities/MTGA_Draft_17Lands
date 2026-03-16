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
    AutoScrollbar,
)
from src.advisor.schema import Recommendation
from src.ui.advisor_view import AdvisorPanel
from src.card_logic import format_win_rate


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

        # Track counts for dynamic vertical splitting and State Evaluation
        self._pack_count = 0
        self._missing_count = 0
        self._taken_count = 0
        self._current_event_type = ""
        self._current_event_set = ""
        self._current_pack = 0
        self._current_pick = 0
        self.on_p1p1_scan = None

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
        self._build_p1p1_state()
        self._build_deck_recovery_state()
        self._build_draft_recap_state()
        self._build_active_state()

        self._update_dashboard_state()
        self.bind("<Configure>", self._on_resize)

    def _build_draft_recap_state(self):
        self.recap_frame = ttk.Frame(self)

        self.recap_canvas = tkinter.Canvas(
            self.recap_frame, highlightthickness=0, bg=Theme.BG_PRIMARY
        )
        self.recap_scrollbar = AutoScrollbar(
            self.recap_frame, orient="vertical", command=self.recap_canvas.yview
        )

        self.recap_canvas.grid(row=0, column=0, sticky="nsew")
        self.recap_scrollbar.grid(row=0, column=1, sticky="ns")
        self.recap_frame.rowconfigure(0, weight=1)
        self.recap_frame.columnconfigure(0, weight=1)

        self.recap_canvas.configure(yscrollcommand=self.recap_scrollbar.set)

        self.recap_container = ttk.Frame(self.recap_canvas, padding=15)
        self.recap_canvas_window = self.recap_canvas.create_window(
            (0, 0), window=self.recap_container, anchor="nw"
        )

        def _on_content_resize(event):
            self.recap_canvas.configure(scrollregion=self.recap_canvas.bbox("all"))

        def _on_canvas_resize(event):
            self.recap_canvas.itemconfig(self.recap_canvas_window, width=event.width)

        self.recap_container.bind("<Configure>", _on_content_resize)
        self.recap_canvas.bind("<Configure>", _on_canvas_resize)

        from src.utils import bind_scroll

        bind_scroll(self.recap_canvas, self.recap_canvas.yview_scroll)
        bind_scroll(self.recap_container, self.recap_canvas.yview_scroll)
        self.recap_container.bind(
            "<Enter>",
            lambda e: bind_scroll(self.recap_container, self.recap_canvas.yview_scroll),
        )

    def _populate_recap_frame(self):
        for widget in self.recap_container.winfo_children():
            widget.destroy()

        if not getattr(self, "_taken_cards", None):
            return

        taken = self._taken_cards
        is_pick_two = "PickTwo" in self._current_event_type
        cards_per_pack = max(1, len(taken) // 3)

        baseline_wr = 54.0
        if getattr(self, "_metrics", None):
            b, _ = self._metrics.get_metrics("All Decks", "gihwr")
            if b > 0:
                baseline_wr = b

        # --- HEADER (Grade Placeholders) ---
        header = ttk.Frame(self.recap_container)
        header.pack(fill="x", pady=(0, 20))

        self.lbl_grade_desc = ttk.Label(
            header,
            text="Analyzing Draft Data...",
            font=(Theme.FONT_FAMILY, 16, "bold"),
            bootstyle="secondary",
        )
        self.lbl_grade_desc.pack(anchor="center")

        badge_frame = ttk.Frame(header)
        badge_frame.pack(pady=10)
        ttk.Label(
            badge_frame, text="Overall Grade: ", font=(Theme.FONT_FAMILY, 14)
        ).pack(side="left")
        self.lbl_grade_letter = ttk.Label(
            badge_frame,
            text=" ? ",
            font=(Theme.FONT_FAMILY, 20, "bold"),
            bootstyle="inverse-secondary",
        )
        self.lbl_grade_letter.pack(side="left")

        # --- DATA CRUNCHING (Fast Operations) ---
        taken = self._taken_cards
        is_pick_two = "PickTwo" in self._current_event_type
        cards_per_pack = max(1, len(taken) // 3)

        baseline_wr = 54.0
        if getattr(self, "_metrics", None):
            b, _ = self._metrics.get_metrics("All Decks", "gihwr")
            if b > 0:
                baseline_wr = b

        # 1. Biggest Steals
        from src import constants

        steals = []
        for i, card in enumerate(taken):
            if (
                "Basic" in card.get("types", [])
                or card.get("name") in constants.BASIC_LANDS
            ):
                continue
            pick_num = (
                (i % cards_per_pack) // 2 + 1
                if is_pick_two
                else (i % cards_per_pack) + 1
            )
            stats = card.get("deck_colors", {}).get("All Decks", {})
            alsa = float(stats.get("alsa", 0.0))
            gihwr = float(stats.get("gihwr", 0.0))

            # Criteria: Better than average card, picked much later than it is typically seen
            if gihwr >= (baseline_wr + 0.5) and alsa > 0 and pick_num >= (alsa + 1.5):
                steals.append(
                    {
                        "card": card,
                        "pick": pick_num,
                        "alsa": alsa,
                        "gihwr": gihwr,
                        "diff": pick_num - alsa,
                    }
                )

        steals.sort(key=lambda x: x["diff"], reverse=True)
        top_steals = steals[:7]

        # 2. Top Power Cards
        top_power = [
            c
            for c in taken
            if not (
                "Basic" in c.get("types", [])
                or c.get("name", "") in constants.BASIC_LANDS
            )
        ]
        top_power.sort(
            key=lambda c: float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        top_power = top_power[:7]

        # 3. Rares & Mythics
        rares = [c for c in taken if c.get("rarity", "").lower() in ["rare", "mythic"]]
        rares.sort(
            key=lambda c: float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )

        # --- RENDER LISTS ---
        content_grid = ttk.Frame(self.recap_container)
        content_grid.pack(fill="both", expand=True)
        content_grid.columnconfigure(0, weight=1)
        content_grid.columnconfigure(1, weight=1)

        def build_card_list(parent, row, col, title, items, is_steal=False):
            frame = ttk.Labelframe(parent, text=f" {title} ", padding=15)
            frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)

            if not items:
                ttk.Label(
                    frame,
                    text="None found.",
                    font=(Theme.FONT_FAMILY, 10, "italic"),
                    bootstyle="secondary",
                ).pack(anchor="w")
                return

            for item in items:
                card = item["card"] if is_steal else item
                name = card.get("name", "Unknown")
                stats = card.get("deck_colors", {}).get("All Decks", {})
                gihwr = float(stats.get("gihwr", 0.0))

                row_f = ttk.Frame(frame)
                row_f.pack(fill="x", pady=4)

                if is_steal:
                    pick_num = item["pick"]
                    alsa = item["alsa"]
                    stat_str = f"Pick {pick_num} (ALSA {alsa:.1f})"
                else:
                    stat_str = f"{gihwr:.1f}% WR"

                lbl_name = ttk.Label(
                    row_f,
                    text=name,
                    font=(Theme.FONT_FAMILY, 11, "bold"),
                    cursor="hand2",
                )
                lbl_name.pack(side="left")

                lbl_stat = ttk.Label(
                    row_f,
                    text=f"  {stat_str}",
                    font=(Theme.FONT_FAMILY, 10),
                    bootstyle="secondary",
                )
                lbl_stat.pack(side="right")

                # Attach Tooltips
                lbl_name.bind(
                    "<Button-1>",
                    lambda e, c=card: self._trigger_recap_tooltip(lbl_name, c),
                )
                row_f.bind(
                    "<Button-1>",
                    lambda e, c=card: self._trigger_recap_tooltip(row_f, c),
                )

        build_card_list(content_grid, 0, 0, "Biggest Steals", top_steals, is_steal=True)
        build_card_list(
            content_grid, 0, 1, "Best Cards Drafted", top_power, is_steal=False
        )
        build_card_list(content_grid, 1, 0, "Rares & Mythics", rares, is_steal=False)

        # --- STATS PANEL (Placeholders) ---
        self.stats_frame = ttk.Labelframe(
            content_grid, text=" Draft Profile ", padding=15
        )
        self.stats_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.lbl_stats_loading = ttk.Label(
            self.stats_frame,
            text="Running AI Optimizer...",
            font=(Theme.FONT_FAMILY, 10, "italic"),
            bootstyle="secondary",
        )
        self.lbl_stats_loading.pack(anchor="w")

        # --- ASYNC GRADE CALCULATION ---
        dataset_name = self.configuration.card_data.latest_dataset

        def _recap_worker():
            try:
                from src.card_logic import suggest_deck

                variants = suggest_deck(
                    self._taken_cards,
                    self._metrics,
                    self.configuration,
                    self._current_event_type,
                    dataset_name=dataset_name,
                )
                self.after(0, lambda: self._apply_recap_grade(variants))
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Recap Generation Error: {e}")

        import threading

        threading.Thread(target=_recap_worker, daemon=True).start()

    def _apply_recap_grade(self, variants):
        if not self.winfo_exists() or not hasattr(self, "lbl_grade_letter"):
            return

        grade_letter = "N/A"
        grade_color = "secondary"
        grade_desc = "Draft Complete!"
        best_variant = None

        if variants:
            best_variant = max(variants.values(), key=lambda v: v["rating"])
            rating = best_variant["rating"]
            if rating >= 85.0:
                grade_letter = "S"
                grade_color = "success"
                grade_desc = "Incredible Draft! (Trophy Contender)"
            elif rating >= 75.0:
                grade_letter = "A"
                grade_color = "success"
                grade_desc = "Excellent Draft! (Strong Deck)"
            elif rating >= 65.0:
                grade_letter = "B"
                grade_color = "info"
                grade_desc = "Solid Draft (Good Fundamentals)"
            elif rating >= 55.0:
                grade_letter = "C"
                grade_color = "warning"
                grade_desc = "Average Draft (Playable)"
            else:
                grade_letter = "D"
                grade_color = "danger"
                grade_desc = "Rough Draft (Needs Luck)"

        self.lbl_grade_desc.config(text=grade_desc, bootstyle="primary")
        self.lbl_grade_letter.config(
            text=f" {grade_letter} ", bootstyle=f"inverse-{grade_color}"
        )

        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        if best_variant:
            deck = best_variant["deck_cards"]
            creatures = sum(
                c.get("count", 1) for c in deck if "Creature" in c.get("types", [])
            )
            lands = sum(c.get("count", 1) for c in deck if "Land" in c.get("types", []))
            spells = sum(c.get("count", 1) for c in deck) - creatures - lands

            arch_str = "".join(best_variant.get("colors", ["Auto"]))
            from src.constants import COLOR_NAMES_DICT

            arch_name = COLOR_NAMES_DICT.get(arch_str, arch_str)

            ttk.Label(
                self.stats_frame,
                text="Suggested Archetype:",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(anchor="w", pady=(0, 2))
            ttk.Label(
                self.stats_frame,
                text=f"{arch_name}",
                font=(Theme.FONT_FAMILY, 13, "bold"),
                bootstyle="primary",
            ).pack(anchor="w", pady=(0, 10))

            ttk.Label(
                self.stats_frame,
                text=f"Creatures: {creatures}",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(anchor="w", pady=2)
            ttk.Label(
                self.stats_frame,
                text=f"Non-Creatures: {spells}",
                font=(Theme.FONT_FAMILY, 11),
            ).pack(anchor="w", pady=2)
            ttk.Label(
                self.stats_frame, text=f"Lands: {lands}", font=(Theme.FONT_FAMILY, 11)
            ).pack(anchor="w", pady=2)
        else:
            ttk.Label(
                self.stats_frame,
                text="Not enough cards to form a profile.",
                bootstyle="secondary",
            ).pack(anchor="w")

    def _trigger_recap_tooltip(self, widget, card):
        from src.ui.components import CardToolTip
        from src import constants

        scale = constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0)
        CardToolTip.create(
            widget, card, self.configuration.features.images_enabled, scale
        )

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
                "Right-click any table header (like 'GIH WR' or 'NAME') to re-arrange, add, or remove stats. You can even display your downloaded Tier Lists!",
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

        self.lbl_waiting_title = ttk.Label(
            center_box,
            text="Waiting for draft to begin...",
            font=(Theme.FONT_FAMILY, 13, "bold"),
            bootstyle="primary",
            justify="center",
        )
        self.lbl_waiting_title.pack(pady=(0, 10), anchor="center")

        self.lbl_waiting_desc = ttk.Label(
            center_box,
            text="Ensure 'Detailed Logs (Plugin Support)' is checked in your MTGA Account Settings.",
            font=(Theme.FONT_FAMILY, 9),
            justify="center",
        )
        self.lbl_waiting_desc.pack(pady=(0, 20), anchor="center")
        self._dynamic_wrap_labels.append(self.lbl_waiting_desc)

        tips = self._build_customization_tips(center_box)
        tips.pack(anchor="center")

    def _build_p1p1_state(self):
        """State 2B: Draft active, but Pack 1 is hidden by MTGA logs."""
        self.p1p1_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.p1p1_frame)
        center_box.pack(expand=True)

        ttk.Label(
            center_box,
            text="Draft Started: The P1P1 Gap",
            font=(Theme.FONT_FAMILY, 14, "bold"),
            bootstyle="warning",
            justify="center",
        ).pack(pady=(0, 10), anchor="center")

        desc1 = ttk.Label(
            center_box,
            text="MTG Arena delays writing the first pack to the log file in Human Drafts.\nTo see your options before picking, we must use Screen Capture (OCR).",
            font=(Theme.FONT_FAMILY, 10),
            justify="center",
        )
        desc1.pack(pady=(0, 20), anchor="center")
        self._dynamic_wrap_labels.append(desc1)

        self.btn_dashboard_scan = ttk.Button(
            center_box,
            text="SCAN P1P1 (Take Screenshot)",
            bootstyle="success",
            command=lambda: self.on_p1p1_scan() if self.on_p1p1_scan else None,
            padding=(20, 10),
        )
        self.btn_dashboard_scan.pack(pady=(0, 20))

        desc2 = ttk.Label(
            center_box,
            text="Note: You can disable this feature or choose to save the screenshots locally via File -> Preferences.",
            font=(Theme.FONT_FAMILY, 9),
            bootstyle="secondary",
            justify="center",
        )
        desc2.pack(pady=(0, 0), anchor="center")
        self._dynamic_wrap_labels.append(desc2)

    def _build_deck_recovery_state(self):
        """State 2C: Draft recovered from logs, but no active pack data available."""
        self.recovery_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.recovery_frame)
        center_box.pack(expand=True)

        self.lbl_recovery_title = ttk.Label(
            center_box,
            text="Draft Recovered",
            font=(Theme.FONT_FAMILY, 14, "bold"),
            bootstyle="info",
            justify="center",
        )
        self.lbl_recovery_title.pack(pady=(0, 10), anchor="center")

        desc1 = ttk.Label(
            center_box,
            text="We successfully recovered your drafted cards from the MTGA logs.\nYour pool is available in the 'Card Pool' and 'Deck Builder' tabs below.",
            font=(Theme.FONT_FAMILY, 10),
            justify="center",
        )
        desc1.pack(pady=(0, 20), anchor="center")
        self._dynamic_wrap_labels.append(desc1)

        desc2 = ttk.Label(
            center_box,
            text="Waiting for a new draft to begin...",
            font=(Theme.FONT_FAMILY, 9),
            bootstyle="secondary",
            justify="center",
        )
        desc2.pack(pady=(0, 0), anchor="center")
        self._dynamic_wrap_labels.append(desc2)

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
            self.f_left, text=" LIVE PACK: TACTICAL EVALUATION ", padding=5
        )
        self.pack_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))

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

        for event_type in ["<Button-3>", "<Control-Button-1>"]:
            self.pack_manager.tree.bind(
                event_type,
                lambda e: (
                    self.on_context_menu(e, self.pack_manager.tree, "pack")
                    if self.on_context_menu
                    else None
                ),
                add="+",
            )

        # 2. Missing Table (Wheel Tracker)
        self.missing_frame = ttk.Labelframe(
            self.f_left, text=" SEEN CARDS (WHEEL TRACKER) ", padding=5
        )

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

        for event_type in ["<Button-3>", "<Control-Button-1>"]:
            self.missing_manager.tree.bind(
                event_type,
                lambda e: (
                    self.on_context_menu(e, self.missing_manager.tree, "missing")
                    if self.on_context_menu
                    else None
                ),
                add="+",
            )

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
        self.rail_btn.grid(row=0, column=1, rowspan=2, sticky="", padx=(2, 2))

        # --- RIGHT: Sidebar ---
        self.sidebar_frame = ttk.Frame(self.h_splitter, width=280)

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
        self.advisor_panel.pack(fill="x", pady=(10, 15), padx=(0, 10))

        self.signal_container = CollapsibleFrame(
            self.sidebar_container,
            title="OPEN LANES",
            configuration=self.configuration,
            setting_key="open_lanes_panel",
        )
        self.signal_container.pack(fill="x", pady=(0, 15), padx=(0, 10))
        self.signal_meter = SignalMeter(self.signal_container.content_frame)
        self.signal_meter.pack(fill="x")

        self.curve_container = CollapsibleFrame(
            self.sidebar_container,
            title="MANA CURVE",
            configuration=self.configuration,
            setting_key="mana_curve_panel",
        )
        self.curve_container.pack(fill="x", pady=(0, 15), padx=(0, 10))
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
        self.pool_container.pack(fill="x", pady=(0, 15), padx=(0, 10))
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

        is_sealed = "Sealed" in self._current_event_type

        # Determine if we should show the explicit P1P1 OCR frame
        show_p1p1 = (
            self._current_event_set
            and is_human
            and self._current_pack <= 1
            and self._current_pick <= 1
            and self._pack_count == 0
            and self.configuration.settings.p1p1_ocr_enabled
        )

        # Determine if we recovered a deck but have no active packs.
        # Only show this static screen if the draft is fully COMPLETED (>= 40 cards).
        # Otherwise, they are mid-draft and just waiting for the next pack to appear!
        is_draft_complete = False
        if is_sealed and self._taken_count >= 40:
            is_draft_complete = True
        elif (
            not is_sealed
            and getattr(self, "_pack_fully_picked", False)
            and self._current_pack >= 3
        ):
            is_draft_complete = True
        elif not is_sealed and self._taken_count >= 40 and self._pack_count == 0:
            is_draft_complete = True

        show_recap = is_draft_complete

        # Capture visibility BEFORE grid_remove() so was_hidden is accurate
        was_content_hidden = not self.content_frame.winfo_viewable()
        self.content_frame.grid_remove()
        self.waiting_frame.grid_remove()
        self.no_data_frame.grid_remove()
        if hasattr(self, "p1p1_frame"):
            self.p1p1_frame.grid_remove()
        if hasattr(self, "recovery_frame"):
            self.recovery_frame.grid_remove()
        if hasattr(self, "recap_frame"):
            self.recap_frame.grid_remove()

        if not has_any_datasets:
            self.no_data_frame.grid(row=0, column=0, sticky="nsew")
        elif show_p1p1:
            self.p1p1_frame.grid(row=0, column=0, sticky="nsew")
        elif show_recap:
            if is_sealed:
                if self._current_event_set:
                    self.lbl_recovery_title.config(
                        text=f"Sealed Pool Recovered: {self._current_event_set} {self._current_event_type}"
                    )
                self.recovery_frame.grid(row=0, column=0, sticky="nsew")
            else:
                self.recap_frame.grid(row=0, column=0, sticky="nsew")
                self._populate_recap_frame()
        elif has_draft_data:
            self.content_frame.grid(row=0, column=0, sticky="nsew")

            if was_content_hidden and self.sidebar_visible:

                def fix_sash():
                    try:
                        curr_w = self.winfo_width()
                        if curr_w > 200:
                            dash_sash = getattr(
                                self.configuration.settings, "dashboard_sash", 800
                            )
                            safe_sash = min(dash_sash, curr_w - 280)
                            if safe_sash > 50:
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
                row=1, column=0, sticky="nsew", padx=(10, 0), pady=(15, 10)
            )

            pack_w = max(1, self._pack_count)
            miss_w = max(1, self._missing_count)

            # minsize guarantees that even if a table only has 1 card, Tkinter will refuse
            # to crush it smaller than 140 pixels, ensuring it remains fully readable!
            self.f_left.rowconfigure(0, weight=pack_w, minsize=140)
            self.f_left.rowconfigure(1, weight=miss_w, minsize=140)

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

        tree.bind(
            "<<TreeviewSelect>>",
            lambda e, t=tree, s=source_type: self.on_card_select(e, t, s),
        )

        for item in tree.get_children():
            tree.delete(item)

        # Track card counts for dynamic layout rendering
        if source_type == "pack":
            self._pack_count = len(cards) if cards else 0
            self._pack_fully_picked = (
                picked_cards is not None
                and self._pack_count > 0
                and len(picked_cards) >= self._pack_count
            )
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
                    "vals": row_values,
                    "tag": row_tag,
                    "sort_key": (
                        rec.contextual_score if rec else stats.get("gihwr", 0.0)
                    ),
                }
            )

        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)

        # Apply zebra striping AFTER sorting so the alternating pattern is correct on load
        for i, row in enumerate(processed_rows):
            if not self.configuration.settings.card_colors_enabled and row["tag"] in [
                "bw_odd",
                "bw_even",
            ]:
                row["tag"] = "bw_odd" if i % 2 == 0 else "bw_even"

            tree.insert("", "end", values=row["vals"], tags=(row["tag"],))

        if hasattr(tree, "reapply_sort"):
            tree.reapply_sort()

    def update_signals(self, scores: Dict[str, float]):
        if self.signal_meter:
            self.signal_meter.update_values(scores)

    def update_stats(self, distribution: List[int]):
        if self.curve_plot:
            self.curve_plot.update_curve(distribution)

    def update_deck_balance(self, taken_cards, history=None, metrics=None):
        # Determine if we have a pool loaded to enforce the "Active" state
        self._taken_cards = taken_cards
        self._history = history
        self._metrics = metrics
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

    def _on_sash_drag_end(self, event):
        """Save the sash position immediately after the user drags it."""
        try:
            self.configuration.settings.dashboard_sash = self.h_splitter.sashpos(0)
        except Exception:
            pass

    def _toggle_sidebar(self):
        """Dynamically grid or hide the sidebar via the rail button."""
        self.sidebar_visible = not self.sidebar_visible
        self.rail_btn.config(text="◀" if self.sidebar_visible else "▶")

        if self.sidebar_visible:
            self.h_splitter.add(self.sidebar_frame, weight=0)

            self.update_idletasks()

            current_width = self.winfo_width()
            default_sash = max(50, current_width - 280) if current_width > 280 else 800

            dash_sash = getattr(
                self.configuration.settings, "dashboard_sash", default_sash
            )
            if dash_sash < 50 or dash_sash >= current_width - 20:
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
