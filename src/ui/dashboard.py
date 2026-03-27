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

        self.recap_curve_plot: Optional[ManaCurvePlot] = None
        self.recap_type_chart: Optional[TypePieChart] = None

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

    def _build_p1p1_state(self):
        """State 2B: Draft active, but Pack 1 is hidden by MTGA logs."""
        self.p1p1_frame = ttk.Frame(self)

        center_box = ttk.Frame(self.p1p1_frame)
        center_box.pack(expand=True)

        ttk.Label(
            center_box,
            text="Draft Started: The P1P1 Gap",
            font=Theme.scaled_font(14, "bold"),
            bootstyle="warning",
            justify="center",
        ).pack(pady=(0, Theme.scaled_val(10)), anchor="center")

        desc1 = ttk.Label(
            center_box,
            text="MTG Arena delays writing the first pack to the log file in Human Drafts.\nTo see your options before picking, we must use Screen Capture (OCR).\nPressing the button below will hide the app (timeout: 8 seconds) and take a screenshot of your screen.",
            font=Theme.scaled_font(10),
            justify="center",
        )
        desc1.pack(pady=(0, Theme.scaled_val(20)), anchor="center")
        self._dynamic_wrap_labels.append(desc1)

        self.btn_dashboard_scan = ttk.Button(
            center_box,
            text="SCAN P1P1 (Take Screenshot)",
            bootstyle="success",
            command=lambda: self.on_p1p1_scan() if self.on_p1p1_scan else None,
            padding=(Theme.scaled_val(20), Theme.scaled_val(10)),
        )
        self.btn_dashboard_scan.pack(pady=(0, Theme.scaled_val(20)))

        desc2 = ttk.Label(
            center_box,
            text="Note: You can disable this feature or choose to save the screenshots locally via File -> Preferences.",
            font=Theme.scaled_font(9),
            bootstyle="secondary",
            justify="center",
        )
        desc2.pack(pady=(0, 0), anchor="center")
        self._dynamic_wrap_labels.append(desc2)

    def _create_stat_box(self, parent, title, text_var_name):
        """Helper to create cohesive stat boxes for the Post-Draft Recap."""
        frame = ttk.Labelframe(parent, text=title, padding=Theme.scaled_val(8))
        lbl = ttk.Label(frame, text="", font=Theme.scaled_font(9), justify="left")
        lbl.pack(anchor="nw", fill="both", expand=True)
        setattr(self, text_var_name, lbl)
        self._dynamic_wrap_labels.append(lbl)
        return frame

    def _build_deck_recovery_state(self):
        """State 2C: Draft Completed. Shows Fantasy-style Recap."""
        self.recovery_frame = ttk.Frame(self)
        self.recovery_frame.columnconfigure(0, weight=1)
        self.recovery_frame.rowconfigure(1, weight=1)

        # HEADER
        header_frame = ttk.Frame(self.recovery_frame, padding=Theme.scaled_val(10), style="Card.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_recovery_title = ttk.Label(
            header_frame,
            text="Draft Completed",
            font=Theme.scaled_font(18, "bold"),
            bootstyle="success",
        )
        self.lbl_recovery_title.pack(side="left")

        self.btn_17lands_link = ttk.Button(
            header_frame, text="View Draft on 17Lands 🌐", bootstyle="info-outline"
        )

        # TABBED CONTENT
        self.recap_notebook = ttk.Notebook(self.recovery_frame)
        self.recap_notebook.grid(row=1, column=0, sticky="nsew", padx=Theme.scaled_val(10), pady=Theme.scaled_val((10, 0)))

        # --- TAB 1: DRAFT RECAP ---
        tab_recap = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_recap, text=" 🏆 Draft Recap ")

        top_recap = ttk.Frame(tab_recap)
        top_recap.pack(fill="x", pady=Theme.scaled_val((0, 10)))

        self.lbl_recovery_grade = ttk.Label(
            top_recap,
            text="Pool Power Grade: --",
            font=Theme.scaled_font(16, "bold"),
            bootstyle="primary",
        )
        self.lbl_recovery_grade.pack(anchor="center", pady=Theme.scaled_val((0, 2)))

        self.lbl_recovery_stats = ttk.Label(
            top_recap,
            text="Top 23 Cards Avg Win Rate: --%",
            font=Theme.scaled_font(11),
        )
        self.lbl_recovery_stats.pack(anchor="center")

        self.lbl_actual_record = ttk.Label(
            top_recap, text="", font=Theme.scaled_font(11, "bold")
        )

        # Grid for Highlights
        grid_recap = ttk.Frame(tab_recap)
        grid_recap.pack(fill="both", expand=True)
        grid_recap.columnconfigure((0, 1), weight=1)
        grid_recap.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_recap, "TOP ARCHETYPES", "lbl_recap_archetypes"
        ).grid(row=0, column=0, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))
        self._create_stat_box(grid_recap, "BEST CARDS DRAFTED", "lbl_recap_best").grid(
            row=0, column=1, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5)
        )
        self._create_stat_box(
            grid_recap, "BIGGEST STEALS (LATE PICKS)", "lbl_recap_steals"
        ).grid(row=1, column=0, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))
        self._create_stat_box(
            grid_recap, "BIGGEST REACHES (EARLY PICKS)", "lbl_recap_reaches"
        ).grid(row=1, column=1, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))

        # --- TAB 2: SYNERGY & ROLES ---
        tab_synergy = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_synergy, text=" 🧩 Synergy & Roles ")

        grid_synergy = ttk.Frame(tab_synergy)
        grid_synergy.pack(fill="both", expand=True)
        grid_synergy.columnconfigure((0, 1), weight=1)
        grid_synergy.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_synergy, "TOP CREATURE TYPES", "lbl_synergy_tribes"
        ).grid(row=0, column=0, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))
        self._create_stat_box(grid_synergy, "CARD ROLES", "lbl_synergy_roles").grid(
            row=0, column=1, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5)
        )
        self._create_stat_box(
            grid_synergy, "PREMIUM STAPLES", "lbl_synergy_staples"
        ).grid(row=1, column=0, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))
        self._create_stat_box(
            grid_synergy, "NON-BASIC LANDS", "lbl_synergy_lands"
        ).grid(row=1, column=1, sticky="nsew", padx=Theme.scaled_val(5), pady=Theme.scaled_val(5))

        # --- TAB 3: MANA & CURVE ---
        tab_analysis = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_analysis, text=" 📊 Mana & Curve ")

        tab_analysis.columnconfigure((0, 1), weight=1)
        tab_analysis.rowconfigure(0, weight=1)

        charts_frame = ttk.Frame(tab_analysis)
        charts_frame.grid(row=0, column=0, sticky="nsew", padx=Theme.scaled_val((0, 10)))

        ttk.Label(
            charts_frame,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_curve_plot = ManaCurvePlot(charts_frame, ideal_distribution=[])
        self.recap_curve_plot.pack(fill="x", pady=Theme.scaled_val((0, 15)))

        ttk.Label(
            charts_frame,
            text="POOL BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_type_chart = TypePieChart(charts_frame)
        self.recap_type_chart.pack(fill="x")

        stats_col = ttk.Frame(tab_analysis)
        stats_col.grid(row=0, column=1, sticky="nsew")

        self._create_stat_box(stats_col, "RARES & MYTHICS", "lbl_recap_rares").pack(
            fill="both", expand=True, pady=Theme.scaled_val((0, 10))
        )

    def update_pool_summary(self, taken_cards, metrics, draft_id=""):
        """Calculates a heuristic letter grade for the completed pool and fetches real 17Lands results."""
        if not taken_cards or len(taken_cards) < 40:
            return

        # Hide 17Lands elements initially in case we are cycling between drafts
        if hasattr(self, "lbl_actual_record"):
            self.lbl_actual_record.pack_forget()
        if hasattr(self, "btn_17lands_link"):
            self.btn_17lands_link.pack_forget()

        def get_gihwr(c):
            return float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            )

        valid_cards = [
            c
            for c in taken_cards
            if "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]

        if not valid_cards:
            return

        # --- 1. OVERALL GRADE (Aligned to Deck Power Scale) ---

        valid_cards.sort(key=get_gihwr, reverse=True)
        top_23 = valid_cards[:23]
        avg_gihwr = sum(get_gihwr(c) for c in top_23) / len(top_23)

        global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
        if global_mean <= 0:
            global_mean = 54.5
        if global_std <= 0:
            global_std = 3.5

        z_score = (avg_gihwr - global_mean) / global_std

        # Standardize against Deck Builder power formula (75 + Z * 12)
        pool_power = max(0, min(100, 75.0 + (z_score * 12.0)))

        if pool_power >= 90:
            grade_str = "S (God Tier)"
            bootstyle = "success"
        elif pool_power >= 85:
            grade_str = "A (Amazing)"
            bootstyle = "success"
        elif pool_power >= 80:
            grade_str = "B+ (Great)"
            bootstyle = "info"
        elif pool_power >= 75:
            grade_str = "B (Good)"
            bootstyle = "info"
        elif pool_power >= 70:
            grade_str = "C (Average)"
            bootstyle = "warning"
        elif pool_power >= 60:
            grade_str = "D (Below Average)"
            bootstyle = "danger"
        else:
            grade_str = "F (Trainwreck)"
            bootstyle = "danger"

        if hasattr(self, "lbl_recovery_grade"):
            self.lbl_recovery_grade.config(
                text=f"Pool Quality: {pool_power:.0f}/100 [{grade_str}]",
                bootstyle=bootstyle,
            )
        if hasattr(self, "lbl_recovery_stats"):
            self.lbl_recovery_stats.config(
                text=f"Top 23 Avg Win Rate: {avg_gihwr:.1f}% (Format Avg: {global_mean:.1f}%)"
            )

        # --- 2. TOP ARCHETYPES ---
        from src.card_logic import identify_top_pairs
        from src.utils import normalize_color_string

        top_pairs = identify_top_pairs(taken_cards, metrics)

        arch_data = []
        for pair in top_pairs:
            raw_lane = "".join(pair)
            lane = normalize_color_string(raw_lane)
            wr, _ = metrics.get_metrics(lane, "gihwr")
            name = constants.COLOR_NAMES_DICT.get(lane, lane)
            arch_data.append((name, wr))

        # Sort from highest win rate to lowest
        arch_data.sort(key=lambda x: x[1], reverse=True)

        arch_text = ""
        for name, wr in arch_data[:3]:
            if wr > 0.0:
                arch_text += f"• {name} ({wr:.1f}%)\n"
            else:
                arch_text += f"• {name}\n"

        if hasattr(self, "lbl_recap_archetypes"):
            self.lbl_recap_archetypes.config(
                text=arch_text if arch_text else "None Identified"
            )

        # --- 3. BEST CARDS DRAFTED ---
        best_text = ""
        for c in top_23[:6]:
            wr = get_gihwr(c)
            name = c.get("name", "Unknown")
            best_text += f"• {name} ({wr:.1f}%)\n"

        if hasattr(self, "lbl_recap_best"):
            self.lbl_recap_best.config(text=best_text)

        # --- 4. STEALS & REACHES (WITH EXACT PACK/PICK) ---
        total_cards = len(taken_cards)
        if total_cards >= 45:
            cards_per_pack = 15
        elif total_cards >= 42:
            cards_per_pack = 14
        else:
            cards_per_pack = total_cards // 3 if total_cards >= 3 else 14
        if cards_per_pack == 0:
            cards_per_pack = 14

        steals = []
        reaches = []

        for i, c in enumerate(taken_cards):
            name = c.get("name", "")
            if "Basic" in c.get("types", []) or name in constants.BASIC_LANDS:
                continue

            pack = (i // cards_per_pack) + 1
            pick = (i % cards_per_pack) + 1

            gihwr = get_gihwr(c)
            alsa = float(c.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0))
            ata = float(c.get("deck_colors", {}).get("All Decks", {}).get("ata", 0.0))

            # Steal: Taken 1.5+ picks later than average, and actually a good card.
            if alsa > 0 and pick > alsa + 1.5 and gihwr >= 55.0:
                steals.append((c, pack, pick, alsa, pick - alsa))

            # Reach: Taken 1.5+ picks earlier than average, and statistically subpar.
            if ata > 0 and ata > pick + 1.5 and gihwr < 54.0:
                reaches.append((c, pack, pick, ata, ata - pick))

        steals.sort(key=lambda x: x[4], reverse=True)
        reaches.sort(key=lambda x: x[4], reverse=True)

        steal_text = ""
        for c, pack, pick, alsa, diff in steals[:6]:
            steal_text += (
                f"• {c.get('name')} (P{pack}P{pick} | ALSA {alsa:.1f} | +{diff:.1f})\n"
            )

        if hasattr(self, "lbl_recap_steals"):
            self.lbl_recap_steals.config(
                text=steal_text if steal_text else "No major steals detected."
            )

        reach_text = ""
        for c, pack, pick, ata, diff in reaches[:6]:
            reach_text += (
                f"• {c.get('name')} (P{pack}P{pick} | ATA {ata:.1f} | -{diff:.1f})\n"
            )

        if hasattr(self, "lbl_recap_reaches"):
            self.lbl_recap_reaches.config(
                text=reach_text if reach_text else "No major reaches detected."
            )

        # --- 5. SYNERGY & ROLES (TAB 2) ---
        subtypes_counts = {}
        tags_count = {}
        non_basics = []

        for c in taken_cards:
            name = c.get("name", "")
            types = c.get("types", [])
            subs = c.get("subtypes", [])

            if "Basic" in types or name in constants.BASIC_LANDS:
                continue

            if "Land" in types:
                non_basics.append(c)

            # Only count subtypes if the card is actually a creature (ignores Food, Treasure, etc.)
            if "Creature" in types:
                for sub in subs:
                    subtypes_counts[sub] = subtypes_counts.get(sub, 0) + 1

            for tag in c.get("tags", []):
                tags_count[tag] = tags_count.get(tag, 0) + 1

        # 1. Tribes
        top_tribes = sorted(subtypes_counts.items(), key=lambda x: x[1], reverse=True)
        tribe_text = ""
        for t, count in top_tribes[:6]:
            if count >= 3:
                tribe_text += f"• {t} ({count})\n"

        if hasattr(self, "lbl_synergy_tribes"):
            self.lbl_synergy_tribes.config(
                text=tribe_text if tribe_text else "No creature types with 3+ cards."
            )

        # 2. Roles
        role_text = ""
        for tag, count in sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[
            :6
        ]:
            ui_name = constants.TAG_VISUALS.get(tag, tag.capitalize())
            role_text += f"• {ui_name} ({count})\n"

        if hasattr(self, "lbl_synergy_roles"):
            self.lbl_synergy_roles.config(
                text=role_text if role_text else "No Scryfall tags matched."
            )

        # 3. Staples
        staples = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["common", "uncommon"]
            and get_gihwr(c) >= 57.0
        ]
        staples.sort(key=get_gihwr, reverse=True)
        staples_text = ""
        for c in staples[:6]:
            staples_text += f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n"

        if hasattr(self, "lbl_synergy_staples"):
            self.lbl_synergy_staples.config(
                text=staples_text if staples_text else "No premium staples drafted."
            )

        # 4. Non-Basic Lands
        non_basics.sort(key=get_gihwr, reverse=True)
        non_basic_text = ""
        for c in non_basics[:6]:
            non_basic_text += f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n"

        if hasattr(self, "lbl_synergy_lands"):
            self.lbl_synergy_lands.config(
                text=non_basic_text if non_basic_text else "No non-basic lands drafted."
            )

        # --- 6. RARES & MYTHICS ---
        rares = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["rare", "mythic"]
        ]
        rares.sort(key=get_gihwr, reverse=True)

        rare_text = ""
        for c in rares[:10]:
            rare_text += f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n"

        if hasattr(self, "lbl_recap_rares"):
            self.lbl_recap_rares.config(
                text=rare_text if rare_text else "No Rares or Mythics drafted."
            )

        # --- 7. CHARTS ---
        from src.card_logic import get_deck_metrics

        deck_metrics = get_deck_metrics(taken_cards)

        if hasattr(self, "recap_curve_plot") and self.recap_curve_plot:
            self.recap_curve_plot.update_curve(deck_metrics.distribution_all)

        if hasattr(self, "recap_type_chart") and self.recap_type_chart:
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

                # EXCLUDE BASIC LANDS
                if "Basic" in types or name in constants.BASIC_LANDS:
                    continue

                if "Creature" in types:
                    type_counts["Creature"] += 1
                elif "Planeswalker" in types:
                    type_counts["Planeswalker"] += 1
                elif "Battle" in types:
                    type_counts["Battle"] += 1
                elif "Instant" in types:
                    type_counts["Instant"] += 1
                elif "Sorcery" in types:
                    type_counts["Sorcery"] += 1
                elif "Enchantment" in types:
                    type_counts["Enchantment"] += 1
                elif "Artifact" in types:
                    type_counts["Artifact"] += 1
                elif "Land" in types:
                    type_counts["Land"] += 1
            self.recap_type_chart.update_counts(type_counts)

        # --- 8. 17LANDS API FETCH ---
        if draft_id:

            def fetch_17lands_record():
                from src.seventeenlands import Seventeenlands

                record = Seventeenlands().get_draft_record(draft_id)

                def update_ui():
                    if record and record.get("wins") is not None:
                        wins = record["wins"]
                        losses = record["losses"]
                        record_style = (
                            "success"
                            if wins >= 3
                            else ("warning" if wins >= 1 else "danger")
                        )

                        if hasattr(self, "lbl_actual_record"):
                            self.lbl_actual_record.config(
                                text=f"Actual 17Lands Record: {wins} Wins - {losses} Losses",
                                bootstyle=record_style,
                            )
                            self.lbl_actual_record.pack(anchor="center", pady=Theme.scaled_val((5, 0)))

                        if hasattr(self, "btn_17lands_link"):
                            self.btn_17lands_link.config(
                                command=lambda: open_file(record["url"])
                            )
                            self.btn_17lands_link.pack(side="right", padx=Theme.scaled_val((0, 10)))
                try:
                    self.after(0, update_ui)
                except RuntimeError:
                    pass

            threading.Thread(target=fetch_17lands_record, daemon=True).start()

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
            self.f_left, text=" LIVE PACK: TACTICAL EVALUATION ", padding=Theme.scaled_val(5)
        )
        self.pack_frame.grid(row=0, column=0, sticky="nsew", padx=(Theme.scaled_val(10), 0), pady=(Theme.scaled_val(10), 0))

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
            self.f_left, text=" SEEN CARDS (WHEEL TRACKER) ", padding=Theme.scaled_val(5)
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
        self.rail_btn.grid(row=0, column=1, rowspan=2, sticky="", padx=(Theme.scaled_val(2), Theme.scaled_val(2)))

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
        self.advisor_panel.pack(fill="x", pady=(Theme.scaled_val(10), Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10)))

        self.signal_container = CollapsibleFrame(
            self.sidebar_container,
            title="OPEN LANES",
            configuration=self.configuration,
            setting_key="open_lanes_panel",
        )
        self.signal_container.pack(fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10)))
        self.signal_meter = SignalMeter(self.signal_container.content_frame)
        self.signal_meter.pack(fill="x")

        self.curve_container = CollapsibleFrame(
            self.sidebar_container,
            title="MANA CURVE",
            configuration=self.configuration,
            setting_key="mana_curve_panel",
        )
        self.curve_container.pack(fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10)))
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
        self.pool_container.pack(fill="x", pady=(0, Theme.scaled_val(15)), padx=(0, Theme.scaled_val(10)))
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

        # Determine if the draft is mathematically completed based on taken cards
        is_bot = self._current_event_type in [
            constants.LIMITED_TYPE_STRING_DRAFT_QUICK,
            constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO_QUICK,
            constants.LIMITED_TYPE_STRING_DRAFT_BOT,
        ]

        draft_complete = (is_human or is_bot) and self._taken_count >= 42
        sealed_complete = (
            "Sealed" in self._current_event_type and self._taken_count >= 40
        )

        show_recovery = draft_complete or sealed_complete

        # Determine if we should show the explicit P1P1 OCR frame
        show_p1p1 = (
            self._current_event_set
            and is_human
            and self._current_pack <= 1
            and self._current_pick <= 1
            and self._pack_count == 0
            and self._taken_count
            < 15  # Prevents overriding a recovered draft if pack=0
            and self.configuration.settings.p1p1_ocr_enabled
            and not show_recovery  # Safety block
        )

        # Capture visibility BEFORE grid_remove() so was_hidden is accurate
        was_content_hidden = not self.content_frame.winfo_viewable()
        self.content_frame.grid_remove()
        self.waiting_frame.grid_remove()
        self.no_data_frame.grid_remove()
        if hasattr(self, "p1p1_frame"):
            self.p1p1_frame.grid_remove()
        if hasattr(self, "recovery_frame"):
            self.recovery_frame.grid_remove()

        if not has_any_datasets:
            self.no_data_frame.grid(row=0, column=0, sticky="nsew")
        elif show_recovery:
            if self._current_event_set:
                prefix = (
                    "Sealed Pool"
                    if "Sealed" in self._current_event_type
                    else "Draft Completed"
                )
                self.lbl_recovery_title.config(
                    text=f"{prefix}: {self._current_event_set} {self._current_event_type}"
                )
            self.recovery_frame.grid(row=0, column=0, sticky="nsew")

            # Force charts to render if they haven't yet
            if hasattr(self, "recap_curve_plot") and self.recap_curve_plot:
                self.recap_curve_plot.redraw()
            if hasattr(self, "recap_type_chart") and self.recap_type_chart:
                self.recap_type_chart.redraw()

        elif show_p1p1:
            self.p1p1_frame.grid(row=0, column=0, sticky="nsew")
        elif has_draft_data:
            self.content_frame.grid(row=0, column=0, sticky="nsew")

            if was_content_hidden and self.sidebar_visible:

                def fix_sash():
                    try:
                        curr_w = self.winfo_width()
                        if curr_w > 200:
                            dash_sash = getattr(
                                self.configuration.settings, "dashboard_sash", Theme.scaled_val(800)
                            )
                            safe_sash = min(dash_sash, curr_w - Theme.scaled_val(280))
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
                row=1, column=0, sticky="nsew", padx=(Theme.scaled_val(10), 0), pady=(Theme.scaled_val(15), Theme.scaled_val(10))
            )

            pack_w = max(1, self._pack_count)
            miss_w = max(1, self._missing_count)

            # minsize guarantees that even if a table only has 1 card, Tkinter will refuse
            # to crush it smaller than 140 pixels, ensuring it remains fully readable!
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
            default_sash = max(Theme.scaled_val(50), current_width - Theme.scaled_val(280)) if current_width > Theme.scaled_val(280) else Theme.scaled_val(800)

            dash_sash = getattr(
                self.configuration.settings, "dashboard_sash", default_sash
            )
            if dash_sash < Theme.scaled_val(50) or dash_sash >= current_width - Theme.scaled_val(20):
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
