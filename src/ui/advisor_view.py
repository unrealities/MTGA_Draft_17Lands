"""
src/ui/advisor_view.py
Advisor UI Component
"""

import tkinter
from tkinter import ttk
from typing import List
from src.advisor.schema import Recommendation
from src.ui.styles import Theme
from src.ui.components import CollapsibleFrame
from src.constants import TAG_VISUALS


class AdvisorPanel(ttk.Frame):
    def __init__(self, parent, configuration):
        super().__init__(parent)
        self.configuration = configuration
        self._build_ui()

    def _build_ui(self):
        self.collapsible = CollapsibleFrame(
            self,
            title="ADVISOR RECOMMENDATIONS",
            configuration=self.configuration,
            setting_key="advisor_panel",
        )
        self.collapsible.pack(fill="x", expand=True)

        self.container = ttk.Frame(self.collapsible.content_frame)
        self.container.pack(fill="x", expand=True)

    def update_recommendations(self, recs: List[Recommendation]):
        """Renders the top choices with reasoning, score badges, and semantic tags."""
        for widget in self.container.winfo_children():
            widget.destroy()

        if not recs:
            ttk.Label(
                self.container,
                text="Analyzing draft path...",
                foreground=Theme.TEXT_MAIN,
                font=(Theme.FONT_FAMILY, 9),
            ).pack(pady=5)
            return

        for i, rec in enumerate(recs[:3]):
            item_frame = ttk.Frame(self.container)
            item_frame.pack(fill="x", pady=(0, 10))

            # --- Header: Score Badge + Card Name ---
            header_frame = ttk.Frame(item_frame)
            header_frame.pack(fill="x", anchor="w")

            is_elite = rec.is_elite
            badge_bg = Theme.SUCCESS if is_elite else Theme.ACCENT

            badge = tkinter.Canvas(
                header_frame,
                width=24,
                height=24,
                bg=Theme.BG_PRIMARY,
                highlightthickness=0,
            )
            badge.pack(side="left", pady=1, padx=(0, 6), anchor="n")

            badge.create_oval(2, 2, 22, 22, fill=badge_bg, outline=badge_bg)
            badge.create_text(
                12,
                12,
                text=f"{rec.contextual_score:.0f}",
                fill="#ffffff",
                font=(Theme.FONT_FAMILY, 12, "bold"),
            )

            name_color = Theme.ACCENT if is_elite else Theme.TEXT_MAIN
            font_weight = "bold" if is_elite else "normal"

            lbl_name = ttk.Label(
                header_frame,
                text=rec.card_name.upper(),
                foreground=name_color,
                font=(Theme.FONT_FAMILY, 12, font_weight),
                wraplength=180,
                justify="left",
            )
            lbl_name.pack(side="left", anchor="n", pady=(2, 0))

            # --- Body: Reasoning Description & Tags ---
            reason_text = ""
            if is_elite:
                reason_text += f"⭐ ELITE PICK (+{rec.z_score}σ)"
                if rec.reasoning:
                    reason_text += f" | {' | '.join(rec.reasoning)}"
            elif rec.reasoning:
                reason_text += " | ".join(rec.reasoning)
            else:
                reason_text += "Tactically superior for your current pool"

            if rec.tags:
                tag_strings = [TAG_VISUALS.get(t, t.capitalize()) for t in rec.tags]
                reason_text += f"\nRoles: {', '.join(tag_strings)}"

            lbl_reason = ttk.Label(
                item_frame,
                text=reason_text,
                font=(Theme.FONT_FAMILY, 9),
                foreground=Theme.TEXT_MAIN,
                wraplength=230,
                justify="left",
            )
            lbl_reason.pack(anchor="w", pady=(4, 0))
