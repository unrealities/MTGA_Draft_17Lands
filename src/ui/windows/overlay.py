"""
src/ui/windows/overlay.py
Compact Overlay Window for in-game drafting.
"""

import tkinter
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from src import constants
from src.card_logic import row_color_tag
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip


class CompactOverlay(tb.Toplevel):
    def __init__(self, parent, orchestrator, configuration, on_restore):
        super().__init__(title="Draft Overlay", topmost=True)
        self.orchestrator = orchestrator
        self.configuration = configuration
        self.on_restore = on_restore
        self.current_pack_cards = []
        self.overrideredirect(True)
        self.geometry("330x600+50+50")
        self.configure(bg=Theme.BG_PRIMARY)

        try:
            self.attributes("-alpha", 0.92)
        except Exception:
            pass

        self._bind_drag_events()

        self._build_ui()

    def _bind_drag_events(self):
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<ButtonRelease-1>", self._stop_move)
        self.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _stop_move(self, event):
        self.x = None
        self.y = None

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        # --- HEADER (Draggable) ---
        header = tb.Frame(self, bootstyle="secondary")
        header.pack(fill=X, ipady=5)

        # Scan / Refresh Button (Packed dynamically in update_data)
        self.btn_scan = tb.Button(
            header,
            text="SCAN P1P1",
            bootstyle="success-outline",
            command=self._manual_scan,
        )

        # Restore Button (Return to Main App)
        tb.Button(header, text="⤢", bootstyle="link", command=self.on_restore).pack(
            side=RIGHT, padx=5
        )

        # Status Label
        self.lbl_status = tb.Label(
            header,
            text="Waiting...",
            font=("Segoe UI", 9, "bold"),
            bootstyle="inverse-secondary",
        )
        self.lbl_status.pack(side=RIGHT, padx=5)

        # --- DYNAMIC CARD LIST ---
        self.table_manager = DynamicTreeviewManager(
            self,
            view_id="overlay_table",
            configuration=self.configuration,
            on_update_callback=self._trigger_refresh,
        )
        self.table_manager.pack(fill=BOTH, expand=True, padx=2, pady=2)

        # Link the tooltip logic
        self.tree = self.table_manager.tree
        self.tree.bind("<<TreeviewSelect>>", self._on_card_select)

    def _trigger_refresh(self):
        """Called when user right-clicks to add/remove columns. Forces re-render."""
        if hasattr(self.orchestrator, "refresh_callback"):
            self.orchestrator.refresh_callback()

    def _manual_scan(self):
        """Manually triggers a P1P1 scan via the Orchestrator."""
        save_img = self.configuration.settings.save_screenshot_enabled
        data_found = self.orchestrator.scanner.draft_data_search(True, save_img)

        if data_found and hasattr(self.orchestrator, "refresh_callback"):
            self.orchestrator.refresh_callback()

    def update_data(
        self, pack_cards, colors, metrics, tier_data, current_pick, recommendations=None
    ):
        # Update State
        self.current_pack_cards = pack_cards or []
        pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
        self.lbl_status.config(text=f"P{pk} / P{pi}")

        # Dynamic P1P1 Button Logic
        if pk <= 1 and pi <= 1:
            self.btn_scan.pack(side=LEFT, padx=5, before=self.lbl_status)
        else:
            self.btn_scan.pack_forget()

        # Update Table Reference (in case it was rebuilt)
        self.tree = self.table_manager.tree

        for item in self.tree.get_children():
            self.tree.delete(item)

        if not pack_cards:
            return

        rec_map = {r.card_name: r for r in (recommendations or [])}
        active_filter = colors[0] if colors else "All Decks"
        processed_rows = []

        for card in pack_cards:
            name = card.get(constants.DATA_FIELD_NAME, "Unknown")
            stats = card.get("deck_colors", {}).get(active_filter, {})
            rec = rec_map.get(name)

            row_tag = "bw_odd" if len(processed_rows) % 2 == 0 else "bw_even"
            if self.configuration.settings.card_colors_enabled:
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
            for field in self.table_manager.active_fields:
                if field == "name":
                    short_name = (
                        display_name
                        if len(display_name) <= 22
                        else display_name[:20] + ".."
                    )
                    row_values.append(short_name)
                elif field == "value":
                    val = rec.contextual_score if rec else stats.get("gihwr", 0.0)
                    row_values.append(f"{val:.0f}")
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
                    row_values.append(
                        f"{val:.1f}"
                        if field in ["gihwr", "ohwr", "gpwr", "gnswr", "gdwr", "iwd"]
                        else str(val)
                    )

            # Sort by Tactical Value if available, else fallback to raw win rate
            sort_val = rec.contextual_score if rec else stats.get("gihwr", 0.0)
            processed_rows.append(
                {"vals": row_values, "tag": row_tag, "sort_key": sort_val}
            )

        # Apply Sort and Render
        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)
        for row in processed_rows:
            self.tree.insert("", "end", values=row["vals"], tags=(row["tag"],))

    def _on_card_select(self, event):
        """Displays the robust Card Tooltip when a row is clicked."""
        selection = self.tree.selection()
        if not selection:
            return

        item_vals = self.tree.item(selection[0])["values"]
        card_name = (
            str(item_vals[0])
            .replace("⭐ ", "")
            .replace("[+] ", "")
            .replace("..", "")
            .strip()
        )

        # Fuzzy match to handle the '..' truncation
        found = next(
            (
                c
                for c in self.current_pack_cards
                if card_name in c.get(constants.DATA_FIELD_NAME, "")
            ),
            None,
        )

        if found:
            arch = self.orchestrator.scanner.set_data.get_card_archetypes_by_field(
                found[constants.DATA_FIELD_NAME], constants.DATA_FIELD_GIHWR
            )
            CardToolTip(
                self.tree,
                found[constants.DATA_FIELD_NAME],
                found.get(constants.DATA_FIELD_DECK_COLORS, {}),
                found.get(constants.DATA_SECTION_IMAGES, []),
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
                archetypes=arch,
            )
