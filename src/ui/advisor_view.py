"""
src/ui/advisor_view.py
The Professional Advisor UI Component.
"""

import tkinter
from tkinter import ttk
from typing import List
from src.advisor.schema import Recommendation
from src.ui.styles import Theme
from src.ui.components import CollapsibleFrame
from src.constants import TAG_VISUALS


class AdvisorPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame", padding=10)
        self._build_ui()

    def _build_ui(self):
        self.collapsible = CollapsibleFrame(self, title="ADVISOR RECOMMENDATIONS")
        self.collapsible.pack(fill="x", expand=True)

        self.container = ttk.Frame(self.collapsible.content_frame, style="Card.TFrame")
        self.container.pack(fill="x", expand=True)

    def update_recommendations(self, recs: List[Recommendation]):
        """Renders the top choices with reasoning and semantic tags."""
        for widget in self.container.winfo_children():
            widget.destroy()

        if not recs:
            ttk.Label(
                self.container,
                text="Analyzing draft path...",
                foreground=Theme.TEXT_MUTED,
            ).pack(pady=5)
            return

        for i, rec in enumerate(recs[:3]):
            frame = ttk.Frame(self.container, style="Card.TFrame", padding=2)
            frame.pack(fill="x", pady=1)

            header = ttk.Frame(frame, style="Card.TFrame")
            header.pack(fill="x")

            name_color = Theme.ACCENT if rec.is_elite else Theme.TEXT_MAIN
            font_weight = "bold" if rec.is_elite else "normal"

            tag_string = ""
            if rec.tags:
                # Convert ["removal", "evasion"] -> "[🎯 Removal, 🦅 Evasion]"
                formatted_tags = [TAG_VISUALS.get(t, t.capitalize()) for t in rec.tags]
                tag_string = f"  [{', '.join(formatted_tags)}]"

            lbl_name = ttk.Label(
                header,
                text=f"{i+1}. {rec.card_name.upper()}{tag_string}",
                foreground=name_color,
                font=(Theme.FONT_FAMILY, 9, font_weight),
            )
            lbl_name.pack(side="left")

            lbl_score = ttk.Label(
                header,
                text=f"Value: {rec.contextual_score}",
                foreground=Theme.TEXT_MUTED,
                font=(Theme.FONT_FAMILY, 8),
            )
            lbl_score.pack(side="right")

            # Reasoning display logic
            if rec.is_elite:
                reason_text = f"⭐ ELITE PICK (+{rec.z_score}σ)"
                if rec.reasoning:
                    reason_text += f" | {' | '.join(rec.reasoning)}"
            elif rec.reasoning:
                reason_text = " | ".join(rec.reasoning)
            else:
                reason_text = "Tactically superior for your current pool"

            lbl_reason = ttk.Label(
                frame,
                text=reason_text,
                font=(Theme.FONT_FAMILY, 8),
                foreground=Theme.SUCCESS if rec.is_elite else Theme.TEXT_MUTED,
            )
            lbl_reason.pack(anchor="w", padx=15)
