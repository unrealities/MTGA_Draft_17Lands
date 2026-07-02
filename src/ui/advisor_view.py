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
    def __init__(
        self,
        parent,
        configuration,
        collapsible=True,
        mini_mode=False,
        on_click_callback=None,
    ):
        super().__init__(parent)
        self.configuration = configuration
        self.is_collapsible = collapsible
        self.mini_mode = mini_mode
        self.on_click_callback = on_click_callback
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
            ).pack(pady=10, anchor="center")
            return

        # Show top 5 in Mini Mode or Sidebar
        limit = 5 if self.mini_mode else 3

        # Font Scaling
        name_font_size = 14 if self.mini_mode else 12
        reason_font_size = 11 if self.mini_mode else 9
        badge_size = 28 if self.mini_mode else 24

        for i, rec in enumerate(recs[:limit]):
            item_frame = tb.Frame(self.container)
            item_frame.pack(fill="x", side="top", anchor="nw", padx=20, pady=(0, 12))

            is_elite = rec.is_elite
            badge_bg = Theme.SUCCESS if is_elite else Theme.ACCENT

            # 1. Left Accent Line (Using tk.Frame for a guaranteed solid color block across all OSs)
            accent = tkinter.Frame(item_frame, width=4)
            try:
                accent.configure(bg=badge_bg)
            except tkinter.TclError:
                # Safe fallback if native semantic colors fail in older Tkinter versions
                accent.configure(bg="#10b981" if is_elite else "#3b82f6")
            accent.pack(side="left", fill="y", padx=(2, 8))

            # 2. Content Body
            content_frame = tb.Frame(item_frame)
            content_frame.pack(side="left", fill="both", expand=True)

            header_frame = tb.Frame(content_frame)
            header_frame.pack(fill="x", anchor="w")

            # 3. The Score (Bold, Colored)
            score_prefix = "★ " if is_elite else ""
            lbl_score = tb.Label(
                header_frame,
                text=f"{score_prefix}{rec.contextual_score:.0f}",
                font=(Theme.FONT_FAMILY, name_font_size + 2, "bold"),
            )
            try:
                lbl_score.configure(foreground=badge_bg)
            except tkinter.TclError:
                lbl_score.configure(foreground="#10b981" if is_elite else "#3b82f6")
            lbl_score.pack(side="left", anchor="nw")

            # Separator
            lbl_sep = tb.Label(
                header_frame,
                text=" | ",
                font=(Theme.FONT_FAMILY, name_font_size, "bold"),
            )
            try:
                lbl_sep.configure(foreground=Theme.TEXT_MUTED)
            except tkinter.TclError:
                pass
            lbl_sep.pack(side="left", anchor="nw", padx=4, pady=1)

            # 4. The Card Name
            font_weight = "bold" if is_elite else "normal"
            lbl_name = tb.Label(
                header_frame,
                text=rec.card_name.upper(),
                font=(Theme.FONT_FAMILY, name_font_size, font_weight),
                wraplength=180 if self.mini_mode else 160,
                justify="left",
            )
            if is_elite:
                try:
                    lbl_name.configure(foreground=Theme.SUCCESS)
                except tkinter.TclError:
                    lbl_name.configure(foreground="#10b981")
            lbl_name.pack(side="left", anchor="nw", pady=2)

            # --- Body: Reasoning Description & Tags ---
            reason_text = ""
            if is_elite:
                reason_text += f"ELITE PICK (+{rec.z_score}σ)"
                if rec.reasoning:
                    reason_text += f" | {' | '.join(rec.reasoning)}"
            elif rec.reasoning:
                reason_text += " | ".join(rec.reasoning)
            else:
                reason_text += "Tactically superior for your pool"

            if rec.tags:
                tag_strings = [TAG_VISUALS.get(t, t.capitalize()) for t in rec.tags]
                reason_text += f"\n{', '.join(tag_strings)}"

            lbl_reason = tb.Label(
                content_frame,
                text=reason_text,
                font=(Theme.FONT_FAMILY, reason_font_size),
                wraplength=250 if self.mini_mode else 220,
                justify="left",
            )
            lbl_reason.pack(anchor="nw", pady=(2, 0))

            if self.on_click_callback:
                for w in [
                    item_frame,
                    content_frame,
                    header_frame,
                    lbl_score,
                    lbl_sep,
                    lbl_name,
                    lbl_reason,
                ]:
                    w.configure(cursor="hand2")
                    w.bind(
                        "<Button-1>",
                        lambda e, n=rec.card_name, wdg=item_frame: self.on_click_callback(
                            n, wdg
                        ),
                    )

    def _on_theme_change(self, event=None):
        if self.winfo_exists():
            self.update_recommendations(self.last_recs)
