"""
src/ui/dashboard_recap.py
Dedicated module for the Post-Draft Recap screen.
Calculates and displays Pool Grades, Steals, Reaches, and Synergies.
"""

import tkinter
from tkinter import ttk
import threading
from src import constants
from src.ui.styles import Theme
from src.utils import open_file
from src.ui.components import ManaCurvePlot, TypePieChart, VerticalScrolledFrame
from src.card_logic import get_deck_metrics, identify_top_pairs


class DraftRecapScreen(ttk.Frame):
    def __init__(self, parent, launch_sealed_callback=None):
        super().__init__(parent)
        self.launch_sealed_callback = launch_sealed_callback
        self.tab_scrollers = []
        self._build_ui()

    @staticmethod
    def _wrap_to_width(lbl, width):
        # Wrap each stat box to its own width; a wraplength wider than the box
        # pushes the end of every line out of view.
        if width > 20 and abs(int(str(lbl.cget("wraplength")) or 0) - width) > 2:
            lbl.configure(wraplength=width)

    def _create_stat_box(self, parent, title, text_var_name):
        frame = ttk.Labelframe(parent, text=title, padding=Theme.scaled_val(8))
        lbl = ttk.Label(
            frame,
            text="",
            font=Theme.scaled_font(9),
            justify="left",
            anchor="nw",
            wraplength=Theme.scaled_val(300),
        )
        lbl.pack(anchor="nw", fill="both", expand=True)
        lbl.bind("<Configure>", lambda e: self._wrap_to_width(e.widget, e.width))
        setattr(self, text_var_name, lbl)
        return frame

    def _add_tab(self, text):
        """Add a notebook tab whose content scrolls when the pane is too short."""
        scroller = VerticalScrolledFrame(
            self.recap_notebook, padding=Theme.scaled_val(15)
        )
        self.recap_notebook.add(scroller, text=text)
        self.tab_scrollers.append(scroller)
        return scroller.content

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # HEADER
        header_frame = ttk.Frame(
            self, padding=Theme.scaled_val(10), style="Card.TFrame"
        )
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

        self.btn_sealed_studio = ttk.Button(
            header_frame,
            text="⚔️ Enter Sealed Studio",
            bootstyle="warning",
            command=self.launch_sealed_callback,
        )

        # TABBED CONTENT
        self.recap_notebook = ttk.Notebook(self)
        self.recap_notebook.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=Theme.scaled_val(10),
            pady=Theme.scaled_val((10, 0)),
        )

        # --- TAB 1: DRAFT RECAP ---
        tab_recap = self._add_tab(" 🏆 Draft Recap ")

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
            top_recap, text="Top 23 Cards Avg Win Rate: --%", font=Theme.scaled_font(11)
        )
        self.lbl_recovery_stats.pack(anchor="center")

        self.lbl_actual_record = ttk.Label(
            top_recap, text="", font=Theme.scaled_font(11, "bold")
        )

        grid_recap = ttk.Frame(tab_recap)
        grid_recap.pack(fill="both", expand=True)
        grid_recap.columnconfigure((0, 1), weight=1, uniform="stat")
        grid_recap.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_recap, "TOP ARCHETYPES", "lbl_recap_archetypes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_recap, "BEST CARDS DRAFTED", "lbl_recap_best").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_recap, "BIGGEST STEALS (LATE PICKS)", "lbl_recap_steals"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_recap, "BIGGEST REACHES (EARLY PICKS)", "lbl_recap_reaches"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 2: SYNERGY & ROLES ---
        tab_synergy = self._add_tab(" 🧩 Synergy & Roles ")

        grid_synergy = ttk.Frame(tab_synergy)
        grid_synergy.pack(fill="both", expand=True)
        grid_synergy.columnconfigure((0, 1), weight=1, uniform="stat")
        grid_synergy.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_synergy, "TOP CREATURE TYPES", "lbl_synergy_tribes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_synergy, "CARD ROLES", "lbl_synergy_roles").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_synergy, "PREMIUM STAPLES", "lbl_synergy_staples"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_synergy, "NON-BASIC LANDS", "lbl_synergy_lands"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 3: MANA & CURVE ---
        tab_analysis = self._add_tab(" 📊 Mana & Curve ")
        tab_analysis.columnconfigure((0, 1), weight=1, uniform="stat")
        tab_analysis.rowconfigure(0, weight=1)

        charts_frame = ttk.Frame(tab_analysis)
        charts_frame.grid(
            row=0, column=0, sticky="nsew", padx=Theme.scaled_val((0, 10))
        )

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

        for scroller in self.tab_scrollers:
            scroller.bind_mousewheel()

    def update_summary(self, taken_cards, metrics, draft_id, event_type):
        if not taken_cards or len(taken_cards) < 40:
            return

        self.lbl_actual_record.pack_forget()
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

        # 1. OVERALL GRADE
        valid_cards.sort(key=get_gihwr, reverse=True)
        top_23 = valid_cards[:23]
        avg_gihwr = sum(get_gihwr(c) for c in top_23) / len(top_23)

        global_mean, global_std = (
            metrics.get_metrics("All Decks", "gihwr") if metrics else (54.5, 3.5)
        )
        if global_mean <= 0:
            global_mean = 54.5
        if global_std <= 0:
            global_std = 3.5

        z_score = (avg_gihwr - global_mean) / global_std
        pool_power = max(0, min(100, 75.0 + (z_score * 12.0)))

        grade_map = [
            (90, "S (God Tier)", "success"),
            (85, "A (Amazing)", "success"),
            (80, "B+ (Great)", "info"),
            (75, "B (Good)", "info"),
            (70, "C (Average)", "warning"),
            (60, "D (Below Average)", "danger"),
        ]
        grade_str, bootstyle = next(
            ((g, s) for threshold, g, s in grade_map if pool_power >= threshold),
            ("F (Trainwreck)", "danger"),
        )

        self.lbl_recovery_grade.config(
            text=f"Pool Quality: {pool_power:.0f}/100 [{grade_str}]",
            bootstyle=bootstyle,
        )
        self.lbl_recovery_stats.config(
            text=f"Top 23 Avg Win Rate: {avg_gihwr:.1f}% (Format Avg: {global_mean:.1f}%)"
        )

        # 2. TOP ARCHETYPES
        from src.utils import normalize_color_string

        top_pairs = identify_top_pairs(taken_cards, metrics)
        arch_data = []
        for pair in top_pairs:
            lane = normalize_color_string("".join(pair))
            wr, _ = metrics.get_metrics(lane, "gihwr") if metrics else (0, 0)
            arch_data.append((constants.COLOR_NAMES_DICT.get(lane, lane), wr))

        arch_data.sort(key=lambda x: x[1], reverse=True)
        arch_text = "".join(
            [f"• {n} ({w:.1f}%)\n" if w > 0 else f"• {n}\n" for n, w in arch_data[:3]]
        )
        self.lbl_recap_archetypes.config(
            text=arch_text if arch_text else "None Identified"
        )

        # 3. BEST CARDS
        best_text = "".join(
            [
                f"• {c.get('name', 'Unknown')} ({get_gihwr(c):.1f}%)\n"
                for c in top_23[:6]
            ]
        )
        self.lbl_recap_best.config(text=best_text)

        # 4. STEALS & REACHES
        total_cards = len(taken_cards)
        cards_per_pack = (
            15
            if total_cards >= 45
            else (
                14
                if total_cards >= 42
                else (total_cards // 3 if total_cards >= 3 else 14)
            )
        )

        steals, reaches = [], []
        for i, c in enumerate(taken_cards):
            name = c.get("name", "")
            if "Basic" in c.get("types", []) or name in constants.BASIC_LANDS:
                continue

            pack, pick = (i // cards_per_pack) + 1, (i % cards_per_pack) + 1
            gihwr, alsa, ata = (
                get_gihwr(c),
                float(c.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0)),
                float(c.get("deck_colors", {}).get("All Decks", {}).get("ata", 0.0)),
            )

            if alsa > 0 and pick > alsa + 1.5 and gihwr >= 55.0:
                steals.append((name, pack, pick, alsa, pick - alsa))
            if ata > 0 and ata > pick + 1.5 and gihwr < 54.0:
                reaches.append((name, pack, pick, ata, ata - pick))

        steals.sort(key=lambda x: x[4], reverse=True)
        reaches.sort(key=lambda x: x[4], reverse=True)

        self.lbl_recap_steals.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ALSA {a:.1f} | +{d:.1f})\n"
                    for n, pa, pi, a, d in steals[:6]
                ]
            )
            or "No major steals detected."
        )
        self.lbl_recap_reaches.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ATA {a:.1f} | -{d:.1f})\n"
                    for n, pa, pi, a, d in reaches[:6]
                ]
            )
            or "No major reaches detected."
        )

        # 5. SYNERGY & ROLES
        subs_counts, tags_count, non_basics = {}, {}, []
        for c in taken_cards:
            if "Basic" in c.get("types", []) or c.get("name") in constants.BASIC_LANDS:
                continue
            if "Land" in c.get("types", []):
                non_basics.append(c)
            if "Creature" in c.get("types", []):
                for s in c.get("subtypes", []):
                    subs_counts[s] = subs_counts.get(s, 0) + 1
            for t in c.get("tags", []):
                tags_count[t] = tags_count.get(t, 0) + 1

        top_tribes = sorted(subs_counts.items(), key=lambda x: x[1], reverse=True)
        self.lbl_synergy_tribes.config(
            text="".join([f"• {t} ({c})\n" for t, c in top_tribes[:6] if c >= 3])
            or "No creature types with 3+ cards."
        )

        self.lbl_synergy_roles.config(
            text="".join(
                [
                    f"• {constants.TAG_VISUALS.get(t, t.capitalize())} ({c})\n"
                    for t, c in sorted(
                        tags_count.items(), key=lambda x: x[1], reverse=True
                    )[:6]
                ]
            )
            or "No Scryfall tags matched."
        )

        staples = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["common", "uncommon"]
            and get_gihwr(c) >= 57.0
        ]
        staples.sort(key=get_gihwr, reverse=True)
        self.lbl_synergy_staples.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in staples[:6]]
            )
            or "No premium staples drafted."
        )

        non_basics.sort(key=get_gihwr, reverse=True)
        self.lbl_synergy_lands.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in non_basics[:6]]
            )
            or "No non-basic lands drafted."
        )

        # 6. RARES & MYTHICS
        rares = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["rare", "mythic"]
        ]
        rares.sort(key=get_gihwr, reverse=True)
        self.lbl_recap_rares.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in rares[:10]]
            )
            or "No Rares or Mythics drafted."
        )

        # 7. CHARTS
        deck_metrics = get_deck_metrics(taken_cards)
        self.recap_curve_plot.update_curve(deck_metrics.distribution_all)

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
            types = card.get("types", [])
            if "Basic" in types or card.get("name") in constants.BASIC_LANDS:
                continue
            for t in [
                "Creature",
                "Planeswalker",
                "Battle",
                "Instant",
                "Sorcery",
                "Enchantment",
                "Artifact",
                "Land",
            ]:
                if t in types:
                    type_counts[t] += 1
        self.recap_type_chart.update_counts(type_counts)

        # 8. SEALED STUDIO BTN
        if "Sealed" in (event_type or ""):
            self.btn_sealed_studio.pack(side="right", padx=Theme.scaled_val(10))
        else:
            self.btn_sealed_studio.pack_forget()

        # 9. 17LANDS API FETCH
        if draft_id:

            def fetch_17lands_record():
                from src.seventeenlands import Seventeenlands

                record = Seventeenlands().get_draft_record(draft_id)

                def apply_ui():
                    if record and record.get("wins") is not None:
                        w, l = record["wins"], record["losses"]
                        self.lbl_actual_record.config(
                            text=f"Actual 17Lands Record: {w} Wins - {l} Losses",
                            bootstyle=(
                                "success"
                                if w >= 3
                                else ("warning" if w >= 1 else "danger")
                            ),
                        )
                        self.lbl_actual_record.pack(
                            anchor="center", pady=Theme.scaled_val((5, 0))
                        )
                        self.btn_17lands_link.config(
                            command=lambda: open_file(record["url"])
                        )
                        self.btn_17lands_link.pack(
                            side="right", padx=Theme.scaled_val((0, 10))
                        )

                try:
                    self.after(0, apply_ui)
                except RuntimeError:
                    pass

            threading.Thread(target=fetch_17lands_record, daemon=True).start()
