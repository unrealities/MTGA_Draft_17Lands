"""
src/ui/advisor_view.py
The Professional Advisor UI Component.
"""

import tkinter
from tkinter import ttk
import ttkbootstrap as tb
from typing import List
from src.advisor.schema import Recommendation
from src.ui.styles import Theme
from src.constants import TAG_VISUALS
from src.ui.components import CollapsibleFrame


class AdvisorPanel(tb.Frame):
    def __init__(self, parent, configuration, collapsible=True, mini_mode=False):
        super().__init__(parent)
        self.configuration = configuration
        self.is_collapsible = collapsible
        self.mini_mode = mini_mode
        self.last_recs = []
        self._build_ui()
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

    def _build_ui(self):
        if self.is_collapsible:
            self.collapsible = CollapsibleFrame(
                self,
                title="ADVISOR RECOMMENDATIONS",
                configuration=self.configuration,
                setting_key="advisor_panel",
            )
            self.collapsible.pack(fill="x", side="top", anchor="n")
            self.container = tb.Frame(self.collapsible.content_frame)
        else:
            self.container = tb.Frame(self)

        self.container.pack(fill="both", expand=True, side="top", anchor="n")

    def update_recommendations(self, recs: List[Recommendation]):
        """Renders the top choices with reasoning, score badges, and semantic tags."""
        self.last_recs = recs
        for widget in self.container.winfo_children():
            widget.destroy()

        if not recs:
            tb.Label(
                self.container,
                text="Calculating tactical scores...",
                font=(Theme.FONT_FAMILY, 10 if self.mini_mode else 9),
            ).pack(pady=10, anchor="nw")
            return

        # Show top 5 in Mini Mode or Sidebar
        limit = 5 if self.mini_mode else 3

        # Font Scaling
        name_font_size = 14 if self.mini_mode else 12
        reason_font_size = 11 if self.mini_mode else 9
        badge_size = 28 if self.mini_mode else 24

        for i, rec in enumerate(recs[:limit]):
            item_frame = tb.Frame(self.container)
            item_frame.pack(fill="x", side="top", anchor="nw", pady=(0, 12))

            # --- Header: Score Badge + Card Name ---
            header_frame = tb.Frame(item_frame)
            header_frame.pack(fill="x", anchor="w")

            is_elite = rec.is_elite
            badge_bg = Theme.SUCCESS if is_elite else Theme.ACCENT

            # 1. The Score Badge
            badge = tb.Canvas(
                header_frame,
                width=badge_size,
                height=badge_size,
                bg=Theme.BG_PRIMARY,
                highlightthickness=0,
            )
            badge.pack(side="left", pady=1, padx=(0, 8), anchor="nw")

            badge.create_oval(
                2, 2, badge_size - 2, badge_size - 2, fill=badge_bg, outline=badge_bg
            )
            badge.create_text(
                badge_size // 2,
                badge_size // 2,
                text=f"{rec.contextual_score:.0f}",
                fill="#ffffff",
                font=(Theme.FONT_FAMILY, name_font_size - 3, "bold"),
            )

            # 2. The Card Name
            name_color = Theme.ACCENT if is_elite else Theme.TEXT_MAIN
            font_weight = "bold" if is_elite else "normal"

            lbl_name = tb.Label(
                header_frame,
                text=rec.card_name.upper(),
                bootstyle="primary" if is_elite else None,
                font=(Theme.FONT_FAMILY, name_font_size, font_weight),
                wraplength=200 if self.mini_mode else 180,
                justify="left",
            )
            lbl_name.pack(side="left", anchor="nw", pady=(2, 0))

            # --- Body: Reasoning Description & Tags ---
            reason_text = ""
            if is_elite:
                reason_text += f"⭐ ELITE PICK (+{rec.z_score}σ)"
                if rec.reasoning:
                    reason_text += f" | {' | '.join(rec.reasoning)}"
            elif rec.reasoning:
                reason_text += " | ".join(rec.reasoning)
            else:
                reason_text += "Tactically superior for your pool"

            if rec.tags:
                tag_strings = [TAG_VISUALS.get(t, t.capitalize()) for t in rec.tags]
                reason_text += f"\nRoles: {', '.join(tag_strings)}"

            lbl_reason = tb.Label(
                item_frame,
                text=reason_text,
                font=(Theme.FONT_FAMILY, reason_font_size),
                wraplength=260 if self.mini_mode else 230,
                justify="left",
            )
            lbl_reason.pack(anchor="nw", pady=(4, 0))

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.update_recommendations(self.last_recs)
